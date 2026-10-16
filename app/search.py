"""Zihan owns search and filter implementation."""

from flask import Blueprint, render_template

search = Blueprint("search", __name__)


@search.get("/search")
def results():
    return render_template("feature_placeholder.html", title="Search results", owner="Zihan")
