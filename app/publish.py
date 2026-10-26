from datetime import datetime, timezone
from hmac import compare_digest
from secrets import token_urlsafe

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.auth import current_owner_id
from app.db import get_db
from app.item_data import CATEGORIES, CONDITIONS
from app.item_forms import item_form_values, validate_item
from app.images import photo_input, image_fields, discard_unreferenced_photo


publish = Blueprint("publish", __name__)


@publish.route("/items/new", methods=["GET", "POST"])
@login_required
def new_item():
    owner_id = current_owner_id()
    owner = str(owner_id)

    if request.method == "POST":
        saved_token = session.get("publish_csrf_token", "")
        form_token = request.form.get("csrf_token", "")

        if session.get("publish_csrf_owner") != owner:
            abort(400)

        if not saved_token:
            abort(400)

        if not compare_digest(saved_token.encode(), form_token.encode()):
            abort(400)

    if (
        session.get("publish_csrf_owner") != owner
        or not session.get("publish_csrf_token")
    ):
        session["publish_csrf_owner"] = owner
        session["publish_csrf_token"] = token_urlsafe(32)

    if request.method == "POST":
        form_values = item_form_values(request.form)
    else:
        form_values = item_form_values({})

    errors = {}
    status_code = 200
    form_error = None

    if request.method == "POST":
        photo, remove, photo_errors = photo_input(form_values)
        errors, price = validate_item(form_values)
        errors.update(photo_errors)

        if errors:
            status_code = 400
        else:
            now = datetime.now(timezone.utc)

            item = form_values.copy()
            item["price"] = price
            item["original_price"] = (
                float(form_values["original_price"])
                if form_values["original_price"]
                else None
            )
            item["owner_id"] = owner_id
            item["status"] = "active"
            item["created_at"] = now
            item["updated_at"] = now
            item["_id"] = ObjectId()

            try:
                item.update(image_fields(form_values, photo, remove))
            except OSError:
                form_error = "Your photo could not be saved. Please try again."
                status_code = 503
            else:
                try:
                    get_db().items.insert_one(item)
                except PyMongoError:
                    discard_unreferenced_photo(item.get("image_key"))
                    form_error = (
                        "We could not confirm your post. Check My items before trying "
                        "again to avoid a duplicate. Your entries are kept below."
                    )
                    status_code = 503
                else:
                    flash("Your item has been posted.", "success")
                    destination = url_for("market.item_detail", item_id=str(item["_id"]))
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return jsonify(redirect_url=destination)
                    return redirect(destination)

    return render_template(
        "publish/new_item.html",
        form_values=form_values,
        errors=errors,
        categories=CATEGORIES,
        conditions=CONDITIONS,
        csrf_token=session["publish_csrf_token"],
        form_error=form_error,
        current_image_url="",
    ), status_code
