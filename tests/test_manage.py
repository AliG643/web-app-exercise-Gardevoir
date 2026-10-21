"""Seller management stays compatible with publishing and public listings."""

from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser

import mongomock
import pytest

import app as app_module


class SelectedOptions(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.field = None
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.field = attrs.get("name")
        elif tag == "option" and self.field and "selected" in attrs:
            self.values[self.field] = attrs.get("value")

    def handle_endtag(self, tag):
        if tag == "select":
            self.field = None


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    mongo = mongomock.MongoClient(tz_aware=True)
    application = app_module.create_app({
        "TESTING": True,
        "SECRET_KEY": "manage-test-only",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "test_manage",
        "MONGO_CLIENT": mongo,
    })
    yield application
    mongo.close()


@pytest.fixture
def seller(app, auth_post):
    browser = app.test_client()
    assert auth_post(browser, "/register", data={
        "username": "Seller One",
        "email": "seller@example.edu",
        "password": "password123",
    }).status_code == 302
    return browser


@pytest.fixture
def item(app, seller):
    db = app.extensions["mongo_db"]
    owner = db.users.find_one({"email": "seller@example.edu"})
    now = datetime.now(timezone.utc)
    document = {
        "title": "Desk lamp",
        "description": "A working desk lamp.",
        "price": 12.5,
        "category": "Furniture",
        "condition": "Good",
        "image_url": "",
        "contact_info": "seller@example.edu",
        "owner_id": owner["_id"],
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    document["_id"] = db.items.insert_one(document).inserted_id
    return db.items.find_one({"_id": document["_id"]})


@pytest.fixture
def edit_form(seller, item):
    assert seller.get(f'/items/{item["_id"]}/edit').status_code == 200
    with seller.session_transaction() as state:
        token = state["manage_csrf_token"]
    return {
        "csrf_token": token,
        "title": "Updated desk lamp",
        "description": "A working desk lamp with a new bulb.",
        "price": "18.75",
        "category": "Furniture",
        "condition": "Good",
        "image_url": "",
        "contact_info": "seller@example.edu",
    }


@pytest.mark.parametrize("image_url", [
    "https://example.com:bad/lamp.jpg",
    "https://example.com/a b.jpg",
])
def test_edit_rejects_invalid_image_url_and_keeps_input(
    app, seller, item, edit_form, image_url,
):
    edit_form["image_url"] = image_url
    response = seller.post(f'/items/{item["_id"]}/edit', data=edit_form)
    assert response.status_code == 400
    assert f'value="{escape(image_url, quote=True)}"' in response.get_data(as_text=True)
    assert app.extensions["mongo_db"].items.find_one({"_id": item["_id"]}) == item


@pytest.mark.parametrize("field,value", [
    ("category", "Unknown category"),
    ("condition", "Unknown condition"),
])
def test_edit_validation_preserves_invalid_selection_and_links_to_field(
    app, seller, item, edit_form, field, value,
):
    edit_form[field] = value
    response = seller.post(f'/items/{item["_id"]}/edit', data=edit_form)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert SelectedOptions(html).values.get(field) == value
    assert f'href="#{field}"' in html
    assert app.extensions["mongo_db"].items.find_one({"_id": item["_id"]}) == item


@pytest.mark.parametrize("action", ["edit", "delete", "sold"])
def test_unicode_csrf_is_rejected_without_changing_the_item(
    app, seller, item, edit_form, action,
):
    edit_form["csrf_token"] = "无效令牌"
    response = seller.post(f'/items/{item["_id"]}/{action}', data=edit_form)
    assert response.status_code == 400
    assert app.extensions["mongo_db"].items.find_one({"_id": item["_id"]}) == item


def test_publish_edit_sold_delete_lifecycle_preserves_ownership(app, seller, auth_post):
    db = app.extensions["mongo_db"]
    assert seller.get("/items/new").status_code == 200
    with seller.session_transaction() as state:
        publish_token = state["publish_csrf_token"]
    values = {
        "title": "Desk lamp",
        "description": "A working desk lamp.",
        "price": "12.50",
        "category": "Furniture",
        "condition": "Good",
        "image_url": "",
        "contact_info": "seller@example.edu",
    }
    response = seller.post("/items/new", data={**values, "csrf_token": publish_token})
    assert response.status_code == 302
    item = db.items.find_one({})
    item_id = str(item["_id"])

    other = app.test_client()
    assert auth_post(other, "/register", data={
        "username": "Seller Two",
        "email": "other@example.edu",
        "password": "password123",
    }).status_code == 302
    assert other.get("/my-items").status_code == 200
    with other.session_transaction() as state:
        other_token = state["manage_csrf_token"]
    assert b"Desk lamp" not in other.get("/my-items").data
    assert other.get(f"/items/{item_id}/edit").status_code == 404
    for action in ("edit", "sold", "delete"):
        assert other.post(f"/items/{item_id}/{action}", data={
            **values, "csrf_token": other_token,
        }).status_code == 404
    assert db.items.find_one({"_id": item["_id"]}) == item

    assert seller.get(f"/items/{item_id}/edit").status_code == 200
    with seller.session_transaction() as state:
        token = state["manage_csrf_token"]
    other_owner = db.users.find_one({"email": "other@example.edu"})["_id"]
    response = seller.post(f"/items/{item_id}/edit", data={
        **values,
        "title": "Updated desk lamp",
        "price": "18.75",
        "owner_id": str(other_owner),
        "status": "sold",
        "created_at": "2000-01-01",
        "csrf_token": token,
    })
    assert response.status_code == 302
    updated = db.items.find_one({"_id": item["_id"]})
    assert updated["price"] == 18.75
    assert updated["owner_id"] == item["owner_id"]
    assert updated["status"] == "active"
    assert updated["created_at"] == item["created_at"]
    assert b"Updated desk lamp" in seller.get(f"/items/{item_id}").data
    assert f'href="/items/{item_id}"'.encode() in seller.get("/search?q=Updated+desk+lamp").data

    assert seller.post(f"/items/{item_id}/sold", data={"csrf_token": token}).status_code == 302
    for path in ("/items", "/search?q=Updated+desk+lamp"):
        assert f'href="/items/{item_id}"'.encode() not in seller.get(path).data
    assert seller.get(f"/items/{item_id}").status_code == 404
    mine = seller.get("/my-items")
    assert b"Updated desk lamp" in mine.data and b"Sold" in mine.data

    assert seller.post(f"/items/{item_id}/delete", data={"csrf_token": token}).status_code == 302
    assert db.items.find_one({"_id": item["_id"]}) is None
    assert b"Updated desk lamp" not in seller.get("/my-items").data
    assert seller.get(f"/items/{item_id}").status_code == 404
    assert seller.get(f"/items/{item_id}/edit").status_code == 404
