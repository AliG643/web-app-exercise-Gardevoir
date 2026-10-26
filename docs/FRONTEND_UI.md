# Frontend UI conventions

Gardevoir keeps its yellow accent and familiar marketplace workflows. The frontend uses local CSS and inline SVG macros, with no font service or JavaScript framework. Photo selection uses progressive JavaScript enhancement; the server validates uploads with Pillow.

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

Run `node --test tests/client/item-form.test.cjs` with Node.js 24 or newer for
client-side photo recovery checks. These execute the shipped form event handlers
with a small DOM/network fixture and require no npm packages. They cover rejecting
an oversized, unsupported, or empty photo, discarding it through a visible control,
keeping entered text or the existing photo, and submitting without a replacement.
The Client tests workflow runs them on pull requests to main.

Run `python -m pytest -q` using `requirements-dev.txt`. Tests use mongomock. Browser QA should also cover 320px, 390px, 768px and a desktop width: browse, search, detail, account forms, posting, editing, My items, empty results, field errors and the database fallback. Confirm keyboard focus, long content, photo/no-photo states and no document-level horizontal scrolling.

Local photo upload is integrated with the grouped item form. It supports preview, replacement, removal, native form submission, and the existing image-link option. When checkouts share MongoDB, configure their private `.env` files with the same absolute `UPLOAD_FOLDER`; images remain excluded from Git. The detail image uses `height: auto` so the HTML 640px dimensions do not push titles below the mobile viewport.
