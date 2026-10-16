"""Ali owns the public item list and detail implementation."""

from flask import Blueprint, render_template

market = Blueprint("market", __name__)


@market.get("/items")
def items():
    return render_template("feature_placeholder.html", title="Marketplace", owner="Ali")


@market.get("/items/<item_id>")
def item_detail(item_id):
    return render_template("feature_placeholder.html", title="Item details", owner="Ali")
