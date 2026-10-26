import math
from urllib.parse import urlsplit

from app.item_data import CATEGORIES, CONDITIONS


ITEM_FIELDS = (
    "title",
    "description",
    "price",
    "original_price",
    "category",
    "condition",
    "image_url",
    "contact_info",
)


def item_form_values(source):
    values = {}

    for field in ITEM_FIELDS:
        value = source.get(field, "")

        if value is None:
            value = ""

        values[field] = str(value).strip()

    return values


def validate_item(values):
    errors = {}

    if not values["title"]:
        errors["title"] = "Please enter a title."
    elif len(values["title"]) > 120:
        errors["title"] = "Title must be at most 120 characters."

    if not values["description"]:
        errors["description"] = "Please enter a description."
    elif len(values["description"]) > 2000:
        errors["description"] = "Description must be at most 2000 characters."

    try:
        price = float(values["price"])
    except ValueError:
        price = None

    if price is None or not math.isfinite(price) or price <= 0:
        errors["price"] = "Please enter a price greater than zero."

    original_price_text = values.get("original_price", "")
    if original_price_text:
        try:
            original_price = float(original_price_text)
        except ValueError:
            original_price = None

        if (
            original_price is None
            or not math.isfinite(original_price)
            or original_price <= 0
        ):
            errors["original_price"] = "Please enter an original price greater than zero."
    if values["category"] not in CATEGORIES:
        errors["category"] = "Please select a valid category."

    if values["condition"] not in CONDITIONS:
        errors["condition"] = "Please select a valid condition."

    if len(values["contact_info"]) > 200:
        errors["contact_info"] = "Contact information is too long."

    image_url = values["image_url"]

    if len(image_url) > 2048:
        errors["image_url"] = "Image URL is too long."

    elif image_url:
        valid_url = True

        try:
            parsed = urlsplit(image_url)

            if parsed.scheme not in ("http", "https"):
                valid_url = False

            if not parsed.hostname:
                valid_url = False

            # 无效端口号会触发 ValueError。
            parsed.port

        except ValueError:
            valid_url = False

        for character in image_url:
            if character.isspace() or ord(character) < 32:
                valid_url = False
                break

        if not valid_url:
            errors["image_url"] = "Please enter an http or https image URL."

    return errors, price