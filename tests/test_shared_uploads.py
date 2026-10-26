"""Shared photo storage must work when the same database is used in another checkout."""
from io import BytesIO

import mongomock
from PIL import Image

import app as app_module


def test_existing_photo_uses_upload_folder_from_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    folder = tmp_path / "shared-photos"
    folder.mkdir()
    monkeypatch.setenv("UPLOAD_FOLDER", str(folder))
    key = "a" * 32 + ".jpg"
    output = BytesIO()
    Image.new("RGB", (24, 16), "red").save(output, format="JPEG")
    (folder / key).write_bytes(output.getvalue())
    mongo = mongomock.MongoClient()
    mongo.shared_uploads.items.insert_one({"image_key": key, "status": "active"})
    try:
        for _ in range(2):
            application = app_module.create_app({
                "TESTING": True, "SECRET_KEY": "shared-photo-test-only",
                "MONGODB_URI": "mongodb://localhost", "MONGODB_DB": "shared_uploads",
                "MONGO_CLIENT": mongo,
            })
            response = application.test_client().get("/uploads/" + key)
            assert response.status_code == 200
            assert response.mimetype == "image/jpeg"
            assert response.data == output.getvalue()
            assert application.config["UPLOAD_FOLDER"] == str(folder)
    finally:
        mongo.close()
