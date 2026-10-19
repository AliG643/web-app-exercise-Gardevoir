"""Ali owns the public item list and detail implementation."""

from flask import Blueprint, render_template,current_app,abort
from pymongo.errors import PyMongoError
from app.db import get_db,parse_object_id
from app.item_data import public_item
market = Blueprint("market", __name__)


@market.get("/items")
def items():
    try:
        db = get_db()
        documents = db.items.find({"status":"active"}).sort([("created_at",-1),("_id",-1)])
        products = [public_item(document) for document in documents]
    except PyMongoError:
        current_app.logger.exception("Unable to load marketplace items.")
        return render_template("market/items.html", items=[],service_error=("The marketplace is temporarily unavailable. Please try again."),),503
    return render_template("market/items.html",items=products,service_error=None)


@market.get("/items/<item_id>")
def item_detail(item_id):
    object_id = parse_object_id(item_id)
    if object_id is None:
        abort(404,description= "Item not found.")
    try:
        document = get_db().items.find_one({"_id":object_id,"status":"active"})
    except PyMongoError:
        current_app.logger.exception("Unable to load item details.")
        abort(503,description=("Item details are temporarily unavailable. Please try again."),)
    if document is None:
        abort(404,description="Item not found.")
    return render_template("market/detail.html", item=public_item(document))

