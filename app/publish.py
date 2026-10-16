"""Yvonne owns the shared item form and create flow."""

from flask import Blueprint, render_template
from flask_login import login_required

publish = Blueprint("publish", __name__)


@publish.route("/items/new", methods=["GET", "POST"])
@login_required
def new_item():
    return render_template("feature_placeholder.html", title="Post an item", owner="Yvonne")
