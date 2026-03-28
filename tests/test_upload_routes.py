from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from modules.state import AppState
from modules.upload_routes import register_upload_routes


class DummySocketIO:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def emit(self, event: str, payload: object) -> None:
        self.events.append((event, payload))


def _make_app(*, auto_chunk_enabled: bool = True, auto_chunk_default_enabled: bool = True) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-key"

    upload_config = SimpleNamespace(
        auto_chunk_enabled=auto_chunk_enabled,
        auto_chunk_default_enabled=auto_chunk_default_enabled,
    )
    register_upload_routes(app, DummySocketIO(), upload_config, AppState())
    return app


def test_upload_requires_file() -> None:
    app = _make_app()
    client = app.test_client()

    response = client.post("/ui/upload", data={})
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["message"] == "file is required"
    assert payload["data"] is None
    assert payload["code"] == 40015


def test_upload_rejects_auto_chunk_when_disabled() -> None:
    app = _make_app(auto_chunk_enabled=False)
    client = app.test_client()

    response = client.post(
        "/ui/upload",
        data={
            "file": (BytesIO(b"abc"), "a.txt", "text/plain"),
            "chunked": "1",
        },
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == 40016


def test_upload_maps_empty_file_error() -> None:
    app = _make_app()
    client = app.test_client()

    with patch("modules.upload_routes.orchestrate_auto_upload", return_value=(None, ("empty file", 400, 40017))):
        response = client.post(
            "/ui/upload",
            data={
                "file": (BytesIO(b"abc"), "a.txt", "text/plain"),
            },
        )

    payload = response.get_json()
    assert response.status_code == 400
    assert payload["code"] == 40017


def test_upload_maps_too_large_error() -> None:
    app = _make_app()
    client = app.test_client()

    with patch("modules.upload_routes.orchestrate_auto_upload", return_value=(None, ("file too large", 413, 41301))):
        response = client.post(
            "/ui/upload",
            data={
                "file": (BytesIO(b"abc"), "a.txt", "text/plain"),
            },
        )

    payload = response.get_json()
    assert response.status_code == 413
    assert payload["code"] == 41301


def test_upload_maps_merge_verification_error() -> None:
    app = _make_app()
    client = app.test_client()

    with patch(
        "modules.upload_routes.orchestrate_auto_upload",
        return_value=(None, ("merge verification failed", 500, 50001)),
    ):
        response = client.post(
            "/ui/upload",
            data={
                "file": (BytesIO(b"abc"), "a.txt", "text/plain"),
            },
        )

    payload = response.get_json()
    assert response.status_code == 500
    assert payload["code"] == 50001


def test_upload_success_response_shape_and_blank_client_msg_id() -> None:
    app = _make_app()
    client = app.test_client()

    service_result = {
        "file": {
            "file_id": "f1",
            "filename": "a.txt",
            "size": 3,
            "mime_type": "text/plain",
            "url": "/media/f1?download=1",
            "download_url": "/media/f1?download=1",
            "alias_url": "/media/f1?download=1",
            "inline_url": "/media/f1",
        },
        "upload": {"chunked": True, "chunk_size": 4096},
    }

    with patch(
        "modules.upload_routes.orchestrate_auto_upload",
        return_value=(service_result, None),
    ) as orchestrate_mock:
        response = client.post(
            "/ui/upload",
            data={
                "file": (BytesIO(b"abc"), "a.txt", "text/plain"),
                "client_msg_id": "   ",
            },
        )

    payload = response.get_json()

    assert response.status_code == 201
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert payload["data"]["file"]["file_id"] == "f1"
    assert payload["data"]["upload"]["chunk_size"] == 4096
    assert payload["data"]["upload"]["chunked"] is True

    assert orchestrate_mock.call_args.kwargs["client_msg_id"] == ""


def test_upload_passes_create_message_to_service() -> None:
    app = _make_app()
    client = app.test_client()

    service_result = {
        "file": {
            "file_id": "f2",
            "filename": "b.txt",
            "size": 3,
            "mime_type": "text/plain",
            "url": "/media/f2?download=1",
            "download_url": "/media/f2?download=1",
            "alias_url": "/media/f2?download=1",
            "inline_url": "/media/f2",
        },
        "upload": {"chunked": True, "chunk_size": 2048},
    }

    with patch(
        "modules.upload_routes.orchestrate_auto_upload",
        return_value=(service_result, None),
    ) as orchestrate_mock:
        response = client.post(
            "/ui/upload",
            data={
                "file": (BytesIO(b"abc"), "b.txt", "text/plain"),
                "create_message": "1",
            },
        )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["code"] == 0
    assert orchestrate_mock.call_args.kwargs["create_message"] is True

