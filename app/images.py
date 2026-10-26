"""Validated product photos stored locally, with server-owned filenames."""

from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4
import warnings

from flask import abort, current_app, request, send_from_directory, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from pymongo.errors import PyMongoError

from app.db import get_db

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
IMAGE_KEY = re.compile(r"[a-f0-9]{32}\.(?:jpg|png)\Z")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def read_photo(upload=None):
    """Decode and normalize one upload in memory; never trust its MIME type."""
    if upload is None:
        # Accept both cached main forms and the enhanced photo picker.
        files = [photo for field in ("image_file", "image")
                 for photo in request.files.getlist(field) if photo.filename]
    else:
        files = [upload] if upload.filename else []
    if len(files) > 1:
        raise ValueError("Choose only one product photo.")
    if not files:
        return None
    photo = files[0]
    if photo.filename.rsplit(".", 1)[-1].lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Choose a JPG, PNG, or WebP photo.")
    contents = photo.stream.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise ValueError("Photo must be 5 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(contents)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Choose a JPG, PNG, or WebP photo.")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValueError("This photo is too large. Choose a smaller photo.")
                source.verify()
            with Image.open(BytesIO(contents)) as source:
                image = ImageOps.exif_transpose(source)
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                rgba = image.convert("RGBA")
                normalized = Image.new("RGB", rgba.size, "white")
                normalized.paste(rgba, mask=rgba.getchannel("A"))
                output = BytesIO()
                normalized.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("This file could not be read as a photo. Choose another image.") from error


def managed_photo_key(document):
    """Recognize both current keys and main's older server-owned PNG URLs."""
    document = document or {}
    key = document.get("image_key")
    if isinstance(key, str) and IMAGE_KEY.fullmatch(key):
        return key
    address = document.get("image_url", "")
    if isinstance(address, str) and address.startswith("/uploads/"):
        key = address.removeprefix("/uploads/")
        if IMAGE_KEY.fullmatch(key):
            return key
    return ""


def photo_input(form_values, document=None):
    """Return normalized upload bytes and field errors without writing files."""
    errors = {}
    try:
        photo = read_photo()
    except ValueError as error:
        photo = None
        errors["image_file"] = str(error)
    remove = request.form.get("remove_image") == "1"
    if photo is not None and remove:
        errors["image_file"] = "Choose a new photo or remove the current photo, not both."
    if photo is not None or remove:
        form_values["image_url"] = ""
    elif document and managed_photo_key(document) and form_values["image_url"] == document.get("image_url"):
        # Older clients may echo the current local URL; it is not a new external link.
        form_values["image_url"] = ""
    return photo, remove, errors


def image_fields(form_values, photo, remove=False, document=None):
    """Persist a verified photo only after all form fields have passed validation."""
    if photo is not None:
        folder = Path(current_app.config["UPLOAD_FOLDER"])
        folder.mkdir(parents=True, exist_ok=True)
        key = uuid4().hex + ".jpg"
        path = folder / key
        created = False
        try:
            with path.open("xb") as output:
                created = True
                output.write(photo)
        except OSError:
            if created:
                path.unlink(missing_ok=True)
            raise
        return {"image_key": key, "image_url": url_for("uploads.image", filename=key)}
    if remove:
        return {"image_key": "", "image_url": ""}
    if form_values["image_url"]:
        return {"image_key": "", "image_url": form_values["image_url"]}
    return {
        "image_key": managed_photo_key(document),
        "image_url": (document or {}).get("image_url", ""),
    }


def discard_unreferenced_photo(key):
    """Clean up only managed files whose absence from MongoDB is confirmed."""
    if not isinstance(key, str) or not IMAGE_KEY.fullmatch(key):
        return
    try:
        if get_db().items.find_one({"$or": [
            {"image_key": key}, {"image_url": "/uploads/" + key},
        ]}) is not None:
            return
    except PyMongoError:
        current_app.logger.warning("Kept product photo because its database state is unknown.")
        return
    try:
        (Path(current_app.config["UPLOAD_FOLDER"]) / key).unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception("Could not clean up an unreferenced product photo.")


def photo(filename):
    if not IMAGE_KEY.fullmatch(filename):
        abort(404)
    try:
        item = get_db().items.find_one({
            "$or": [{"image_key": filename}, {"image_url": "/uploads/" + filename}],
            "status": {"$in": ["active", "sold"]},
        })
    except PyMongoError:
        abort(503)
    if item is None:
        abort(404)
    response = send_from_directory(current_app.config["UPLOAD_FOLDER"], filename,
                                   mimetype="image/png" if filename.endswith(".png") else "image/jpeg",
                                   max_age=3600)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
