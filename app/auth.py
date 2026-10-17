"""Registration and login. Other modules use current_user and current_owner_id."""

from bson import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db, parse_object_id

auth = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"


class User(UserMixin):
    def __init__(self, document):
        self.id = str(document["_id"])
        self.username = document["username"]
        self.email = document["email"]


def init_login(app):
    login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    object_id = parse_object_id(user_id)
    if object_id is None:
        return None
    document = get_db().users.find_one({"_id": object_id})
    return User(document) if document else None


def current_owner_id():
    """Return the logged-in user's ObjectId for item ownership queries."""
    if not current_user.is_authenticated:
        return None
    return ObjectId(current_user.id)


def post_login_destination():
    """Return a requested local page, or fall back to the item list."""
    target = request.values.get("next", "")
    if (
        target.startswith("/")
        and not target.startswith("//")
        and "\\" not in target
        and not any(ord(character) < 32 for character in target)
    ):
        return target
    return url_for("market.items")


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("market.items"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not email or not password:
            flash("Please complete every field.", "error")
        elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            flash("Please enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif get_db().users.find_one({"email": email}):
            flash("An account with that email already exists.", "error")
        else:
            try:
                result = get_db().users.insert_one(
                    {
                        "username": username,
                        "email": email,
                        "password_hash": generate_password_hash(password),
                    }
                )
            except DuplicateKeyError:
                flash("An account with that email already exists.", "error")
            else:
                login_user(User({"_id": result.inserted_id, "username": username, "email": email}))
                return redirect(url_for("market.items"))
    return render_template("auth/register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(post_login_destination())
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        document = get_db().users.find_one({"email": email})
        if document and check_password_hash(document["password_hash"], password):
            login_user(User(document))
            return redirect(post_login_destination())
        flash("Incorrect email or password.", "error")
    return render_template("auth/login.html")


@auth.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("market.items"))
