"""Seller listing, edit, hard delete, and sold flows."""

from datetime import datetime, timezone
from hmac import compare_digest
from secrets import token_urlsafe

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from flask_login import login_required

from app.auth import current_owner_id
from app.db import get_db, parse_object_id
from app.item_data import CATEGORIES, CONDITIONS, public_item
from app.item_forms import item_form_values, validate_item
from app.uploads import ImageUploadError,save_item_image
manage = Blueprint("manage", __name__)


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
        or not compare_digest(expected.encode(), submitted.encode())
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
    form_values = item_form_values(
        request.form if request.method == "POST" else document
    )

    errors = {}
    status_code = 200

    if request.method == "POST":
        # Validate text fields without treating the stored image
        # address as a user-entered URL.
        form_values["image_url"] = ""
        errors, price = validate_item(form_values)

        image_url = document.get("image_url", "")

        if not errors:
            try:
                image_url = save_item_image(
                    request.files.get("image"),
                    existing_url=image_url,
                )
            except ImageUploadError as error:
                errors["image"] = str(error)
            except OSError:
                current_app.logger.exception(
                    "Unable to save replacement photo"
                )
                errors["image"] = (
                    "Photo storage is temporarily unavailable."
                )
                status_code = 503

        if errors:
            if status_code != 503:
                status_code = 400
        else:
            changes = form_values.copy()
            changes["image_url"] = image_url
            changes["price"] = price
            changes["original_price"] = (
                float(form_values["original_price"])
                if form_values["original_price"]
                else None
            )
            changes["updated_at"] = datetime.now(timezone.utc)

            result = get_db().items.update_one(
                query,
                {"$set": changes},
            )

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
    ), status_code

@manage.post("/items/<item_id>/delete")
@login_required
def delete_item(item_id):
    _require_csrf_token()
    result = get_db().items.delete_one(_owned_item_filter(item_id))
    if result.deleted_count == 0:
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


@manage.post("/items/<item_id>/relist")
@login_required
def relist_item(item_id):
    _require_csrf_token()
    result = get_db().items.update_one(
        _owned_item_filter(item_id, statuses=("sold",)),
        {"$set": {
            "status": "active",
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    if result.matched_count == 0:
        abort(404)
    return redirect(url_for("manage.my_items"))
