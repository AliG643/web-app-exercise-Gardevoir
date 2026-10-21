"""Authentication CSRF checks must run before account or login state changes."""

import mongomock
import pytest

from app import create_app


ACCOUNT = {
    "username": "Campus Seller",
    "email": "seller@example.edu",
    "password": "password123",
}


@pytest.fixture
def app():
    mongo = mongomock.MongoClient()
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "auth-csrf-test-only",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "test_auth_csrf",
        "MONGO_CLIENT": mongo,
    })
    yield application
    mongo.close()


@pytest.mark.parametrize("path", ("/login", "/register"))
def test_auth_forms_have_session_bound_tokens(app, csrf_token, path):
    browser = app.test_client()
    first = csrf_token(browser, path)
    assert csrf_token(browser, path) == first
    assert csrf_token(app.test_client(), path) != first


@pytest.mark.parametrize("path", ("/login", "/register"))
def test_login_and_register_can_be_open_in_separate_tabs(app, csrf_token, path):
    browser = app.test_client()
    first = csrf_token(browser, path)
    assert csrf_token(browser, "/register" if path == "/login" else "/login") == first


@pytest.mark.parametrize("path", ("/login", "/register", "/logout"))
@pytest.mark.parametrize("bad_token", (None, "", "forged", "无效令牌"))
def test_invalid_auth_tokens_have_no_account_or_session_effects(
    app, csrf_token, auth_post, monkeypatch, path, bad_token,
):
    browser = app.test_client()
    users = app.extensions["mongo_db"].users
    if path != "/register":
        assert auth_post(browser, "/register", data=ACCOUNT).status_code == 302
        if path == "/login":
            assert auth_post(browser, "/logout").status_code == 302

    csrf_token(browser, "/my-items" if path == "/logout" else path)
    with browser.session_transaction() as state:
        previous_user = state.get("_user_id")
    previous_count = users.count_documents({})

    def unexpected_lookup(*args, **kwargs):
        pytest.fail("Invalid CSRF must be rejected before looking up accounts")

    monkeypatch.setattr(users, "find_one", unexpected_lookup)
    data = ACCOUNT.copy()
    if bad_token is not None:
        data["csrf_token"] = bad_token
    response = browser.post(path, data=data)

    assert response.status_code == 400
    assert b"Refresh the page and try again" in response.data
    assert users.count_documents({}) == previous_count
    with browser.session_transaction() as state:
        assert state.get("_user_id") == previous_user


@pytest.mark.parametrize("path", ("/login", "/register", "/logout"))
def test_another_browsers_token_is_rejected(app, csrf_token, auth_post, path):
    browser = app.test_client()
    if path == "/logout":
        assert auth_post(browser, "/register", data=ACCOUNT).status_code == 302
    csrf_token(browser, "/my-items" if path == "/logout" else path)
    foreign_token = csrf_token(app.test_client(), "/login")

    response = browser.post(path, data={**ACCOUNT, "csrf_token": foreign_token})

    assert response.status_code == 400
    with browser.session_transaction() as state:
        assert ("_user_id" in state) == (path == "/logout")


@pytest.mark.parametrize("path", ("/login", "/register"))
def test_post_cannot_create_its_own_expected_token(app, path):
    browser = app.test_client()
    response = browser.post(path, data={**ACCOUNT, "csrf_token": "forged"})
    assert response.status_code == 400
    assert app.extensions["mongo_db"].users.count_documents({}) == 0


@pytest.mark.parametrize("path", ("/login", "/register", "/logout"))
def test_token_must_be_submitted_in_the_form_not_the_url(app, csrf_token, auth_post, path):
    browser = app.test_client()
    if path == "/logout":
        assert auth_post(browser, "/register", data=ACCOUNT).status_code == 302
    token = csrf_token(browser, "/my-items" if path == "/logout" else path)
    response = browser.post(path, query_string={"csrf_token": token}, data=ACCOUNT)
    assert response.status_code == 400
    with browser.session_transaction() as state:
        assert ("_user_id" in state) == (path == "/logout")


def test_successful_authentication_and_logout_rotate_tokens(app, csrf_token):
    browser = app.test_client()
    before_register = csrf_token(browser, "/register?next=/items/new")
    response = browser.post("/register", data={
        **ACCOUNT, "csrf_token": before_register, "next": "/items/new",
    })
    assert response.location == "/items/new"
    after_register = csrf_token(browser, "/my-items")
    assert after_register != before_register
    assert browser.post("/logout", data={"csrf_token": before_register}).status_code == 400
    assert browser.post("/logout", data={"csrf_token": after_register}).status_code == 302
    assert browser.get("/my-items").status_code == 302

    before_login = csrf_token(browser, "/login?next=/my-items")
    assert before_login != after_register
    response = browser.post("/login?next=/my-items", data={
        **ACCOUNT, "csrf_token": before_login,
    })
    assert response.location == "/my-items"
    after_login = csrf_token(browser, "/my-items")
    assert after_login != before_login
    assert browser.post("/logout", data={"csrf_token": before_login}).status_code == 400
    assert browser.post("/logout", data={"csrf_token": after_login}).status_code == 302


@pytest.mark.parametrize("path", ("/login", "/register"))
def test_validation_errors_keep_form_input_and_token(app, csrf_token, path):
    browser = app.test_client()
    token = csrf_token(browser, path)
    response = browser.post(path, data={
        **ACCOUNT, "password": "wrong", "csrf_token": token,
    })
    assert response.status_code == 200
    assert ACCOUNT["email"].encode() in response.data
    assert b'value="wrong"' not in response.data
    if path == "/register":
        assert ACCOUNT["username"].encode() in response.data
    assert csrf_token(browser, path) == token
    with browser.session_transaction() as state:
        assert "_user_id" not in state


def test_logout_requires_post_and_a_token_in_the_navigation(app, auth_post, csrf_token):
    browser = app.test_client()
    assert auth_post(browser, "/register", data=ACCOUNT).status_code == 302
    assert browser.get("/logout").status_code == 405
    page = browser.get("/my-items")
    assert b'action="/logout" method="post"' in page.data
    assert csrf_token(browser, "/my-items").encode() in page.data
    assert browser.get("/my-items").status_code == 200
