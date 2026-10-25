"""Database failures remain recoverable across authentication and listing flows."""

from datetime import datetime, timezone
from html.parser import HTMLParser
from unittest.mock import patch

from bson import ObjectId
import mongomock
from pymongo.errors import AutoReconnect, DuplicateKeyError, ServerSelectionTimeoutError
import pytest
from werkzeug.security import generate_password_hash

from app import create_app


ACCOUNT = {"email": "seller@example.test", "password": "password123"}
FAILURE_DETAIL = "private connection details must not appear in HTML"


class RecoveryPage(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.links = {}
        self.forms = []
        self.link = None
        self.feed(response.get_data(as_text=True))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.link = {"href": attrs.get("href"), "text": []}
        elif tag == "form":
            self.forms.append(attrs)

    def handle_data(self, data):
        if self.link is not None:
            self.link["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.link is not None:
            self.links[" ".join("".join(self.link["text"]).split())] = self.link["href"]
            self.link = None


@pytest.fixture(scope="module")
def password_hash():
    return generate_password_hash(ACCOUNT["password"])


@pytest.fixture
def app(password_hash):
    mongo = mongomock.MongoClient(tz_aware=True)
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "database-errors-test-only",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "test_database_errors",
        "MONGO_CLIENT": mongo,
    })
    db = application.extensions["mongo_db"]
    owner_id = db.users.insert_one({
        "username": "Campus Seller", "email": ACCOUNT["email"],
        "password_hash": password_hash,
    }).inserted_id
    db.items.insert_one({
        "_id": ObjectId("111111111111111111111111"),
        "owner_id": owner_id, "title": "Desk lamp", "description": "A working lamp.",
        "price": 12.0, "category": "Furniture", "condition": "Good",
        "image_url": "", "contact_info": ACCOUNT["email"], "status": "active",
        "created_at": datetime.now(timezone.utc),
    })
    yield application
    mongo.close()


@pytest.fixture
def seller(app, auth_post):
    browser = app.test_client()
    assert auth_post(browser, "/login", data=ACCOUNT).status_code == 302
    assert browser.get("/my-items").status_code == 200
    return browser


def assert_unavailable(response):
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert b"Temporarily unavailable" in response.data
    assert b'role="alert"' in response.data
    assert FAILURE_DETAIL.encode() not in response.data
    return RecoveryPage(response)


@pytest.mark.parametrize("path", (
    "/items", "/search?q=lamp%20%26%20text&sort=price_desc", "/my-items", "/items/new",
))
def test_user_loading_failure_renders_once_and_keeps_session_for_recovery(app, seller, path):
    users = app.extensions["mongo_db"].users
    with seller.session_transaction() as state:
        before = dict(state)
    with patch.object(users, "find_one", side_effect=AutoReconnect(FAILURE_DETAIL)) as lookup:
        response = seller.get(path)
        page = assert_unavailable(response)
        assert lookup.call_count == 1
    assert page.links["Try again"] == path
    assert "Log out" not in page.links
    assert not page.forms
    with seller.session_transaction() as state:
        assert dict(state) == before
    recovered = seller.get(page.links["Try again"])
    assert recovered.status_code == 200
    assert b"Log out" in recovered.data


@pytest.mark.parametrize("path", ("/login", "/register"))
@pytest.mark.parametrize("failure", (AutoReconnect, ServerSelectionTimeoutError))
def test_account_lookup_failure_does_not_sign_in_or_expose_credentials(app, csrf_token, path, failure):
    browser = app.test_client()
    token = csrf_token(browser, path)
    users = app.extensions["mongo_db"].users
    with patch.object(users, "find_one", side_effect=failure(FAILURE_DETAIL)) as lookup:
        response = browser.post(path, data={**ACCOUNT, "username": "New seller", "csrf_token": token})
        page = assert_unavailable(response)
        assert lookup.call_count == 1
    assert "Try again" not in page.links
    assert page.links["Go to log in"] == "/login"
    assert not page.forms
    assert ACCOUNT["password"].encode() not in response.data
    assert users.count_documents({}) == 1
    with browser.session_transaction() as state:
        assert "_user_id" not in state
        assert state["auth_csrf_token"] == token
    assert browser.get(page.links["Go to log in"]).status_code == 200


def test_registration_insert_failure_is_recoverable_without_automatic_retry(app, csrf_token):
    browser = app.test_client()
    token = csrf_token(browser, "/register")
    users = app.extensions["mongo_db"].users
    with patch.object(users, "insert_one", side_effect=AutoReconnect(FAILURE_DETAIL)) as insert:
        response = browser.post("/register", data={
            "username": "New seller", "email": "new@example.test",
            "password": ACCOUNT["password"], "csrf_token": token,
        })
        assert_unavailable(response)
        assert insert.call_count == 1
    assert users.count_documents({}) == 1
    with browser.session_transaction() as state:
        assert "_user_id" not in state


