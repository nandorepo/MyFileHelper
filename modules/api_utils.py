from __future__ import annotations

from datetime import datetime, timezone

from flask import jsonify


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def api_response(*, code: int, message: str, data: dict | list | None, status: int):
    return jsonify({"code": code, "message": message, "data": data}), status


def api_ok(data: dict | list | None = None, status: int = 200):
    return api_response(code=0, message="ok", data=data, status=status)


def api_error(message: str, status: int, code: int = 1):
    return api_response(code=code, message=message, data=None, status=status)


def normalize_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def parse_utc(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def versioned_paths(path_suffix: str, api_config) -> list[str]:
    suffix = path_suffix if path_suffix.startswith("/") else f"/{path_suffix}"
    base = api_config.base_path.rstrip("/")
    version = api_config.default_version.strip("/")

    paths = [f"{base}/{version}{suffix}"]
    if api_config.enable_versionless_alias:
        paths.append(f"{base}{suffix}")

    unique_paths: list[str] = []
    for path in paths:
        if path not in unique_paths:
            unique_paths.append(path)
    return unique_paths


def register_api_route(app, path_suffix: str, methods: list[str], view_func, endpoint_prefix: str, api_config) -> None:
    for idx, path in enumerate(versioned_paths(path_suffix, api_config)):
        app.add_url_rule(
            path,
            endpoint=f"{endpoint_prefix}_{idx}",
            view_func=view_func,
            methods=methods,
        )


def download_path_for(file_id: str, api_config, versioned: bool = True) -> str:
    base = api_config.base_path.rstrip("/")
    if versioned:
        return f"{base}/{api_config.default_version}/download/{file_id}"
    return f"{base}/download/{file_id}"
