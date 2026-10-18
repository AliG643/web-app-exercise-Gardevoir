import mongomock
import pytest

from app import create_app
from app.db import get_db, parse_object_id


@pytest.fixture
def app():
    client = mongomock.MongoClient()
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "MONGODB_URI": "mongodb://localhost:27017",
            "MONGODB_DB": "test_gardevoir",
            "MONGO_CLIENT": client,
        }
    )
    yield app
    client.close()


def test_public_pages_and_owner_routes(app):
    browser = app.test_client()
    for path in ("/items", "/items/example", "/search?q=lamp"):
        assert browser.get(path).status_code == 200
    for path in ("/items/new", "/my-items", "/items/example/edit"):
        response = browser.get(path)
        assert response.status_code == 302
        assert "/login" in response.location
    assert parse_object_id("bad") is None
    assert parse_object_id(None) is None


def test_registration_login_and_current_owner(app):
    browser = app.test_client()
    response = browser.post(
        "/register",
        data={"username": "Campus Seller", "email": "SELLER@example.edu", "password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"My items" in response.data
    with app.app_context():
        user = get_db().users.find_one({"email": "seller@example.edu"})
        assert user is not None
        assert user["password_hash"] != "password123"
    assert browser.get("/my-items").status_code == 200
    assert browser.post("/logout").status_code == 302
    assert browser.get("/my-items").status_code == 302
    assert browser.post("/login", data={"email": "seller@example.edu", "password": "password123"}).status_code == 302
    assert browser.get("/my-items").status_code == 200


def test_login_returns_to_requested_page_without_external_redirects(app):
    browser = app.test_client()
    browser.post(
        "/register",
        data={"username": "Campus Seller", "email": "seller@example.edu", "password": "password123"},
    )
    browser.post("/logout")

    login_url = browser.get("/my-items").location
    assert login_url.startswith("/login?next=")
    assert browser.get(login_url).status_code == 200
    response = browser.post(login_url, data={"email": "seller@example.edu", "password": "password123"})
    assert response.location == "/my-items"

    browser.post("/logout")
    for target in ("https://example.com", "//example.com", "/\\example.com"):
        response = browser.post(
            "/login",
            data={"email": "seller@example.edu", "password": "password123", "next": target},
        )
        assert response.location == "/items"
        browser.post("/logout")


def test_db_commands_create_indexes_and_seed_items(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["db-init"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    with app.app_context():
        assert get_db().items.count_documents({"status": "active"}) == 3
        assert get_db().users.index_information()["email_1"]["unique"]
