from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from modules.routes import register_routes
from modules.state import AppState


class DummySocketIO:
    def emit(self, *_args, **_kwargs):
        return None


def _make_app(tmp_path: Path) -> Flask:
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
        access_control_enabled=False,
        allowed_networks=[],
        autoindex_enabled=False,
        pagination_default_limit=20,
        pagination_hard_cap=100,
    )
    client_log_config = SimpleNamespace(
        path=tmp_path / "client.log",
        max_bytes=1024,
        backup_count=1,
    )

    register_routes(app, DummySocketIO(), upload_config, server_config, state, client_log_config)
    return app


def test_index_script_order_smoke(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = app.test_client()

    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200

    expected_files = [
        "socket_loader.js",
        "i18n.js",
        "upload_flow.js",
        "file_preview.js",
        "message_renderer.js",
        "message_view.js",
        "app.js",
    ]
    positions = [body.find(name) for name in expected_files]

    assert all(pos >= 0 for pos in positions)
    assert positions == sorted(positions)


def test_frontend_factory_exports_smoke() -> None:
    root = Path(__file__).resolve().parents[1]

    expected_exports = {
        "socket_loader.js": ("window.MyFileHelperSocketLoader", "ensureSocketIoLoaded"),
        "i18n.js": ("window.MyFileHelperI18n", "createI18n"),
        "upload_flow.js": ("window.MyFileHelperUploadFlow", "createUploadFlow"),
        "file_preview.js": ("window.MyFileHelperFilePreview", "createFilePreviewHelpers"),
        "message_renderer.js": ("window.MyFileHelperMessageRenderer", "createMessageRenderer"),
        "message_view.js": ("window.MyFileHelperMessageView", "createMessageView"),
    }

    for filename, (window_symbol, factory_symbol) in expected_exports.items():
        content = (root / "static" / filename).read_text(encoding="utf-8")
        assert window_symbol in content
        assert factory_symbol in content

