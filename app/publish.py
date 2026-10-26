from datetime import datetime, timezone
from hmac import compare_digest
from secrets import token_urlsafe
from app.uploads import ImageUploadError, save_item_image
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required
from pymongo.errors import PyMongoError

from app.auth import current_owner_id
from app.db import get_db
from app.item_data import CATEGORIES, CONDITIONS
from app.item_forms import item_form_values, validate_item


publish = Blueprint("publish", __name__)


@publish.route("/items/new", methods=["GET", "POST"])
@login_required
def new_item():
    owner_id = current_owner_id()
    owner = str(owner_id)

    if request.method == "POST":
        saved_token = session.get("publish_csrf_token", "")
        form_token = request.form.get("csrf_token", "")

        if (
            session.get("publish_csrf_owner") != owner
            or not saved_token
            or not compare_digest(
                saved_token.encode(),
                form_token.encode(),
            )
        ):
            abort(400)

    if (
        session.get("publish_csrf_owner") != owner
        or not session.get("publish_csrf_token")
    ):
        session["publish_csrf_owner"] = owner
        session["publish_csrf_token"] = token_urlsafe(32)

    form_values = item_form_values(
        request.form if request.method == "POST" else {}
    )

    # The server now controls the stored image address.
    form_values["image_url"] = ""

    errors = {}
    status_code = 200

    if request.method == "POST":
        errors, price = validate_item(form_values)
        image_url = ""

        # Process the photo after validating the text fields.
        if not errors:
            try:
                image_url = save_item_image(
                    request.files.get("image")
                )
            except ImageUploadError as error:
                errors["image"] = str(error)
            except OSError:
                current_app.logger.exception(
                    "Unable to save product photo"
                )
                errors["image"] = (
                    "Photo storage is temporarily unavailable."
                )
                status_code = 503

        if errors:
            if status_code != 503:
                status_code = 400
        else:
            now = datetime.now(timezone.utc)

            item = form_values.copy()
            item["image_url"] = image_url
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

            try:
                result = get_db().items.insert_one(item)
            except PyMongoError:
                flash(
                    "We could not confirm your post. Check My items "
                    "before trying again to avoid a duplicate. "
                    "Your text entries are kept below. "
                    "Select your photo again if you retry.",
                    "error",
                )
                status_code = 503
            else:
                flash("Your item has been posted.", "success")
                return redirect(
                    url_for(
                        "market.item_detail",
                        item_id=str(result.inserted_id),
                    )
                )

    return render_template(
        "publish/new_item.html",
        form_values=form_values,
        errors=errors,
        categories=CATEGORIES,
        conditions=CONDITIONS,
        csrf_token=session["publish_csrf_token"],
    ), status_code