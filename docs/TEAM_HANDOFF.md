# Gardevoir foundation handoff

This document records the shared contracts for the first sprint. It lets each feature owner work in a separate file while the team connects their flows in small pull requests. The source of truth for course requirements remains `instructions.md`.

## Foundation available now

- `app/__init__.py` creates the Flask app, registers routes, and provides `db-check`, `db-init`, and `seed-demo` commands.
- `app/db.py` exposes `get_db()` and `parse_object_id()` to every feature module.
- `app/auth.py` implements registration, login, logout, and Flask-Login's current user. Use `@login_required` on owner-only pages and `current_owner_id()` when querying or writing items.
- `app/templates/base.html` and `app/static/styles.css` provide the mobile page shell and navigation.
- `app/item_data.py` holds common options and `public_item()` to convert MongoDB `_id` and `owner_id` values to strings for templates.
- `env.example` documents required settings. The real `.env` is ignored by Git.

## Account form CSRF protection

Login, registration, and logout POST requests require a hidden `csrf_token` that matches the current browser session. Render it with `auth_csrf_token()` in account forms and the shared logout form. Missing, empty, forged, or another session's tokens return HTTP 400 before account lookups or login state changes. Refresh the form to recover from a stale token. Successful registration, login, and logout rotate the token; ordinary GET requests and validation errors keep it stable so multiple open forms remain usable until the login state changes. Existing safe `next` redirects are preserved. Publishing and item management retain their own CSRF checks.

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
| `status` | string | `active` or `sold`; new items start `active` |
| `created_at`, `updated_at` | UTC datetime | Set by the server |

The current category defaults are Electronics, Books, Furniture, Clothing, and Other. Condition defaults are New, Like New, Good, and Fair. **The group has not confirmed these options yet**; change them centrally in `app/item_data.py` after agreement.

Deleting an item permanently removes its document from MongoDB with `delete_one()`. Match both the item ID and `owner_id == current_owner_id()` in the delete query, require a valid CSRF token, and check `deleted_count`; a missing or non-owned item returns 404. Sellers can delete their own active or sold items. The confirmation explains that deletion cannot be undone. Marking an item sold keeps the document and changes its status to `sold`. Public browsing and search show only `active` items; a seller may see their own active and sold items. Check ownership before editing or marking an item sold as well. Legacy documents with `status: "deleted"` remain hidden and are not automatically purged by this change.

## Route ownership

| Owner | File | Routes and work |
| --- | --- | --- |
| Ali | `app/market.py` | `GET /items`, `GET /items/<item_id>`; create a reusable item card template for list and search |
| Yvonne | `app/publish.py` | `GET/POST /items/new`; create a reusable item form template for publish and edit |
| Sirius | `app/manage.py` | `GET /my-items`, `GET/POST /items/<item_id>/edit`, `POST /items/<item_id>/delete`, `POST /items/<item_id>/sold`, `POST /items/<item_id>/relist`; reuse Yvonne's form |
| Zihan | `app/search.py` | `GET /search`; query fields `q`, `category`, `min_price`, `max_price`; reuse Ali's card |
| Yuyang | `app/auth.py`, `app/db.py`, shared shell | Maintain account, database, environment, and shared navigation contracts |

Browse, detail, search, publishing, and seller management now render their implemented pages with MongoDB queries. Keep the URL paths and endpoint names stable so the navigation and other modules continue to work. Public routes are browse, detail, and search. Publishing and managing require login.

Publishing and editing share `app/templates/items/_item_form.html`, the `item_form_values()` and `validate_item()` helpers in `app/item_forms.py`, and `app/static/item-form.css`. Add or change editable fields there to keep both flows consistent. Editing preserves invalid selections and entered values on HTTP 400 responses; validation errors link to the relevant fields. Only the shared form fields can be updated: `owner_id`, `status`, and `created_at` remain server-controlled. Management rejects malformed CSRF tokens, including non-ASCII input, before changing an item.

Sold items show a Relist button in My items to undo an accidental sold action. Its POST route requires login, a valid management CSRF token, and an item owned by the current seller with status `sold`. It restores status `active` and updates `updated_at`, so the item appears in public browsing, detail, and search again; the original fields, owner, and creation time are preserved.

For the search page, apply all provided filters together and preserve their values in the result form. Use only active items and show an empty state when nothing matches. Filter URL parameters are `q`, `category`, `min_price`, and `max_price`. The `sort` parameter accepts `newest` (the default), `price_asc`, or `price_desc`. Price sorting breaks ties by newest creation time, then descending `_id`, so equal-price items have a stable order. Unknown sort values return a field error without querying MongoDB.

Search keeps the `search.results` endpoint. Keywords match literal, case-insensitive text in the title or description; price bounds are inclusive. Invalid filters return a form with field errors (HTTP 400), and database failures show an availability message (HTTP 503). Results use Ali's shared `market/_item_card.html` partial, with `item` produced by `public_item()`, and load its `app/static/item-card.css` stylesheet. Search form and layout styles live in `app/static/search.css`; the shared base provides an optional `extra_head` block for page styles.

Selected search filters appear as individually removable links. Removing one filter preserves the others and the selected sort; Clear filters and the empty-state View all available items link preserve the sort while removing all filters. Recovery links fall back to `newest` if the supplied sort is invalid and omit unrelated URL parameters. Keywords are limited to 200 characters after trimming surrounding whitespace, with a field error and no database query when the limit is exceeded. Entered values and filter removal links remain available on validation and database errors.

## Suggested integration check

1. Run the commands in README and confirm `db-check`, `db-init`, and `seed-demo` succeed.
2. Register and log in, then post an item. Confirm it appears in the list and search and opens in detail.
3. Edit it, then confirm the detail and search reflect the changes.
4. Mark it sold, then confirm public list and search omit it while My items still shows it as sold.
5. Delete the item, then confirm it is absent from My items, the public list, search, and the MongoDB collection. Opening its old detail or edit URL should return 404; another seller must not be able to delete it.

Use separate feature branches in this one team repository. The initial foundation needs to be merged before teammates pull it. The old React/Go/PostgreSQL project is a reference; the meeting plan says to confirm direct code reuse with the instructor and credit the original authors.
