from __future__ import annotations

import atexit

from flask import Flask
from flask_socketio import SocketIO

from modules.cleanup import clean_upload_dirs
from modules.config import load_server_config, load_upload_config
from modules.routes import register_routes
from modules.sockets import register_socket_handlers
from modules.state import AppState


def create_socketio_app(
    *,
    run_startup_cleanup: bool = True,
    register_exit_cleanup: bool = True,
) -> tuple[Flask, SocketIO]:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "d76vaS9lR64SdGl8DA"

    upload_config = load_upload_config()
    server_config = load_server_config()
    state = AppState()

    socketio = SocketIO(
        app,
        cors_allowed_origins=server_config.socketio_cors_allowed_origins,
        ping_interval=server_config.socketio_ping_interval,
        ping_timeout=server_config.socketio_ping_timeout,
    )

    upload_config.upload_dir.mkdir(parents=True, exist_ok=True)
    upload_config.chunk_dir.mkdir(parents=True, exist_ok=True)

    if run_startup_cleanup:
        clean_upload_dirs(upload_config)
    if register_exit_cleanup:
        atexit.register(clean_upload_dirs, upload_config)

    register_routes(
        app,
        socketio,
        upload_config,
        server_config,
        state,
        server_config.client_log,
    )
    register_socket_handlers(socketio, state)

    app.extensions["myfilehelper"] = {
        "upload_config": upload_config,
        "server_config": server_config,
        "state": state,
        "socketio": socketio,
    }
    return app, socketio


def create_app(
    *,
    run_startup_cleanup: bool = True,
    register_exit_cleanup: bool = True,
) -> Flask:
    app, _socketio = create_socketio_app(
        run_startup_cleanup=run_startup_cleanup,
        register_exit_cleanup=register_exit_cleanup,
    )
    return app


if __name__ == "__main__":
    app, socketio = create_socketio_app()
    socketio.run(app, host="0.0.0.0", port=80, debug=False, allow_unsafe_werkzeug=True)
