from __future__ import annotations

from flask import Flask
from flask_socketio import SocketIO

from modules.sockets import register_socket_handlers
from modules.state import AppState


def _make_socket_app() -> tuple[Flask, SocketIO, AppState]:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-key"
    socketio = SocketIO(app, async_mode="threading")
    state = AppState()
    register_socket_handlers(socketio, state)
    return app, socketio, state


def test_register_rejects_blank_username() -> None:
    app, socketio, _state = _make_socket_app()
    client = socketio.test_client(app, flask_test_client=app.test_client())

    ack = client.emit("register", {"username": "   "}, callback=True)

    assert ack["ok"] is False
    assert "cannot be empty" in ack["error"]
    client.disconnect()


def test_register_and_disconnect_updates_state() -> None:
    app, socketio, state = _make_socket_app()
    client = socketio.test_client(app, flask_test_client=app.test_client())

    ack = client.emit("register", {"username": "alpha"}, callback=True)

    assert ack == {"ok": True}
    assert len(state.clients) == 1
    assert len(state.terminal_sessions) == 1

    client.disconnect()

    assert state.clients == {}
    assert state.sid_to_terminal_session == {}
    assert state.terminal_sessions == {}


def test_message_event_ignores_blank_text() -> None:
    app, socketio, state = _make_socket_app()
    client = socketio.test_client(app, flask_test_client=app.test_client())
    client.emit("register", {"username": "alpha"}, callback=True)

    client.emit("message", {"text": "   "})

    assert state.messages == []
    client.disconnect()

