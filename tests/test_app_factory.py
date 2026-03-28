from __future__ import annotations

from app import create_app, create_socketio_app


def test_create_app_registers_core_routes_without_runtime_cleanup() -> None:
    app = create_app(run_startup_cleanup=False, register_exit_cleanup=False)
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/" in rules
    assert "/ui/upload" in rules
    assert "/ui/messages" in rules
    assert "/ui/client-log" in rules


def test_create_socketio_app_exposes_runtime_dependencies() -> None:
    app, socketio = create_socketio_app(run_startup_cleanup=False, register_exit_cleanup=False)
    runtime = app.extensions["myfilehelper"]

    assert runtime["socketio"] is socketio
    assert runtime["state"] is not None
    assert runtime["upload_config"] is not None
    assert runtime["server_config"] is not None

