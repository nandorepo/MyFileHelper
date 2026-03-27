from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import request


def register_log_routes(app, client_log_config) -> None:
    client_log_config.path.parent.mkdir(parents=True, exist_ok=True)
    client_log_handler = RotatingFileHandler(
        client_log_config.path,
        maxBytes=client_log_config.max_bytes,
        backupCount=client_log_config.backup_count,
        encoding="utf-8",
    )
    client_log_handler.setLevel(0)
    client_log_handler.setFormatter(None)
    client_log_logger = logging.getLogger("client_log")
    client_log_logger.propagate = False
    client_log_logger.addHandler(client_log_handler)

    def handle_client_log() -> tuple[str, int]:
        data = request.get_json(silent=True) or {}
        entry = {
            "server_ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "level": data.get("level", "info"),
            "args": data.get("args", []),
            "page": data.get("page", request.path),
            "ua": request.headers.get("User-Agent", ""),
        }
        client_log_logger.info(json.dumps(entry, ensure_ascii=False))
        return "", 204

    app.add_url_rule("/ui/client-log", endpoint="ui_client_log", view_func=handle_client_log, methods=["POST"])
