"""Marketplace upload API shared by existing main clients and the new picker.

Validation and storage live in app.images; register only this blueprint so
JPEG and legacy PNG URLs use the same reference and access checks.
"""

from flask import Blueprint

from app.images import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS,
    image_fields,
    photo,
    read_photo,
)

uploads = Blueprint("uploads", __name__)


class ImageUploadError(ValueError):
    """An uploaded file is not an acceptable product image."""


def save_item_image(upload, existing_url=""):
    """Keep the main uploader's callable API and use shared verified storage."""
    if upload is None or not upload.filename:
        return existing_url
    try:
        normalized = read_photo(upload)
    except ValueError as error:
        raise ImageUploadError(str(error)) from error
    return image_fields({}, normalized)["image_url"]


@uploads.get("/uploads/<filename>")
def image(filename):
    return photo(filename)
