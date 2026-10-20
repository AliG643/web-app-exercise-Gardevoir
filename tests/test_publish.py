from datetime import datetime, timezone

import mongomock
import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect

import app as app_module


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    mongo = mongomock.MongoClient(tz_aware=True)

    application = app_module.create_app({
        "TESTING": True,
        "SECRET_KEY": "publish-test-secret",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "test_publish",
        "MONGO_CLIENT": mongo,
    })

    yield application
    mongo.close()


@pytest.fixture
def client(app):
    browser = app.test_client()

    response = browser.post("/register", data={
        "username": "Test Seller",
        "email": "seller@example.edu",
        "password": "password123",
    })

    assert response.status_code == 302
    assert browser.get("/items/new").status_code == 200

    return browser


@pytest.fixture
def form(client):
    with client.session_transaction() as session:
        token = session["publish_csrf_token"]

    return {
        "csrf_token": token,
        "title": "Test lamp",
        "description": "A working desk lamp.",
        "price": "12.50",
        "category": "Furniture",
        "condition": "Good",
        "image_url": "",
        "contact_info": "seller@example.edu",
    }


@pytest.mark.parametrize("method", ["get", "post"])
def test_publishing_requires_login(app, method):
    browser = app.test_client()
    response = getattr(browser, method)("/items/new")

    assert response.status_code == 302
    assert "/login" in response.location
    assert app.extensions["mongo_db"].items.count_documents({}) == 0


def test_form_contains_csrf_token(client, form):
    response = client.get("/items/new")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="csrf_token"' in html
    assert form["csrf_token"] in html


def test_valid_post_saves_item_and_opens_detail(app, client, form):
    fake_owner = ObjectId()

    form.update({
        "title": "  Test lamp  ",
        "owner_id": str(fake_owner),
        "status": "sold",
        "created_at": "2000-01-01",
        "updated_at": "2000-01-01",
    })

    response = client.post("/items/new", data=form)

    db = app.extensions["mongo_db"]
    item = db.items.find_one({})
    seller = db.users.find_one({"email": "seller@example.edu"})

    assert response.status_code == 302
    assert db.items.count_documents({}) == 1

    assert item["title"] == "Test lamp"
    assert item["description"] == form["description"]
    assert item["price"] == 12.5
    assert isinstance(item["price"], float)
    assert item["category"] == "Furniture"
    assert item["condition"] == "Good"
    assert item["image_url"] == ""
    assert item["contact_info"] == form["contact_info"]

    assert item["owner_id"] == seller["_id"]
    assert item["owner_id"] != fake_owner
    assert item["status"] == "active"

    assert isinstance(item["created_at"], datetime)
    assert item["created_at"].utcoffset() == timezone.utc.utcoffset(None)
    assert item["created_at"] == item["updated_at"]

    assert response.location == f'/items/{item["_id"]}'

    detail = client.get(response.location)
    assert detail.status_code == 200
    assert b"Test lamp" in detail.data


@pytest.mark.parametrize("price", ["", "0", "-1", "abc", "nan", "inf"])
def test_invalid_price_keeps_values_without_saving(app, client, form, price):
    form["price"] = price

    response = client.post("/items/new", data=form)

    assert response.status_code == 400
    assert b"Please enter a price greater than zero." in response.data
    assert b"Test lamp" in response.data
    assert b"A working desk lamp." in response.data
    assert app.extensions["mongo_db"].items.count_documents({}) == 0


@pytest.mark.parametrize("field,value", [
    ("title", "   "),
    ("title", "x" * 121),
    ("description", ""),
    ("description", "x" * 2001),
    ("category", "Invalid category"),
    ("condition", "Invalid condition"),
    ("image_url", "javascript:alert(1)"),
    ("image_url", "https://example.com:bad/lamp.jpg"),
    ("image_url", "https://example.com/a b.jpg"),
    ("image_url", "https://example.com/" + "x" * 2048),
    ("contact_info", "x" * 201),
])
def test_invalid_fields_are_not_saved(app, client, form, field, value):
    form[field] = value

    response = client.post("/items/new", data=form)

    assert response.status_code == 400
    assert b"Please correct the following fields:" in response.data
    assert app.extensions["mongo_db"].items.count_documents({}) == 0


@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_missing_or_wrong_csrf_is_rejected(app, client, form, token):
    if token is None:
        form.pop("csrf_token")
    else:
        form["csrf_token"] = token

    response = client.post("/items/new", data=form)

    assert response.status_code == 400
    assert app.extensions["mongo_db"].items.count_documents({}) == 0


def test_database_error_keeps_form_values(app, client, form, monkeypatch):
    collection = app.extensions["mongo_db"].items

    def fail_insert(document):
        raise AutoReconnect("Test connection failure")

    monkeypatch.setattr(collection, "insert_one", fail_insert)

    response = client.post("/items/new", data=form)

    assert response.status_code == 503
    assert b"We could not confirm your post." in response.data
    assert b"Test lamp" in response.data
    assert b"A working desk lamp." in response.data
    assert collection.count_documents({}) == 0