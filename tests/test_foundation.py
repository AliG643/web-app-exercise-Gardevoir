from datetime import datetime, timezone

from bson import ObjectId
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

    with app.app_context():
        now = datetime.now(timezone.utc)

        result = get_db().items.insert_one({
            "title": "Test lamp",
            "description": "A working desk lamp.",
            "price": 12.0,
            "category": "Electronics",
            "condition": "Good",
            "image_url": "",
            "contact_info": "seller@example.edu",
            "owner_id": ObjectId(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        })

        item_id = str(result.inserted_id)

    for path in (
        "/items",
        f"/items/{item_id}",
        "/search?q=lamp",
    ):
        assert browser.get(path).status_code == 200

    assert browser.get("/items/example").status_code == 404
    assert browser.get(f"/items/{ObjectId()}").status_code == 404

    for path in (
        "/items/new",
        "/my-items",
        f"/items/{item_id}/edit",
    ):
        response = browser.get(path)
        assert response.status_code == 302
        assert "/login" in response.location

    assert parse_object_id("bad") is None
    assert parse_object_id(None) is None


def test_registration_login_and_current_owner(app):
    browser = app.test_client()
    response = browser.post(
        "/register",
        data={
            "username": "Campus Seller",
            "email": "SELLER@example.edu",
            "password": "password123",
        },
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

    response = browser.post(
        "/login",
        data={
            "email": "seller@example.edu",
            "password": "password123",
        },
    )
    assert response.status_code == 302
    assert browser.get("/my-items").status_code == 200


def test_login_returns_to_requested_page_without_external_redirects(app):
    browser = app.test_client()
    browser.post(
        "/register",
        data={
            "username": "Campus Seller",
            "email": "seller@example.edu",
            "password": "password123",
        },
    )
    browser.post("/logout")

    login_url = browser.get("/my-items").location
    assert login_url.startswith("/login?next=")
    assert browser.get(login_url).status_code == 200

    response = browser.post(
        login_url,
        data={
            "email": "seller@example.edu",
            "password": "password123",
        },
    )
    assert response.location == "/my-items"

    browser.post("/logout")

    for target in ("https://example.com", "//example.com", "/\\example.com"):
        response = browser.post(
            "/login",
            data={
                "email": "seller@example.edu",
                "password": "password123",
                "next": target,
            },
        )
        assert response.location == "/items"
        browser.post("/logout")


def test_registration_returns_to_page_requested_before_login(app):
    browser = app.test_client()

    login_url = browser.get("/items/new").location
    login_page = browser.get(login_url)
    assert b'href="/register?next=/items/new"' in login_page.data

    register_page = browser.get("/register?next=/items/new")
    assert b'name="next" value="/items/new"' in register_page.data
    assert b'href="/login?next=/items/new"' in register_page.data

    response = browser.post(
        "/register",
        data={
            "username": "New Seller",
            "email": "new-seller@example.edu",
            "password": "password123",
            "next": "/items/new",
        },
    )
    assert response.location == "/items/new"
    assert browser.get(response.location).status_code == 200


@pytest.mark.parametrize(
    "target",
    ("https://example.com", "//example.com", "/\\example.com"),
)
def test_registration_rejects_external_redirects(app, target):
    browser = app.test_client()

    response = browser.post(
        "/register",
        data={
            "username": "New Seller",
            "email": "new-seller@example.edu",
            "password": "password123",
            "next": target,
        },
    )
    assert response.location == "/items"


def test_db_commands_create_indexes_and_seed_items(app):
    runner = app.test_cli_runner()

    assert runner.invoke(args=["db-init"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 0

    with app.app_context():
        assert get_db().items.count_documents({"status": "active"}) == 3
        assert get_db().users.index_information()["email_1"]["unique"]


def test_my_items_shows_only_current_sellers_active_and_sold_items(app):
    browser = app.test_client()

    browser.post("/register", data={
        "username": "Seller One",
        "email": "one@example.edu",
        "password": "password123",
    })
    browser.post("/logout")

    browser.post("/register", data={
        "username": "Seller Two",
        "email": "two@example.edu",
        "password": "password123",
    })
    browser.post("/logout")

    with app.app_context():
        db = get_db()
        first = db.users.find_one({"email": "one@example.edu"})
        second = db.users.find_one({"email": "two@example.edu"})

        db.items.insert_many([
            {
                "title": "My active item",
                "price": 10,
                "status": "active",
                "owner_id": first["_id"],
            },
            {
                "title": "My sold item",
                "price": 20,
                "status": "sold",
                "owner_id": first["_id"],
            },
            {
                "title": "My deleted item",
                "price": 30,
                "status": "deleted",
                "owner_id": first["_id"],
            },
            {
                "title": "Someone else's item",
                "price": 40,
                "status": "active",
                "owner_id": second["_id"],
            },
        ])

    browser.post("/login", data={
        "email": "one@example.edu",
        "password": "password123",
    })
    page = browser.get("/my-items")

    assert page.status_code == 200
    assert b"My active item" in page.data
    assert b"My sold item" in page.data
    assert b"My deleted item" not in page.data
    assert b"Someone else's item" not in page.data


def test_mark_sold_only_changes_owners_active_item(app):
    browser = app.test_client()

    browser.post("/register", data={
        "username": "Seller One",
        "email": "one@example.edu",
        "password": "password123",
    })

    with app.app_context():
        db = get_db()
        owner_id = db.users.find_one({"email": "one@example.edu"})["_id"]

        other_owner_id = db.users.insert_one({
            "username": "Seller Two",
            "email": "two@example.edu",
            "password_hash": "unused",
        }).inserted_id

        own_item_id = db.items.insert_one({
            "title": "My lamp",
            "price": 10,
            "status": "active",
            "owner_id": owner_id,
        }).inserted_id

        other_item_id = db.items.insert_one({
            "title": "Other lamp",
            "price": 20,
            "status": "active",
            "owner_id": other_owner_id,
        }).inserted_id

    assert browser.post(f"/items/{own_item_id}/sold").status_code == 400

    page = browser.get("/my-items")
    assert page.status_code == 200

    with browser.session_transaction() as session:
        token = session["manage_csrf_token"]

    data = {"csrf_token": token}

    assert browser.post(
        f"/items/{other_item_id}/sold", data=data
    ).status_code == 404
    assert browser.post(
        f"/items/{own_item_id}/sold", data=data
    ).status_code == 302
    assert browser.post(
        f"/items/{own_item_id}/sold", data=data
    ).status_code == 404

    with app.app_context():
        assert db.items.find_one({"_id": own_item_id})["status"] == "sold"
        assert db.items.find_one({"_id": other_item_id})["status"] == "active"


def test_edit_item_only_changes_owners_item(app):
    browser = app.test_client()

    browser.post("/register", data={
        "username": "Seller One",
        "email": "one@example.edu",
        "password": "password123",
    })

    with app.app_context():
        db = get_db()
        owner_id = db.users.find_one({"email": "one@example.edu"})["_id"]

        other_owner_id = db.users.insert_one({
            "username": "Seller Two",
            "email": "two@example.edu",
            "password_hash": "unused",
        }).inserted_id

        own_item_id = db.items.insert_one({
            "title": "My lamp",
            "description": "Old description",
            "price": 10,
            "category": "Electronics",
            "condition": "Good",
            "status": "active",
            "owner_id": owner_id,
        }).inserted_id

        other_item_id = db.items.insert_one({
            "title": "Other lamp",
            "description": "Other description",
            "price": 20,
            "category": "Electronics",
            "condition": "Good",
            "status": "active",
            "owner_id": other_owner_id,
        }).inserted_id

    assert browser.get(f"/items/{other_item_id}/edit").status_code == 404
    assert browser.get(f"/items/{own_item_id}/edit").status_code == 200

    with browser.session_transaction() as session:
        token = session["manage_csrf_token"]

    changes = {
        "csrf_token": token,
        "title": "Updated lamp",
        "description": "Updated description",
        "price": "15.50",
        "category": "Electronics",
        "condition": "Like New",
        "image_url": "",
        "contact_info": "",
        "owner_id": str(other_owner_id),
        "status": "sold",
    }

    assert browser.post(
        f"/items/{other_item_id}/edit", data=changes
    ).status_code == 404
    assert browser.post(
        f"/items/{own_item_id}/edit", data=changes
    ).status_code == 302

    with app.app_context():
        own_item = db.items.find_one({"_id": own_item_id})
        other_item = db.items.find_one({"_id": other_item_id})

        assert own_item["title"] == "Updated lamp"
        assert own_item["price"] == 15.50
        assert own_item["owner_id"] == owner_id
        assert own_item["status"] == "active"
        assert other_item["title"] == "Other lamp"
        assert other_item["price"] == 20


@pytest.mark.parametrize("status", ("active", "sold"))
def test_delete_item_permanently_removes_only_owners_item(app, status):
    browser = app.test_client()

    browser.post("/register", data={
        "username": "Seller One",
        "email": "one@example.edu",
        "password": "password123",
    })

    with app.app_context():
        db = get_db()
        owner_id = db.users.find_one({"email": "one@example.edu"})["_id"]

        other_owner_id = db.users.insert_one({
            "username": "Seller Two",
            "email": "two@example.edu",
            "password_hash": "unused",
        }).inserted_id

        own_item_id = db.items.insert_one({
            "title": "My lamp",
            "price": 10,
            "status": status,
            "owner_id": owner_id,
        }).inserted_id

        other_item_id = db.items.insert_one({
            "title": "Other lamp",
            "price": 20,
            "status": "active",
            "owner_id": other_owner_id,
        }).inserted_id

    assert browser.post(f"/items/{own_item_id}/delete").status_code == 400
    assert browser.get("/my-items").status_code == 200

    with browser.session_transaction() as session:
        token = session["manage_csrf_token"]

    data = {"csrf_token": token}

    assert browser.post(
        f"/items/{other_item_id}/delete", data=data
    ).status_code == 404

    for invalid_item_id in ("invalid", str(ObjectId())):
        assert browser.post(
            f"/items/{invalid_item_id}/delete", data=data
        ).status_code == 404

    with app.app_context():
        assert db.items.count_documents({}) == 2

    assert browser.post(
        f"/items/{own_item_id}/delete", data=data
    ).status_code == 302
    assert browser.post(
        f"/items/{own_item_id}/delete", data=data
    ).status_code == 404
    assert b"My lamp" not in browser.get("/my-items").data
    assert b"My lamp" not in browser.get("/items").data
    assert b"My lamp" not in browser.get("/search?q=lamp").data
    assert browser.get(f"/items/{own_item_id}").status_code == 404
    assert browser.get(f"/items/{own_item_id}/edit").status_code == 404

    with app.app_context():
        assert db.items.find_one({"_id": own_item_id}) is None
        assert db.items.count_documents({}) == 1
        assert db.items.find_one({"_id": other_item_id})["status"] == "active"
