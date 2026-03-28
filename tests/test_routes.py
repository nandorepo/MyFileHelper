from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from modules.error_codes import ROUTE_ACCESS_FORBIDDEN, ROUTE_MEDIA_FILE_NOT_FOUND
from modules.routes import is_ip_allowed, register_routes
from modules.state import AppState


class DummySocketIO:
    def emit(self, *_args, **_kwargs):
        return None


def _make_app(
    tmp_path: Path,
    *,
    access_control_enabled: bool = False,
    allowed_networks: list[str] | None = None,
    autoindex_enabled: bool = False,
) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parents[1] / "templates"),
    )
    app.config["SECRET_KEY"] = "test-key"

    upload_dir = tmp_path / "files"
    chunk_dir = tmp_path / "chunks"
    upload_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    state = AppState()

    upload_config = SimpleNamespace(
        upload_dir=upload_dir,
        chunk_dir=chunk_dir,
        auto_chunk_default_enabled=True,
        auto_chunk_enabled=True,
    )
    server_config = SimpleNamespace(
        access_control_enabled=access_control_enabled,
        allowed_networks=allowed_networks or [],
        autoindex_enabled=autoindex_enabled,
        pagination_default_limit=20,
        pagination_hard_cap=100,
    )
    client_log_config = SimpleNamespace(
        path=tmp_path / "client.log",
        max_bytes=1024,
        backup_count=1,
    )

    register_routes(app, DummySocketIO(), upload_config, server_config, state, client_log_config)
    app.extensions["test_state"] = state
    app.extensions["test_upload_dir"] = upload_dir
    return app


def test_is_ip_allowed_accepts_ipv4_and_ipv6() -> None:
    assert is_ip_allowed("192.168.1.10", ["192.168.1.0/24"])
    assert is_ip_allowed("2001:db8::1", ["2001:db8::/32"])


def test_is_ip_allowed_rejects_invalid_input() -> None:
    assert not is_ip_allowed("", ["0.0.0.0/0"])
    assert not is_ip_allowed("not-an-ip", ["0.0.0.0/0"])
    assert not is_ip_allowed("10.0.0.10", ["bad-cidr"])


def test_register_routes_exposes_ui_endpoints(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/ui/upload" in rules
    assert "/ui/messages" in rules
    assert "/ui/client-log" in rules


def test_access_control_blocks_disallowed_ip(tmp_path: Path) -> None:
    app = _make_app(tmp_path, access_control_enabled=True, allowed_networks=["10.0.0.0/8"])
    client = app.test_client()

    response = client.get("/files", environ_base={"REMOTE_ADDR": "192.168.1.88"})
    payload = response.get_json()

    assert response.status_code == 403
    assert payload["code"] == ROUTE_ACCESS_FORBIDDEN
    assert payload["message"] == "forbidden"
    assert payload["data"] is None


def test_files_index_returns_404_when_autoindex_disabled(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = app.test_client()

    response = client.get("/files")

    assert response.status_code == 404


def test_access_control_uses_x_forwarded_for_first_ip(tmp_path: Path) -> None:
    app = _make_app(tmp_path, access_control_enabled=True, allowed_networks=["10.0.0.0/8"])
    client = app.test_client()

    response = client.get(
        "/",
        headers={"X-Forwarded-For": "192.168.1.88, 10.0.0.9"},
        environ_base={"REMOTE_ADDR": "10.1.1.1"},
    )
    payload = response.get_json()

    assert response.status_code == 403
    assert payload["code"] == ROUTE_ACCESS_FORBIDDEN


def test_media_missing_entry_returns_plain_404(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = app.test_client()

    response = client.get("/media/not-found")

    assert response.status_code == 404
    assert response.get_data(as_text=True) == "Not Found"


def test_media_missing_file_on_disk_returns_json_error(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = app.test_client()
    state = app.extensions["test_state"]

    state.uploaded_files["f1"] = {
        "file_id": "f1",
        "stored_name": "missing.txt",
        "original_name": "missing.txt",
        "mime": "text/plain",
    }

    response = client.get("/media/f1")
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["code"] == ROUTE_MEDIA_FILE_NOT_FOUND
    assert payload["message"] == "file not found"
    assert payload["data"] is None


def test_files_index_enabled_returns_html_with_media_links(tmp_path: Path) -> None:
    app = _make_app(tmp_path, autoindex_enabled=True)
    client = app.test_client()
    state = app.extensions["test_state"]

    state.uploaded_files["f2"] = {
        "file_id": "f2",
        "original_name": "alpha.txt",
        "size": 12,
        "uploaded_at": "2026-03-28T01:02:03Z",
    }

    response = client.get("/files")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "text/html" in response.headers.get("Content-Type", "")
    assert "Uploaded Files" in body
    assert "File ID" in body
    assert "f2" in body
    assert "/media/1" in body
    assert "/media/f2" not in body
    assert "/media/f2?download=1" not in body


def test_media_alias_resolves_to_first_sorted_file(tmp_path: Path) -> None:
    app = _make_app(tmp_path, autoindex_enabled=True)
    client = app.test_client()
    state = app.extensions["test_state"]
    upload_dir = app.extensions["test_upload_dir"]

    first_file_path = upload_dir / "first.txt"
    first_file_path.write_bytes(b"first-content")
    second_file_path = upload_dir / "second.txt"
    second_file_path.write_bytes(b"second-content")

    state.uploaded_files["f2"] = {
        "file_id": "f2",
        "stored_name": "second.txt",
        "original_name": "second.txt",
        "mime": "text/plain",
        "size": 14,
        "uploaded_at": "2026-03-28T01:02:04Z",
    }
    state.uploaded_files["f1"] = {
        "file_id": "f1",
        "stored_name": "first.txt",
        "original_name": "first.txt",
        "mime": "text/plain",
        "size": 13,
        "uploaded_at": "2026-03-28T01:02:03Z",
    }

    response = client.get("/media/1")

    assert response.status_code == 200
    assert response.get_data() == b"first-content"
