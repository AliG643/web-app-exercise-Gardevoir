"""Public item search with combined filters and selectable result ordering."""

import math
import re

from flask import Blueprint, current_app, render_template, request
from pymongo.errors import PyMongoError

from app.db import get_db
from app.item_data import CATEGORIES, public_item

search = Blueprint("search", __name__)

SORT_OPTIONS = {
    "newest": {
        "label": "Newest first",
        "order": [("created_at", -1), ("_id", -1)],
    },
    "price_asc": {
        "label": "Price: low to high",
        "order": [("price", 1), ("created_at", -1), ("_id", -1)],
    },
    "price_desc": {
        "label": "Price: high to low",
        "order": [("price", -1), ("created_at", -1), ("_id", -1)],
    },
}


@search.get("/search")
def results():
    filters = {
        name: request.args.get(name, "").strip()
        for name in ("q", "category", "min_price", "max_price")
    }
    sort = request.args.get("sort", "newest").strip() or "newest"
    errors = {}
    query = {"status": "active"}

    if sort not in SORT_OPTIONS:
        errors["sort"] = "Choose a sort order from the list."

    if filters["q"]:
        # Treat punctuation as text, rather than allowing user-supplied regexes.
        keyword = {"$regex": re.escape(filters["q"]), "$options": "i"}
        query["$or"] = [{"title": keyword}, {"description": keyword}]

    if filters["category"]:
        if filters["category"] not in CATEGORIES:
            errors["category"] = "Choose a category from the list."
        else:
            query["category"] = filters["category"]

    prices = {}
    for field, operator in (("min_price", "$gte"), ("max_price", "$lte")):
        if not filters[field]:
            continue
        try:
            price = float(filters[field])
        except ValueError:
            errors[field] = "Enter a valid price of zero or more."
            continue
        if not math.isfinite(price) or price < 0:
            errors[field] = "Enter a valid price of zero or more."
        else:
            prices[operator] = price

    if "$gte" in prices and "$lte" in prices and prices["$gte"] > prices["$lte"]:
        errors["max_price"] = "Maximum price must be at least the minimum price."
    if prices:
        query["price"] = prices

    items = []
    service_error = None
    status_code = 400 if errors else 200
    if not errors:
        try:
            documents = get_db().items.find(query).sort(SORT_OPTIONS[sort]["order"])
            items = [public_item(document) for document in documents]
        except PyMongoError:
            current_app.logger.exception("Unable to load search results")
            service_error = "Search is temporarily unavailable. Please try again."
            status_code = 503

    return render_template(
        "search/results.html",
        filters=filters,
        categories=CATEGORIES,
        sort=sort,
        sort_options=SORT_OPTIONS,
        errors=errors,
        items=items,
        service_error=service_error,
        has_filters=any(filters.values()),
    ), status_code
