from __future__ import annotations

import atexit

from flask import Flask
from flask_socketio import SocketIO

from modules.cleanup import clean_upload_dirs
from modules.config import CLIENT_LOG_FILE, LOG_DIR, load_api_config, load_security_config, load_upload_config
from modules.routes import register_routes
from modules.sockets import register_socket_handlers
from modules.state import AppState

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"

UPLOAD_CONFIG = load_upload_config()
API_CONFIG = load_api_config()
SECURITY_CONFIG = load_security_config()

socketio = SocketIO(
    app,
    cors_allowed_origins=API_CONFIG.socketio_cors_allowed_origins,
    ping_interval=API_CONFIG.socketio_ping_interval,
    ping_timeout=API_CONFIG.socketio_ping_timeout,
)

UPLOAD_CONFIG.upload_dir.mkdir(parents=True, exist_ok=True)
UPLOAD_CONFIG.chunk_dir.mkdir(parents=True, exist_ok=True)

state = AppState()

clean_upload_dirs(UPLOAD_CONFIG)
atexit.register(clean_upload_dirs, UPLOAD_CONFIG)

register_routes(
    app,
    socketio,
    UPLOAD_CONFIG,
    API_CONFIG,
    SECURITY_CONFIG,
    state,
    LOG_DIR,
    CLIENT_LOG_FILE,
)
register_socket_handlers(socketio, state)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=80, debug=False, allow_unsafe_werkzeug=True)
