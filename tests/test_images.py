"""Product photos must survive saves and never bypass ownership or file checks."""

from io import BytesIO
from pathlib import Path

import mongomock
from PIL import Image
from pymongo.errors import AutoReconnect
from pymongo.results import UpdateResult
import pytest

import app as app_module
from app.images import IMAGE_KEY, MAX_IMAGE_BYTES


def photo_bytes(format="PNG", color="red", size=(24, 16), **kwargs):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format=format, **kwargs)
    return output.getvalue()


def attached(contents=None, filename="lamp.png"):
    return BytesIO(photo_bytes() if contents is None else contents), filename


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    mongo = mongomock.MongoClient(tz_aware=True)
    application = app_module.create_app({
        "TESTING": True, "SECRET_KEY": "image-test-only",
        "MONGODB_URI": "mongodb://localhost:27017", "MONGODB_DB": "test_images",
        "MONGO_CLIENT": mongo, "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    yield application
    mongo.close()


@pytest.fixture
def client(app, auth_post):
    browser = app.test_client()
    assert auth_post(browser, "/register", data={
        "username": "Photo Seller", "email": "photo@example.edu", "password": "password123",
    }).status_code == 302
    assert browser.get("/items/new").status_code == 200
    return browser


@pytest.fixture
def form(client):
    with client.session_transaction() as state:
        token = state["publish_csrf_token"]
    return {
        "title": "Photo lamp", "description": "A working desk lamp.", "price": "12.50",
        "category": "Furniture", "condition": "Good", "contact_info": "photo@example.edu",
        "image_url": "", "csrf_token": token,
    }


def stored_files(app):
    return list(Path(app.config["UPLOAD_FOLDER"]).glob("*"))


@pytest.fixture
def item(app, client, form):
    assert client.post("/items/new", data={**form, "image_file": attached()}).status_code == 302
    return app.extensions["mongo_db"].items.find_one({})


@pytest.fixture
def edit(client, item, form):
    assert client.get(f'/items/{item["_id"]}/edit').status_code == 200
    with client.session_transaction() as state:
        token = state["manage_csrf_token"]
    return {**form, "csrf_token": token}


@pytest.mark.parametrize("format,extension", [("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp")])
def test_upload_is_verified_normalized_and_shown_in_public_pages(app, client, form, format, extension):
    response = client.post("/items/new", data={
        **form, "image_file": attached(photo_bytes(format), f"../../same-name.{extension}"),
        "image_key": "forged-key",
    })
    assert response.status_code == 302
    document = app.extensions["mongo_db"].items.find_one({})
    assert IMAGE_KEY.fullmatch(document["image_key"])
    assert document["image_url"] == "/uploads/" + document["image_key"]
    assert len(stored_files(app)) == 1
    image = client.get(document["image_url"])
    assert image.status_code == 200
    assert image.mimetype == "image/jpeg"
    assert image.headers["X-Content-Type-Options"] == "nosniff"
    with Image.open(BytesIO(image.data)) as decoded:
        assert decoded.format == "JPEG"
    for path in (response.location, "/items", "/search?q=Photo+lamp"):
        assert document["image_url"].encode() in client.get(path).data


@pytest.mark.parametrize("contents,filename", [
    (b"<script>alert(1)</script>", "fake.jpg"),
    (b"", "empty.png"),
    (b"not an image", "fake.png"),
    (photo_bytes("GIF"), "animation.jpg"),
    (photo_bytes(), "photo.svg"),
    (photo_bytes(), "photo.html"),
])
def test_invalid_uploads_never_create_records_or_files(app, client, form, contents, filename):
    response = client.post("/items/new", data={**form, "image_file": attached(contents, filename)})
    assert response.status_code == 400
    assert b'href="#image_file"' in response.data
    assert b"Photo lamp" in response.data
    assert app.extensions["mongo_db"].items.count_documents({}) == 0
    assert stored_files(app) == []


def test_image_size_limit_is_checked_before_saving(app, client, form):
    response = client.post("/items/new", data={
        **form, "image_file": attached(b"x" * (MAX_IMAGE_BYTES + 1)),
    })
    assert response.status_code == 400
    assert b"5 MB or smaller" in response.data
    assert stored_files(app) == []


def test_request_size_limit_has_a_helpful_response(app, client, form):
    response = client.post("/items/new", data={
        **form, "image_file": attached(b"x" * (7 * 1024 * 1024)),
    })
    assert response.status_code == 413
    assert b"Photo too large" in response.data
    assert app.extensions["mongo_db"].items.count_documents({}) == 0
    assert stored_files(app) == []


def test_pixel_limit_and_multiple_files_are_rejected(app, client, form, monkeypatch):
    monkeypatch.setattr("app.images.MAX_IMAGE_PIXELS", 100)
    response = client.post("/items/new", data={**form, "image_file": attached()})
    assert response.status_code == 400
    assert b"Choose a smaller photo" in response.data
    response = client.post("/items/new", data={**form, "image_file": [attached(), attached()]})
    assert response.status_code == 400
    assert b"Choose only one" in response.data
    assert stored_files(app) == []


def test_other_validation_errors_do_not_leave_an_uploaded_file(app, client, form):
    response = client.post("/items/new", data={**form, "price": "0", "image_file": attached()})
    assert response.status_code == 400
    assert stored_files(app) == []
    assert app.extensions["mongo_db"].items.count_documents({}) == 0


def test_orientation_and_metadata_are_normalized(app, client, form):
    exif = Image.Exif()
    exif[274] = 6
    exif[271] = "private-camera-tag"
    original = photo_bytes("JPEG", size=(2000, 1000), exif=exif)
    response = client.post("/items/new", data={**form, "image_file": attached(original, "camera.jpg")})
    assert response.status_code == 302
    with Image.open(stored_files(app)[0]) as image:
        assert image.size == (800, 1600)
        assert not image.getexif()


@pytest.mark.parametrize("echo_local_url", [False, True])
def test_edit_without_a_new_photo_keeps_the_existing_file(app, client, item, edit, echo_local_url):
    response = client.post(f'/items/{item["_id"]}/edit', data={
        **edit, "title": "New title", "image_key": "forged-key",
        "image_url": item["image_url"] if echo_local_url else "",
    })
    assert response.status_code == 302
    current = app.extensions["mongo_db"].items.find_one({"_id": item["_id"]})
    assert current["image_url"] == item["image_url"]
    assert current["image_key"] == item["image_key"]
    assert len(stored_files(app)) == 1
    assert client.get(item["image_url"]).status_code == 200


def test_replacing_photo_removes_only_the_old_file_after_save(app, client, item, edit):
    response = client.post(f'/items/{item["_id"]}/edit', data={
        **edit, "image_file": attached(photo_bytes(color="blue")),
    })
    assert response.status_code == 302
    current = app.extensions["mongo_db"].items.find_one({"_id": item["_id"]})
    assert current["image_key"] != item["image_key"]
    assert current["owner_id"] == item["owner_id"]
    assert current["created_at"] == item["created_at"]
    assert len(stored_files(app)) == 1
    assert client.get(item["image_url"]).status_code == 404
    assert client.get(current["image_url"]).status_code == 200


def test_remove_photo_clears_the_file_and_reference(app, client, item, edit):
    assert client.post(f'/items/{item["_id"]}/edit', data={**edit, "remove_image": "1"}).status_code == 302
    current = app.extensions["mongo_db"].items.find_one({"_id": item["_id"]})
    assert current["image_url"] == current["image_key"] == ""
    assert stored_files(app) == []
    assert client.get(item["image_url"]).status_code == 404


def test_remove_and_replace_conflict_leaves_existing_photo_untouched(app, client, item, edit):
    response = client.post(f'/items/{item["_id"]}/edit', data={
        **edit, "remove_image": "1", "image_file": attached(),
    })
    assert response.status_code == 400
    assert app.extensions["mongo_db"].items.find_one({"_id": item["_id"]}) == item
    assert len(stored_files(app)) == 1


def test_sold_and_relisted_items_keep_the_photo(app, client, item, edit):
    for action, status in [("sold", "sold"), ("relist", "active")]:
        assert client.post(f'/items/{item["_id"]}/{action}', data={"csrf_token": edit["csrf_token"]}).status_code == 302
        current = app.extensions["mongo_db"].items.find_one({"_id": item["_id"]})
        assert current["status"] == status
        assert current["image_key"] == item["image_key"]
        assert client.get(item["image_url"]).status_code == 200
        assert len(stored_files(app)) == 1


@pytest.mark.parametrize("status", ["active", "sold"])
def test_hard_delete_removes_both_record_and_managed_photo(app, client, item, edit, status):
    db = app.extensions["mongo_db"]
    db.items.update_one({"_id": item["_id"]}, {"$set": {"status": status}})
    response = client.post(f'/items/{item["_id"]}/delete', data={"csrf_token": edit["csrf_token"]})
    assert response.status_code == 302
    assert db.items.find_one({"_id": item["_id"]}) is None
    assert stored_files(app) == []
    assert client.get(item["image_url"]).status_code == 404


def test_other_seller_cannot_replace_or_remove_a_photo(app, client, item, auth_post, form):
    other = app.test_client()
    auth_post(other, "/register", data={
        "username": "Other", "email": "other@example.edu", "password": "password123",
    })
    other.get("/my-items")
    with other.session_transaction() as state:
        token = state["manage_csrf_token"]
    assert other.post(f'/items/{item["_id"]}/edit', data={
        **form, "csrf_token": token, "image_file": attached(),
    }).status_code == 404
    assert other.post(f'/items/{item["_id"]}/delete', data={"csrf_token": token}).status_code == 404
    assert app.extensions["mongo_db"].items.find_one({"_id": item["_id"]}) == item
    assert len(stored_files(app)) == 1


def test_missing_csrf_and_anonymous_upload_cannot_write_files(app, client, form):
    assert client.post("/items/new", data={**form, "csrf_token": "", "image_file": attached()}).status_code == 400
    assert app.test_client().post("/items/new", data={**form, "image_file": attached()}).status_code == 302
    assert stored_files(app) == []


def test_external_urls_remain_compatible_and_can_replace_an_upload(app, client, item, edit):
    response = client.post(f'/items/{item["_id"]}/edit', data={**edit, "image_url": "https://example.com/lamp.jpg"})
    assert response.status_code == 302
    current = app.extensions["mongo_db"].items.find_one({"_id": item["_id"]})
    assert current["image_url"] == "https://example.com/lamp.jpg"
    assert current["image_key"] == ""
    assert stored_files(app) == []
    assert client.post(f'/items/{item["_id"]}/edit', data={**edit, "image_file": attached()}).status_code == 302
    assert len(stored_files(app)) == 1


def test_local_path_in_a_post_is_not_a_trusted_upload(app, client, form):
    assert client.post("/items/new", data={**form, "image_url": "/uploads/" + "a" * 32 + ".jpg"}).status_code == 400
    assert app.extensions["mongo_db"].items.count_documents({}) == 0


def test_failed_insert_cleans_unreferenced_upload(app, client, form, monkeypatch):
    def fail_insert(*args, **kwargs):
        raise AutoReconnect("before insert")
    monkeypatch.setattr(app.extensions["mongo_db"].items, "insert_one", fail_insert)
    response = client.post("/items/new", data={**form, "image_file": attached()})
    assert response.status_code == 503
    assert b"Photo lamp" in response.data
    assert stored_files(app) == []


def test_lost_insert_acknowledgement_does_not_delete_committed_photo(app, client, form, monkeypatch):
    collection = app.extensions["mongo_db"].items
    original = collection.insert_one
    def insert_then_fail(document):
        original(document)
        raise AutoReconnect("lost acknowledgement")
    monkeypatch.setattr(collection, "insert_one", insert_then_fail)
    response = client.post("/items/new", data={**form, "image_file": attached()})
    assert response.status_code == 503
    document = collection.find_one({})
    assert len(stored_files(app)) == 1
    assert client.get(document["image_url"]).status_code == 200


def test_failed_edit_keeps_old_photo_and_discards_new_file(app, client, item, edit, monkeypatch):
    def fail_update(*args, **kwargs):
        raise AutoReconnect("before update")
    monkeypatch.setattr(app.extensions["mongo_db"].items, "update_one", fail_update)
    response = client.post(f'/items/{item["_id"]}/edit', data={**edit, "image_file": attached()})
    assert response.status_code == 503
    assert app.extensions["mongo_db"].items.find_one({"_id": item["_id"]}) == item
    assert len(stored_files(app)) == 1
    assert client.get(item["image_url"]).status_code == 200


def test_conflicting_edit_does_not_leak_a_new_file(app, client, item, edit, monkeypatch):
    monkeypatch.setattr(app.extensions["mongo_db"].items, "update_one", lambda *a, **k: UpdateResult({"n": 0}, True))
    response = client.post(f'/items/{item["_id"]}/edit', data={**edit, "image_file": attached()})
    assert response.status_code == 409
    assert len(stored_files(app)) == 1
    assert client.get(item["image_url"]).status_code == 200


def test_shared_photo_is_removed_only_after_the_last_reference(app, client, item, edit):
    db = app.extensions["mongo_db"]
    copy = {key: value for key, value in item.items() if key != "_id"}
    other_id = db.items.insert_one(copy).inserted_id
    assert client.post(f'/items/{item["_id"]}/delete', data={"csrf_token": edit["csrf_token"]}).status_code == 302
    assert len(stored_files(app)) == 1
    assert client.post(f'/items/{other_id}/delete', data={"csrf_token": edit["csrf_token"]}).status_code == 302
    assert stored_files(app) == []


def test_ajax_saves_return_a_destination_without_consuming_success_flash(app, client, form):
    response = client.post("/items/new", data={**form, "image_file": attached()},
                           headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200
    destination = response.get_json()["redirect_url"]
    assert b"Your item has been posted." in client.get(destination).data


def test_upload_form_supports_no_javascript_and_keeps_current_preview(client, item):
    for path in ("/items/new", f'/items/{item["_id"]}/edit'):
        html = client.get(path).get_data(as_text=True)
        assert 'enctype="multipart/form-data"' in html
        assert 'name="image_file" type="file"' in html
        assert "item-form.js" in html
        assert "Use an image link instead" in html
    assert item["image_url"].encode() in client.get(f'/items/{item["_id"]}/edit').data


def test_lost_edit_acknowledgement_keeps_the_committed_photo(app, client, item, edit, monkeypatch):
    collection = app.extensions["mongo_db"].items
    original_update = collection.update_one

    def update_then_fail(*args, **kwargs):
        original_update(*args, **kwargs)
        raise AutoReconnect("lost edit acknowledgement")

    monkeypatch.setattr(collection, "update_one", update_then_fail)
    response = client.post(f'/items/{item["_id"]}/edit', data={
        **edit, "image_file": attached(photo_bytes(color="blue")),
    })
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    current = collection.find_one({"_id": item["_id"]})
    assert current["image_key"] != item["image_key"]
    assert len(stored_files(app)) == 1
    assert client.get(current["image_url"]).status_code == 200
    assert client.get(item["image_url"]).status_code == 404
