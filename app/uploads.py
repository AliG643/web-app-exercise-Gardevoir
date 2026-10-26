import re
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    send_from_directory,
    url_for,
)
from PIL import Image, ImageOps, UnidentifiedImageError

uploads = Blueprint("uploads", __name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000


class ImageUploadError(ValueError):
    """An uploaded file is not an acceptable product image."""


def save_item_image(upload, existing_url=""):
    # No replacement selected: keep the existing image.
    if upload is None or not upload.filename:
        return existing_url

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


@uploads.get("/uploads/<filename>")
def image(filename):
    if re.fullmatch(r"[0-9a-f]{32}\.png", filename) is None:
        abort(404)

    response = send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename,
        mimetype="image/png",
    )

    response.headers["X-Content-Type-Options"] = "nosniff"
    return response