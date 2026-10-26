from flask import Blueprint, abort,render_template,redirect,request,url_for
from flask_login import login_required
from app.auth import current_owner_id, require_auth_csrf_token
from app.db import get_db, parse_object_id
from datetime import datetime,timezone
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
messages = Blueprint("messages", __name__)

# The existing auth check must also be attached to this blueprint.
messages.before_request(require_auth_csrf_token)

@messages.get("/messages")
@login_required
def inbox():
    viewer_id = current_owner_id()

    documents = get_db().conversations.find({
        "$or": [
            {"buyer_id": viewer_id},
            {"seller_id": viewer_id},
        ],
    }).sort([
        ("updated_at", -1),
        ("_id", -1),
    ])

    conversations = [
        {
            "id":str(document["_id"]),
            "item_title": document.get(
                "item_title", "Item conversation"
            )
        }
        for document in documents
    ]

    return (
        render_template(
            "messages/inbox.html",
            conversations=conversations,
        ),
        200,
        {"Cache-Control": "no-store"},
    )


def _conversation_or_404(conversation_id):
    object_id = parse_object_id(conversation_id)
    if object_id is None:
        abort(404)

    viewer_id = current_owner_id()
    if viewer_id is None:
        abort(401)

    conversation = get_db().conversations.find_one({
        "_id": object_id,
        "$or": [
            {"buyer_id": viewer_id},
            {"seller_id": viewer_id},
        ],
    })

    if conversation is None:
        abort(404)

    return conversation


@messages.after_request
def private_chat_response(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@messages.post("/items/<item_id>/conversations")
@login_required
def start_conversation(item_id):
    item_object_id = parse_object_id(item_id)
    if item_object_id is None:
        abort(404)

    db = get_db()
    item = db.items.find_one({
        "_id": item_object_id,
        "status": "active",
    })
    if item is None:
        abort(404)

    buyer_id = current_owner_id()
    seller_id = item["owner_id"]

    if buyer_id == seller_id:
        abort(400, description="This is your own listing.")

    if db.users.find_one({"_id": seller_id}, {"_id": 1}) is None:
        abort(404, description="Seller account unavailable.")

    key = {
        "item_id": item_object_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
    }
    now = datetime.now(timezone.utc)

    try:
        thread = db.conversations.find_one_and_update(
            key,
            {"$setOnInsert": {
                **key,
                "item_title": item["title"],
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        thread = db.conversations.find_one(key)
        if thread is None:
            raise

    return redirect(url_for(
        "messages.conversation",
        conversation_id=str(thread["_id"]),
    ))

@messages.route(
    "/conversations/<conversation_id>",
    methods=["GET", "POST"],
)
@login_required
def conversation(conversation_id):
    thread = _conversation_or_404(conversation_id)
    db = get_db()
    viewer_id = current_owner_id()

    if request.method == "POST":
        body = request.form.get("body", "").strip()

        if not 1 <= len(body) <= 2000:
            abort(
                400,
                description="Enter a message of 1 to 2000 characters.",
            )

        now = datetime.now(timezone.utc)

        db.messages.insert_one({
            "conversation_id": thread["_id"],
            "sender_id": viewer_id,
            "body": body,
            "created_at": now,
        })

        db.conversations.update_one(
            {"_id": thread["_id"]},
            {"$max": {"updated_at": now}},
        )

        return redirect(url_for(
            "messages.conversation",
            conversation_id=str(thread["_id"]),
        ))

    other_id = (
        thread["seller_id"]
        if viewer_id == thread["buyer_id"]
        else thread["buyer_id"]
    )
    other_user = db.users.find_one(
        {"_id": other_id},
        {"username": 1},
    ) or {}

    documents = db.messages.find({
        "conversation_id": thread["_id"],
    }).sort([("created_at", 1), ("_id", 1)])

    thread_messages = [
        {
            "body": document["body"],
            "mine": document["sender_id"] == viewer_id,
        }
        for document in documents
    ]

    return render_template(
        "messages/conversation.html",
        conversation={
            "id": str(thread["_id"]),
            "item_title": thread.get(
                "item_title", "Item conversation"
            ),
        },
        partner_name=other_user.get(
            "username", "Unavailable account"
        ),
        thread_messages=thread_messages,
    )