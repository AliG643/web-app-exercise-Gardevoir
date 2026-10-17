from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from bson import ObjectId
import mongomock
from pymongo.errors import AutoReconnect
import pytest

from app import create_app
from app.db import get_db


class SearchPage(HTMLParser):
    """Read user-visible form values and item links without extra dependencies."""

    def __init__(self, response):
        super().__init__()
        self.item_links = []
        self.values = {}
        self.feed(response.get_data(as_text=True))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href", "").startswith("/items/"):
            self.item_links.append(attrs["href"])
        if tag == "input" and attrs.get("name"):
            self.values[attrs["name"]] = attrs.get("value", "")
        if tag == "option" and "selected" in attrs:
            self.values["category"] = attrs["value"]


@pytest.fixture
def catalog_app():
    client = mongomock.MongoClient()
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "search-test-only-secret",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "test_search",
        "MONGO_CLIENT": client,
    })
    owner = ObjectId()
    examples = (
        ("Desk lamp", "Working lamp for a study desk", 12.0, "Furniture", "active"),
        ("Reading light", "A quiet LAMP for reading", 25.0, "Furniture", "active"),
        ("Lamp design handbook", "Design reference", 18.0, "Books", "active"),
        ("Wireless keyboard", "Compact keyboard", 25.0, "Electronics", "active"),
        ("[CS] textbook", "Course reference", 35.0, "Books", "active"),
        ("Sold lamp", "Previously available", 12.0, "Furniture", "sold"),
        ("Deleted lamp", "Removed listing", 12.0, "Furniture", "deleted"),
    )
    documents = {}
    for offset, (title, description, price, category, status) in enumerate(examples):
        documents[title] = {
            "_id": ObjectId(),
            "owner_id": owner,
            "title": title,
            "description": description,
            "price": price,
            "category": category,
            "condition": "Good",
            "image_url": "",
            "status": status,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset),
        }
    with app.app_context():
        get_db().items.insert_many(list(documents.values()))
    yield app, documents
    client.close()


def links_for(documents, *titles):
    return [f"/items/{documents[title]['_id']}" for title in titles]


def test_search_is_public_and_shows_only_active_items_newest_first(catalog_app):
    app, documents = catalog_app
    response = app.test_client().get("/search")
    assert response.status_code == 200
    assert SearchPage(response).item_links == links_for(
        documents, "[CS] textbook", "Wireless keyboard", "Lamp design handbook", "Reading light", "Desk lamp"
    )
    assert b"5 items found" in response.data


@pytest.mark.parametrize(("filters", "titles"), [
    ({"q": "LAMP"}, ("Lamp design handbook", "Reading light", "Desk lamp")),
    ({"category": "Books"}, ("[CS] textbook", "Lamp design handbook")),
    ({"min_price": "25"}, ("[CS] textbook", "Wireless keyboard", "Reading light")),
    ({"max_price": "12"}, ("Desk lamp",)),
    ({"min_price": "25", "max_price": "25"}, ("Wireless keyboard", "Reading light")),
    ({"q": "lamp", "category": "Furniture", "min_price": "12", "max_price": "12"}, ("Desk lamp",)),
    ({"q": "lamp", "category": "Electronics"}, ()),
    ({"q": "[CS]"}, ("[CS] textbook",)),
    ({"q": ".*"}, ()),
    ({"q": "   ", "category": "", "min_price": "0", "max_price": ""},
     ("[CS] textbook", "Wireless keyboard", "Lamp design handbook", "Reading light", "Desk lamp")),
])
def test_filters_match_expected_items_and_combine(catalog_app, filters, titles):
    app, documents = catalog_app
    response = app.test_client().get("/search", query_string=filters)
    assert response.status_code == 200
    assert SearchPage(response).item_links == links_for(documents, *titles)


def test_results_keep_filters_and_display_prices_and_detail_links(catalog_app):
    app, documents = catalog_app
    filters = {"q": "lamp", "category": "Furniture", "min_price": "12.00", "max_price": "25.00"}
    response = app.test_client().get("/search", query_string=filters)
    assert SearchPage(response).values == filters
    assert SearchPage(response).item_links == links_for(documents, "Reading light", "Desk lamp")
    assert b"$12.00" in response.data and b"$25.00" in response.data
    assert b"No photo" in response.data


@pytest.mark.parametrize(("filters", "message"), [
    ({"min_price": "abc"}, b"Enter a valid price"),
    ({"min_price": "-1"}, b"Enter a valid price"),
    ({"min_price": "nan"}, b"Enter a valid price"),
    ({"max_price": "inf"}, b"Enter a valid price"),
    ({"max_price": "1e999"}, b"Enter a valid price"),
    ({"max_price": "-0.01"}, b"Enter a valid price"),
    ({"min_price": "25", "max_price": "12"}, b"Maximum price must be at least"),
    ({"category": "Not a category"}, b"Choose a category from the list"),
])
def test_invalid_filters_keep_input_and_do_not_query_database(catalog_app, monkeypatch, filters, message):
    app, _ = catalog_app

    def unexpected_query(*args, **kwargs):
        pytest.fail("Invalid filters must not run a database query")

    with app.app_context():
        monkeypatch.setattr(get_db().items, "find", unexpected_query)
    response = app.test_client().get("/search", query_string=filters)
    assert response.status_code == 400
    assert message in response.data
    assert b'aria-invalid="true"' in response.data
    for name, value in filters.items():
        assert SearchPage(response).values[name] == value
    assert SearchPage(response).item_links == []
    assert b"No items match" not in response.data


def test_no_matches_and_empty_catalog_have_distinct_helpful_messages(catalog_app):
    app, _ = catalog_app
    browser = app.test_client()
    response = browser.get("/search?q=nonexistent")
    assert response.status_code == 200
    assert b"No items match your search" in response.data
    assert b"0 items found" in response.data
    with app.app_context():
        get_db().items.delete_many({})
    response = browser.get("/search")
    assert response.status_code == 200
    assert b"No items are available right now" in response.data


def test_database_failure_does_not_look_like_no_matches(catalog_app, monkeypatch):
    app, _ = catalog_app

    def unavailable(*args, **kwargs):
        raise AutoReconnect("private database connection detail")

    with app.app_context():
        monkeypatch.setattr(get_db().items, "find", unavailable)
    response = app.test_client().get("/search?q=lamp")
    assert response.status_code == 503
    assert b"Search is temporarily unavailable" in response.data
    assert b"No items match" not in response.data
    assert b"private database connection detail" not in response.data
    assert SearchPage(response).values["q"] == "lamp"


def test_untrusted_text_is_escaped_and_search_does_not_change_items(catalog_app):
    app, documents = catalog_app
    title = '<script>alert("item")</script>'
    with app.app_context():
        db = get_db()
        db.items.update_one({"_id": documents["Desk lamp"]["_id"]}, {"$set": {"title": title}})
        before = list(db.items.find())
    browser = app.test_client()
    response = browser.get("/search", query_string={"q": title})
    assert response.status_code == 200
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data
    assert SearchPage(response).values["q"] == title
    assert SearchPage(response).item_links == links_for(documents, "Desk lamp")
    invalid = browser.get("/search", query_string={"category": title})
    assert invalid.status_code == 400
    assert b"<script>" not in invalid.data
    with app.app_context():
        assert list(get_db().items.find()) == before
