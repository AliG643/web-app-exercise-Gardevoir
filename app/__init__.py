"""Application factory and route registration for Gardevoir."""

import os
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from pymongo.errors import PyMongoError

from app.db import init_db
from app.messages import messages

def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        MONGODB_URI=os.getenv("MONGODB_URI"),
        MONGODB_DB=os.getenv("MONGODB_DB", "gardevoir_secondhand"),
        UPLOAD_FOLDER=os.path.join(app.instance_path,"uploads"),
        MAX_CONTENT_LENGTH=None
    )
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY is missing. Copy env.example to .env and set it.")
    if not app.config["MONGODB_URI"]:
        raise RuntimeError("MONGODB_URI is missing. Copy env.example to .env and set it.")

    init_db(app)

    from app.auth import auth, init_login
    from app.market import market
    from app.publish import publish
    from app.manage import manage
    from app.search import search
    from app.uploads import uploads

    init_login(app)
    for blueprint in (auth, market, publish, manage, search,uploads,messages):
        app.register_blueprint(blueprint)

    @app.errorhandler(413)
    def upload_too_large(error):
        return render_template("upload_too_large.html"), 413

    @app.errorhandler(PyMongoError)
    def database_unavailable(error):
        app.logger.exception("Unable to complete a database operation")
        # Flask-Login's template context processor may repeat the failed lookup.
        # Render this fallback without request-specific context processors.
        template = app.jinja_env.get_template("errors/database_unavailable.html")
        return template.render(
            authentication_unavailable=True,
            retry_url=request.full_path if request.query_string else request.path,
        ), 503, {"Cache-Control": "no-store"}

    @app.get("/")
    def index():
        return redirect(url_for("market.items"))

    @app.cli.command("db-check")
    def db_check():
        """Check whether MongoDB accepts connections."""
        app.extensions["mongo_client"].admin.command("ping")
        click.echo("MongoDB connection successful.")

    @app.cli.command("db-init")
    def db_init():
        """Create the indexes shared by the first version of the app."""
        from app.db import get_db

        db = get_db()
        db.users.create_index("email", unique=True)
        db.items.create_index([("status", 1), ("created_at", -1)])
        db.items.create_index([("owner_id", 1), ("status", 1)])
        click.echo("MongoDB indexes are ready.")
        db.conversations.create_index(
        [("item_id", 1), ("buyer_id", 1), ("seller_id", 1)],
        unique=True,
        )

        db.messages.create_index([
            ("conversation_id", 1),
            ("created_at", 1),
            ("_id", 1),
        ])

    @app.cli.command("seed-demo")
    @click.option("--owner-email", help="Assign samples to an existing registered user.")
    def seed_demo(owner_email):
        """Insert a small repeatable catalog for parallel feature development."""
        from datetime import datetime, timezone

        from bson import ObjectId

        from app.db import get_db

        db = get_db()
        owner = None
        if owner_email:
            owner = db.users.find_one({"email": owner_email.strip().lower()})
            if owner is None:
                raise click.ClickException("Register that email in the app before seeding.")
        owner_id = owner["_id"] if owner else ObjectId("000000000000000000000001")
        samples = (
            ("Desk lamp", "Working lamp for a study desk", 12.0, "Furniture", "Good"),
            ("Calculus textbook", "Clean copy with a few notes", 18.0, "Books", "Good"),
            ("Wireless keyboard", "Compact keyboard, lightly used", 25.0, "Electronics", "Like New"),
        )
        now = datetime.now(timezone.utc)
        for title, description, price, category, condition in samples:
            db.items.update_one(
                {"title": title, "owner_id": owner_id},
                {"$setOnInsert": {
                    "title": title,
                    "description": description,
                    "price": price,
                    "category": category,
                    "condition": condition,
                    "image_url": "",
                    "contact_info": "Contact the seller through campus email",
                    "owner_id": owner_id,
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                }},
                upsert=True,
            )
        click.echo("Three demo items are available (existing samples were kept).")

    return app
