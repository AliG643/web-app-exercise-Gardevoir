"""Sirius owns the seller listing, edit, delete, and sold flows."""

from flask import Blueprint, render_template
from flask_login import login_required

manage = Blueprint("manage", __name__)


@manage.get("/my-items")
@login_required
def my_items():
    return render_template("feature_placeholder.html", title="My items", owner="Sirius")


@manage.route("/items/<item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    return render_template("feature_placeholder.html", title="Edit item", owner="Sirius")


@manage.post("/items/<item_id>/delete")
@login_required
def delete_item(item_id):
    return render_template("feature_placeholder.html", title="Delete item", owner="Sirius"), 501


@manage.post("/items/<item_id>/sold")
@login_required
def mark_sold(item_id):
    return render_template("feature_placeholder.html", title="Mark sold", owner="Sirius"), 501
