# Frontend UI conventions

Gardevoir keeps its yellow accent and familiar marketplace workflows. The frontend uses local CSS and inline SVG macros, with no font service, JavaScript framework, or additional runtime dependency.

## Shared system

- `app/static/styles.css` owns semantic colors, spacing, focus treatment, buttons, navigation, fields, notices, and basic page layouts.
- `app/templates/_ui.html` provides the common stroke icons and field-error markup. Icons are decorative; their surrounding labels name the action.
- The active navigation link has `aria-current="page"`. A visible-on-focus skip link leads to the main content.
- Controls keep at least 44px target height. Motion is limited to short state transitions and respects reduced-motion preferences.
- Browse and search reuse `market/_item_card.html` and `item-card.css`. Missing photos have a deliberate placeholder; real images reserve their layout space.
- Publishing and editing reuse the same grouped fields, including optional original price. Validation keeps entered values, links the error summary to fields, and connects field-level errors with `aria-describedby`.
- `manage.css` styles seller rows and distinguishes active, sold, and destructive actions. Existing confirmations, ownership checks and CSRF validation remain in place.

## Responsive behavior

- Mobile navigation uses a compact Post label. Category shortcuts can scroll within their own row.
- Browse and search cards use two columns on most phones and one below 360px. Browse uses three columns on wider screens.
- Search puts filters beside results above 760px and stacks them on smaller screens.
- Item details stack on mobile; form field pairs stack below 540px.

## Verification

Run `python -m pytest -q` using `requirements-dev.txt`. Tests use mongomock. Browser QA should also cover 320px, 390px, 768px and a desktop width: browse, search, detail, account forms, posting, editing, My items, empty results, field errors and the database fallback. Confirm keyboard focus, long content, photo/no-photo states and no document-level horizontal scrolling.

This UI change is based on main with PRs #16 and #17. Local file-upload work is maintained separately and is not part of this branch.
