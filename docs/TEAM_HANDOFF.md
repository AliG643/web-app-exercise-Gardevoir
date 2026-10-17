# Gardevoir foundation handoff

This document records the shared contracts for the first sprint. It lets each feature owner work in a separate file while the team connects their flows in small pull requests. The source of truth for course requirements remains `instructions.md`.

## Foundation available now

- `app/__init__.py` creates the Flask app, registers routes, and provides `db-check`, `db-init`, and `seed-demo` commands.
- `app/db.py` exposes `get_db()` and `parse_object_id()` to every feature module.
- `app/auth.py` implements registration, login, logout, and Flask-Login's current user. Use `@login_required` on owner-only pages and `current_owner_id()` when querying or writing items.
- `app/templates/base.html` and `app/static/styles.css` provide the mobile page shell and navigation.
- `app/item_data.py` holds common options and `public_item()` to convert MongoDB `_id` and `owner_id` values to strings for templates.
- `env.example` documents required settings. The real `.env` is ignored by Git.

## Item document contract

The `items` collection stores the following fields. Keep MongoDB IDs as `ObjectId` values in the database; convert them to strings only for URLs and templates.

| Field | Type | Rule |
| --- | --- | --- |
| `_id` | ObjectId | MongoDB generated |
| `title` | string | Required |
| `description` | string | Required |
| `price` | number | Greater than zero, US dollars |
| `category` | string | One of `CATEGORIES` in `app/item_data.py` |
| `condition` | string | One of `CONDITIONS` in `app/item_data.py` |
| `image_url` | string | URL supplied by the seller; an empty string is allowed for demo data |
| `contact_info` | string | Seller contact text |
| `owner_id` | ObjectId | Set by the server from `current_owner_id()` |
| `status` | string | `active`, `sold`, or `deleted`; new items start `active` |
| `created_at`, `updated_at` | UTC datetime | Set by the server |

The current category defaults are Electronics, Books, Furniture, Clothing, and Other. Condition defaults are New, Like New, Good, and Fair. **The group has not confirmed these options yet**; change them centrally in `app/item_data.py` after agreement.

Use a status change to `deleted` for a seller's delete action, then exclude deleted items from public queries. Public browsing and search should normally show only `active` items. A seller may see their own active and sold items. Check `owner_id == current_owner_id()` before editing, deleting, or marking an item sold.

## Route ownership

| Owner | File | Routes and work |
| --- | --- | --- |
| Ali | `app/market.py` | `GET /items`, `GET /items/<item_id>`; create a reusable item card template for list and search |
| Yvonne | `app/publish.py` | `GET/POST /items/new`; create a reusable item form template for publish and edit |
| Sirius | `app/manage.py` | `GET /my-items`, `GET/POST /items/<item_id>/edit`, `POST /items/<item_id>/delete`, `POST /items/<item_id>/sold`; reuse Yvonne's form |
| Zihan | `app/search.py` | `GET /search`; query fields `q`, `category`, `min_price`, `max_price`; reuse Ali's card |
| Yuyang | `app/auth.py`, `app/db.py`, shared shell | Maintain account, database, environment, and shared navigation contracts |

Search now renders results from MongoDB. The other feature routes currently return temporary pages; feature owners should replace those responses with their templates and queries. Keep the URL paths and endpoint names stable so the navigation and other modules continue to work. Public routes are browse, detail, and search. Publishing and managing require login.

For the search page, apply all provided filters together and preserve their values in the result form. Use only active items and show an empty state when nothing matches. The URL parameters are exactly `q`, `category`, `min_price`, and `max_price`.

Search keeps the `search.results` endpoint. Keywords match literal, case-insensitive text in the title or description; price bounds are inclusive. Invalid filters return a form with field errors (HTTP 400), and database failures show an availability message (HTTP 503). Until Ali's shared card is available, results use the isolated `search/_item_card.html` partial, with `item` produced by `public_item()`. Replace that include with the agreed shared card during integration. Search styles live in `app/static/search.css`; the shared base provides an optional `extra_head` block for page styles.

## Suggested integration check

1. Run the commands in README and confirm `db-check`, `db-init`, and `seed-demo` succeed.
2. Register and log in, then post an item. Confirm it appears in the list and search and opens in detail.
3. Edit it, then confirm the detail and search reflect the changes.
4. Mark it sold or delete it, then confirm public list and search omit it.

Use separate feature branches in this one team repository. The initial foundation needs to be merged before teammates pull it. The old React/Go/PostgreSQL project is a reference; the meeting plan says to confirm direct code reuse with the instructor and credit the original authors.
