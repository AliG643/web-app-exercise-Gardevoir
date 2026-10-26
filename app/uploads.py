<<<<<<< HEAD
import re
from pathlib import Path
from uuid import uuid4
=======
"""Marketplace upload API shared by existing main clients and the new picker.
>>>>>>> origin/main

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
<<<<<<< HEAD

    # Validate and decode the actual image contents.
    try:
        with Image.open(
           upload.stream,
            formats=("JPEG", "PNG", "WEBP"),
        ) as original:
            if original.width * original.height > MAX_IMAGE_PIXELS:
                raise ImageUploadError(
                    "Choose a photo with at most 12 million pixels."
                )

            original.load()

            picture = ImageOps.exif_transpose(original)
            picture.thumbnail((1600, 1600))
            picture = picture.convert("RGBA")
            picture.info.clear()

    except ImageUploadError:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ImageUploadError(
            "Choose a valid JPEG, PNG, or WebP image."
        ) from error

    # Generate the storage name ourselves.
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    filename = f"{uuid4().hex}.png"
    destination = folder / filename

    try:
        folder.mkdir(parents=True, exist_ok=True)
        picture.save(destination, format="PNG")
    finally:
        picture.close()

    return url_for("uploads.image", filename=filename)
=======
    try:
        normalized = read_photo(upload)
    except ValueError as error:
        raise ImageUploadError(str(error)) from error
    return image_fields({}, normalized)["image_url"]
>>>>>>> origin/main


@uploads.get("/uploads/<filename>")
def image(filename):
    return photo(filename)
