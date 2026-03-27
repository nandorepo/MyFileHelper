from __future__ import annotations

from datetime import datetime, timezone

from flask import jsonify


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def json_response(*, code: int, message: str, data: dict | list | None, status: int):
    return jsonify({"code": code, "message": message, "data": data}), status


def ok_response(data: dict | list | None = None, status: int = 200):
    return json_response(code=0, message="ok", data=data, status=status)


def error_response(message: str, status: int, code: int = 1):
    return json_response(code=code, message=message, data=None, status=status)


def normalize_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def parse_utc(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