def test_duplicate_account_still_uses_existing_validation(app, csrf_token):
    browser = app.test_client()
    token = csrf_token(browser, "/register")
    with patch.object(app.extensions["mongo_db"].users, "insert_one", side_effect=DuplicateKeyError("duplicate")):
        response = browser.post("/register", data={
            "username": "New seller", "email": "new@example.test",
            "password": ACCOUNT["password"], "csrf_token": token,
        })
    assert response.status_code == 200
    assert b"An account with that email already exists" in response.data
    assert b"Temporarily unavailable" not in response.data


@pytest.mark.parametrize("during_iteration", (False, True))
def test_my_items_query_and_cursor_failures_return_503(app, seller, during_iteration):
    class UnavailableCursor:
        def sort(self, *args):
            return self

        def __iter__(self):
            raise AutoReconnect(FAILURE_DETAIL)

    options = {"side_effect": AutoReconnect(FAILURE_DETAIL)}
    if during_iteration:
        options = {"return_value": UnavailableCursor()}
    with patch.object(app.extensions["mongo_db"].items, "find", **options):
        response = seller.get("/my-items")
        page = assert_unavailable(response)
    assert b"No items" not in response.data
    recovered = seller.get(page.links["Try again"])
    assert recovered.status_code == 200
    assert b"Desk lamp" in recovered.data


@pytest.mark.parametrize("method", ("get", "post"))
def test_edit_lookup_failure_returns_503_without_changing_item(app, seller, method):
    items = app.extensions["mongo_db"].items
    before = items.find_one()
    with seller.session_transaction() as state:
        token = state["manage_csrf_token"]
    with patch.object(items, "find_one", side_effect=AutoReconnect(FAILURE_DETAIL)):
        response = getattr(seller, method)(f'/items/{before["_id"]}/edit', data={"csrf_token": token})
        assert_unavailable(response)
    assert items.find_one() == before


@pytest.mark.parametrize(("action", "operation", "status"), (
    ("edit", "update_one", "active"), ("sold", "update_one", "active"),
    ("relist", "update_one", "sold"), ("delete", "delete_one", "active"),
))
def test_management_write_failures_do_not_retry_or_destroy_the_session(app, seller, action, operation, status):
    items = app.extensions["mongo_db"].items
    items.update_one({}, {"$set": {"status": status}})
    before = items.find_one()
    with seller.session_transaction() as state:
        token = state["manage_csrf_token"]
        owner = state["_user_id"]
    with patch.object(items, operation, side_effect=AutoReconnect(FAILURE_DETAIL)) as write:
        response = seller.post(f'/items/{before["_id"]}/{action}', data={
            "csrf_token": token, "title": "Updated lamp", "description": "Still working.",
            "price": "15", "category": "Furniture", "condition": "Good", "image_url": "",
            "contact_info": ACCOUNT["email"],
        })
        page = assert_unavailable(response)
        assert write.call_count == 1
    assert b"Your last action may already have completed" in response.data
    assert "Try again" not in page.links
    assert page.links["Check My items"] == "/my-items"
    assert not page.forms
    assert items.find_one() == before
    with seller.session_transaction() as state:
        assert state["_user_id"] == owner
        assert state["manage_csrf_token"] == token


def test_uncertain_write_is_not_repeated_or_reported_as_success(app, seller):
    items = app.extensions["mongo_db"].items
    original_update = items.update_one
    item = items.find_one()
    with seller.session_transaction() as state:
        token = state["manage_csrf_token"]

    def update_then_disconnect(*args, **kwargs):
        original_update(*args, **kwargs)
        raise AutoReconnect(FAILURE_DETAIL)

    with patch.object(items, "update_one", side_effect=update_then_disconnect) as write:
        response = seller.post(f'/items/{item["_id"]}/sold', data={"csrf_token": token})
        page = assert_unavailable(response)
        assert write.call_count == 1
    assert items.find_one()["status"] == "sold"
    assert b"Your last action may already have completed" in response.data
    assert seller.get(page.links["Check My items"]).status_code == 200


def test_unrelated_programming_errors_are_not_disguised_as_outages(app, seller):
    with patch.object(app.extensions["mongo_db"].items, "find", side_effect=ValueError("programming error")):
        with pytest.raises(ValueError, match="programming error"):
            seller.get("/my-items")
