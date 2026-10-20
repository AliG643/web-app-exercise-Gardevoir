"""Helpers that submit authentication forms as a browser would."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest


class CsrfInputs(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.tokens = []
        self.feed(response.get_data(as_text=True))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "csrf_token":
            self.tokens.append(attrs.get("value", ""))


@pytest.fixture
def csrf_token():
    def read_token(browser, path):
        response = browser.get(path)
        assert response.status_code == 200
        tokens = CsrfInputs(response).tokens
        assert tokens and tokens[0], "Expected a CSRF token in the rendered form"
        return tokens[0]

    return read_token


@pytest.fixture
def auth_post(csrf_token):
    def submit(browser, path, data=None, **kwargs):
        form_path = "/my-items" if urlsplit(path).path == "/logout" else path
        token = csrf_token(browser, form_path)
        return browser.post(path, data={**(data or {}), "csrf_token": token}, **kwargs)

    return submit
