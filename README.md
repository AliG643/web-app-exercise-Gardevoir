# Gardevoir Campus Second-Hand Marketplace

## Product vision statement

Gardevoir helps students buy and sell second-hand items on campus through a simple mobile-friendly marketplace.

## Current status

The account flow, browsing, item details, publishing, seller management, and search are implemented. Sellers can edit their own listings with the shared publishing form, mark them sold, relist sold items, and permanently delete them. Public search supports combined keyword, category, and price filters plus sorting for active items. See [team handoff](docs/TEAM_HANDOFF.md).

## User stories and task boards

- [User stories in GitHub Issues](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues)
- [Sprint task boards in GitHub Projects](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/projects)

Issues are enabled. The team still needs to record its user stories and maintain the two sprint boards in GitHub.

## Run locally

1. Clone the team repository and enter it:

   ```bash
   git clone https://github.com/software-students-fall2026/web-app-exercise-Gardevoir.git
   cd web-app-exercise-Gardevoir
   ```

2. Run the course setup once in this clone and follow its prompts to approve the coding-tool hooks:

   ```bash
   python3 .automations/setup.py
   ```

   On Windows, use `python .automations/setup.py`.

3. Install Python 3.10 or newer and start Docker Desktop (or provide an existing MongoDB server). Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   On Windows, activate with `.venv\Scripts\activate`.

4. Copy `env.example` to `.env`. Replace `SECRET_KEY` with a random value and change `MONGO_PASSWORD`. Update the password in `MONGODB_URI` to match. If your team uses an existing MongoDB server, replace `MONGODB_URI` with that server's connection string. Keep `.env` private and share it only through the team's messenger channel.

   ```bash
   cp env.example .env
   ```

   On Windows, use `copy env.example .env`. A random secret can be generated with `python -c "import secrets; print(secrets.token_hex(32))"`.

5. If using the included local MongoDB service, start it from the repository root:

   ```bash
   docker compose up -d mongo
   ```

6. Check the database, create indexes, and add three sample items:

   ```bash
   flask --app app db-check
   flask --app app db-init
   flask --app app seed-demo
   ```

7. Start the web application:

   ```bash
   flask --app app run --debug
   ```

   Open `http://127.0.0.1:5000`. Register an account to access the protected pages. To give the sample items to that account for management testing, run `flask --app app seed-demo --owner-email your-email@example.edu` after registering.

To stop the local database, run `docker compose down`. The named volume preserves data between runs. For test dependencies, run `python -m pip install -r requirements-dev.txt` and then `python -m pytest -q`.

## Product photos

Publishing and editing support one JPG, PNG, or WebP photo up to 5 MB, with
preview, replacement, removal, and an optional external image URL. Files are
verified and normalized to JPEG; upload and edit validation preserve existing
photos when saving fails. The form also works without JavaScript.

Photos are stored in `instance/uploads/` by default and are excluded from Git.
MongoDB stores a reference, not the photo itself. When multiple checkouts use
the same database, set `UPLOAD_FOLDER` in each checkout's private `.env` to the
same absolute directory containing those photos. Restart Flask after changing
this value. Other computers need access to both the database and the photo
storage; cloning the repository alone does not transfer uploaded photos.
