from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from modules.message_routes import register_message_routes
from modules.state import AppState


class DummySocketIO:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def emit(self, event: str, payload: object) -> None:
        self.events.append((event, payload))


def _make_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-key"

    state = AppState()
    socketio = DummySocketIO()
    server_config = SimpleNamespace(
        pagination_default_limit=20,
        pagination_hard_cap=100,
    )

    register_message_routes(app, socketio, server_config, state)
    app.extensions["test_state"] = state
    app.extensions["test_socketio"] = socketio
    return app


def test_get_messages_rejects_invalid_pagination() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.get("/ui/messages?limit=abc&cursor=0")
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["message"] == "invalid pagination parameters"
    assert payload["data"] is None
    assert payload["code"] == 40001


def test_get_messages_rejects_non_positive_limit() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.get("/ui/messages?limit=0")
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == 40002


def test_get_messages_rejects_invalid_since() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.get("/ui/messages?since=not-a-time")
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == 40003


def test_get_messages_clamps_limit_and_cursor() -> None:
    app = _make_app()
    client = app.test_client()

    for idx in range(3):
        post_response = client.post("/ui/messages", json={"text": f"hello-{idx}"})
        assert post_response.status_code == 201

    response = client.get("/ui/messages?limit=999&cursor=-4")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["data"]["limit"] == 100
    assert payload["data"]["total"] == 3
    assert len(payload["data"]["items"]) == 3


def test_post_messages_rejects_non_array_attachment_ids() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.post("/ui/messages", json={"text": "hello", "attachment_ids": "x"})
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == 40004


def test_post_messages_rejects_missing_attachment() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.post("/ui/messages", json={"attachment_ids": ["missing-id"]})
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["code"] == 40402


def test_post_messages_accepts_text_only_message() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.post("/ui/messages", json={"text": "hello"})
    payload = response.get_json()

    assert response.status_code == 201
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert payload["data"]["message"]["text"] == "hello"
    assert payload["data"]["message"]["kind"] == "text"


def test_post_messages_normalizes_blank_client_msg_id_to_none() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.post("/ui/messages", json={"text": "hello", "client_msg_id": "   "})
    payload = response.get_json()

    assert response.status_code == 201
    assert payload["code"] == 0
    assert payload["data"]["message"]["client_msg_id"] is None


