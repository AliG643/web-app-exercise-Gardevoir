"""Shared marketplace fields and display conversion.

Feature owners can import these constants without editing a shared route file.
"""

CATEGORIES = ("Electronics", "Books", "Furniture", "Clothing","Plush toys", "Other")
CONDITIONS = ("New", "Like New", "Good", "Fair")
STATUSES = ("active", "sold")


def public_item(document):
    """Convert MongoDB identifiers to strings for templates and URLs."""
    if document is None:
        return None
    item = dict(document)
    item["id"] = str(item.pop("_id"))
    item["owner_id"] = str(item["owner_id"])
    return item
