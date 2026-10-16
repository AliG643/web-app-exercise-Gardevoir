"""One MongoDB client shared by all feature modules."""

from bson import ObjectId
from bson.errors import InvalidId
from flask import current_app
from pymongo import MongoClient


def init_db(app):
    client = app.config.get("MONGO_CLIENT")
    if client is None:
        client = MongoClient(app.config["MONGODB_URI"], serverSelectionTimeoutMS=3000)
    app.extensions["mongo_client"] = client
    app.extensions["mongo_db"] = client[app.config["MONGODB_DB"]]


def get_db():
    """Return the configured PyMongo Database inside a request or CLI context."""
    return current_app.extensions["mongo_db"]


def parse_object_id(value):
    """Return a valid ObjectId, or None for an invalid URL or form value."""
    if value is None:
        return None
    try:
        return ObjectId(value)
    except (TypeError, InvalidId):
        return None
