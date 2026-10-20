from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
import pytest
from bson import ObjectId
from app.market import item_detail, items
import mongomock
from pymongo.errors import AutoReconnect
from app import create_app
from app.db import get_db

class MarketPage(HTMLParser):
    """Extract product links from rendered HTML"""
    def __init__(self, response):
        super().__init__()
        self.item_links = []
        self.values = []
        self.feed(response.get_data(as_text=True))


    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get("href","")
        if tag == "a" and href.startswith("/items/"):
            self.item_links.append(href)
@pytest.fixture

def app():
    """create a fresh application and fake database for each test"""
    mongo_client = mongomock.MongoClient()
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "market-test-only-secret",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "test_market",
        "MONGO_CLIENT": mongo_client,
    })
    yield application
    mongo_client.close()


@pytest.fixture
def catalog(app):
    """add two active products, one sold, and one deleted"""
    owner_id = ObjectId()
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    documents = {}

    examples = (
        ("older", "active", 0),
        ("newer", "active", 1),
        ("sold", "sold", 2),
        ("deleted", "deleted", 3),
    )

    for name, status, days in examples:
        created_at = base_time + timedelta(days=days)

        documents[name] = {
            "_id": ObjectId(),
            "owner_id": owner_id,
            "title": f"{name.title()} textbook",
            "description": f"Description for the {name} textbook",
            "price": 12.5,
            "category": "Books",
            "condition": "Good",
            "image_url": "https://example.com/textbook.jpg",
            "contact_info": "seller@example.edu",
            "status": status,
            "created_at": created_at,
            "updated_at": created_at,
        }

    with app.app_context():
        get_db().items.insert_many(list(documents.values()))

    return documents


def test_browse_shows_active_items_once_newest_first(app, catalog):
    """check if active items are duplicated and deleted items get excluded"""
    response = app.test_client().get("/items")
    assert response.status_code == 200
    assert MarketPage(response).item_links == [
        f"/items/{catalog['newer']['_id']}",
        f"/items/{catalog['older']['_id']}",
    ]

    assert "$12.50" in response.get_data(as_text=True)


def test_empty_marketplace(app):
    response = app.test_client().get("/items")

    assert response.status_code == 200
    assert "No items available yet" in response.get_data(as_text=True)
    assert MarketPage(response).item_links == []


def test_itmes_displays_product_information(app,catalog):
    item = catalog["older"]
    response = app.test_client().get(f"/items/{item['_id']}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200

    for field in (
        "title",
        "description",
        "category",
        "condition",
        "contact_info",
    ):
        assert item[field] in html

    assert "$12.50" in html
    assert f'src="{item["image_url"]}"' in html


@pytest.mark.parametrize("item_id", ["example", "123", "z" * 24])
def test_invalid_id_returns_404(app, item_id):
    response = app.test_client().get(f"/items/{item_id}")

    assert response.status_code == 404


def test_missing_product_returns_404(app):
    response = app.test_client().get(f"/items/{ObjectId()}")

    assert response.status_code == 404


@pytest.mark.parametrize("name", ["sold", "deleted"])
def test_inactive_product_returns_404(app, catalog, name):
    response = app.test_client().get(
        f"/items/{catalog[name]['_id']}"
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "field, message",
    [
        ("image_url", "No photo available for this item."),
        (
            "contact_info",
            "The seller has not provided contact information.",
        ),
    ],
)
def test_detail_fallbacks(app, catalog, field, message):
    item_id = catalog["older"]["_id"]

    with app.app_context():
        get_db().items.update_one(
            {"_id": item_id},
            {"$set": {field: ""}},
        )

    response = app.test_client().get(f"/items/{item_id}")

    assert response.status_code == 200
    assert message in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "path, method",
    [
        ("/items", "find"),
        ("/items/000000000000000000000001", "find_one"),
    ],
)
def test_database_failure_returns_503(app, monkeypatch, path, method):
    def unavailable(*args, **kwargs):
        raise AutoReconnect("private database details")

    with app.app_context():
        monkeypatch.setattr(get_db().items, method, unavailable)

    response = app.test_client().get(path)
    html = response.get_data(as_text=True)

    assert response.status_code == 503
    assert "temporarily unavailable" in html
    assert "private database details" not in html
    assert "No items available yet" not in html
    assert MarketPage(response).item_links == []

class BrokenCursor:
    def __init__(self,product):
        self.product=product
    def sort(self,*args,**kwargs):
        return self
    def __iter__(self):
        yield self.product
        raise AutoReconnect("private cursor details")


def test_failure_during_cursor_iteration_returns_503(
    app, catalog, monkeypatch
):
    def failing_find(*args, **kwargs):
        return BrokenCursor(catalog["older"])


    with app.app_context():
        monkeypatch.setattr(get_db().items, "find", failing_find)

    response = app.test_client().get("/items")
    html = response.get_data(as_text=True)

    assert response.status_code == 503
    assert "temporarily unavailable" in html
    assert "private cursor details" not in html
    assert "No items available yet" not in html
    assert MarketPage(response).item_links == []

