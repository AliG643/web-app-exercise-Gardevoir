"""Seller listing, edit, soft delete, and sold flows."""

from datetime import datetime, timezone
from hmac import compare_digest
import math
from secrets import token_urlsafe
from urllib.parse import urlsplit

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from flask_login import login_required

from app.auth import current_owner_id
from app.db import get_db, parse_object_id
from app.item_data import CATEGORIES, CONDITIONS, public_item

manage = Blueprint("manage", __name__)

EDIT_FIELDS = (
    "title",
    "description",
    "price",
    "category",
    "condition",
    "image_url",
    "contact_info",
)


def _csrf_token():
    owner = str(current_owner_id())
    if session.get("manage_csrf_owner") != owner or not session.get("manage_csrf_token"):
        session["manage_csrf_owner"] = owner
        session["manage_csrf_token"] = token_urlsafe(32)
    return session["manage_csrf_token"]


def _require_csrf_token():
    expected = session.get("manage_csrf_token", "")
    submitted = request.form.get("csrf_token", "")
    if (
        session.get("manage_csrf_owner") != str(current_owner_id())
        or not expected
        or not compare_digest(expected, submitted)
    ):
        abort(400)


def _owned_item_filter(item_id, statuses=("active", "sold")):
    object_id = parse_object_id(item_id)
    if object_id is None:
        abort(404)
    return {
        "_id": object_id,
        "owner_id": current_owner_id(),
        "status": {"$in": list(statuses)},
    }


def _form_values(source):
    return {
        name: str(source.get(name, "") or "").strip()
        for name in EDIT_FIELDS
    }


def _validate_edit(values):
    errors = {}

    if not values["title"] or len(values["title"]) > 120:
        errors["title"] = "Enter a title of at most 120 characters."
    if not values["description"] or len(values["description"]) > 2000:
        errors["description"] = "Enter a description of at most 2000 characters."
    if values["category"] not in CATEGORIES:
        errors["category"] = "Choose a valid category."
    if values["condition"] not in CONDITIONS:
        errors["condition"] = "Choose a valid condition."
    if len(values["contact_info"]) > 200:
        errors["contact_info"] = "Contact information must be at most 200 characters."

    if len(values["image_url"]) > 2048:
        errors["image_url"] = "Image URL is too long."
    elif values["image_url"]:
        try:
            parsed = urlsplit(values["image_url"])
        except ValueError:
            parsed = None
        if parsed is None or parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors["image_url"] = "Enter an http or https image URL."

    try:
        price = float(values["price"])
    except ValueError:
        price = None
    if price is None or not math.isfinite(price) or price <= 0:
        errors["price"] = "Enter a price greater than zero."

    return errors, price


@manage.get("/my-items")
@login_required
def my_items():
    documents = get_db().items.find({
        "owner_id": current_owner_id(),
        "status": {"$in": ["active", "sold"]},
    }).sort([("created_at", -1), ("_id", -1)])

    items = [public_item(document) for document in documents]
    return render_template(
        "manage/my_items.html",
        editing=False,
        items=items,
        csrf_token=_csrf_token(),
    )


@manage.route("/items/<item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    if request.method == "POST":
        _require_csrf_token()

    query = _owned_item_filter(item_id)
    document = get_db().items.find_one(query)
    if document is None:
        abort(404)

    item = public_item(document)
    form_values = _form_values(request.form if request.method == "POST" else document)
    errors = {}

    if request.method == "POST":
        errors, price = _validate_edit(form_values)
        if not errors:
            changes = {
                name: form_values[name]
                for name in EDIT_FIELDS
                if name != "price"
            }
            changes["price"] = price
            changes["updated_at"] = datetime.now(timezone.utc)

            result = get_db().items.update_one(query, {"$set": changes})
            if result.matched_count == 0:
                abort(404)
            return redirect(url_for("manage.my_items"))

    return render_template(
        "manage/my_items.html",
        editing=True,
        item=item,
        form_values=form_values,
        errors=errors,
        categories=CATEGORIES,
        conditions=CONDITIONS,
        csrf_token=_csrf_token(),
    ), (400 if errors else 200)


@manage.post("/items/<item_id>/delete")
@login_required
def delete_item(item_id):
    _require_csrf_token()
    result = get_db().items.update_one(
        _owned_item_filter(item_id),
        {"$set": {
            "status": "deleted",
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    if result.matched_count == 0:
        abort(404)
    return redirect(url_for("manage.my_items"))


@manage.post("/items/<item_id>/sold")
@login_required
def mark_sold(item_id):
    _require_csrf_token()
    result = get_db().items.update_one(
        _owned_item_filter(item_id, statuses=("active",)),
        {"$set": {
            "status": "sold",
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    if result.matched_count == 0:
        abort(404)
    return redirect(url_for("manage.my_items"))