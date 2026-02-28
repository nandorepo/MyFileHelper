
from __future__ import annotations

import atexit
import ipaddress
import json
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List
from uuid import uuid4

import yaml
from flask import Flask, jsonify, render_template, request, send_file, session
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"

LOG_DIR = Path("logs")
CLIENT_LOG_FILE = LOG_DIR / "client.log"
UPLOAD_CONFIG_PATH = Path("config/upload_config.yaml")
API_CONFIG_PATH = Path("config/api_config.yaml")
SECURITY_CONFIG_PATH = Path("config/security_config.yaml")


@dataclass
class UploadConfig:
    upload_dir: Path
    chunk_dir: Path
    max_file_size_mb: int
    default_chunk_size_mb: int
    min_chunk_size_mb: int
    max_chunk_size_mb: int
    max_concurrency: int
    auto_chunk_enabled: bool
    auto_chunk_default_enabled: bool
    high_concurrency_threshold: int
    mem_budget_per_upload_mb: int

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def default_chunk_size_bytes(self) -> int:
        return self.default_chunk_size_mb * 1024 * 1024

    @property
    def min_chunk_size_bytes(self) -> int:
        return self.min_chunk_size_mb * 1024 * 1024

    @property
    def max_chunk_size_bytes(self) -> int:
        return self.max_chunk_size_mb * 1024 * 1024

    @property
    def mem_budget_per_upload_bytes(self) -> int:
        return self.mem_budget_per_upload_mb * 1024 * 1024


@dataclass
class ApiConfig:
    base_path: str
    default_version: str
    supported_versions: list[str]
    enable_versionless_alias: bool
    pagination_default_limit: int
    pagination_hard_cap: int
    pagination_target_response_bytes: int
    socketio_ping_interval: int
    socketio_ping_timeout: int
    socketio_cors_allowed_origins: str | list[str]


@dataclass
class SecurityConfig:
    auth_enabled: bool
    auth_mode: str
    auth_header_name: str
    auth_api_keys: list[str]
    auth_bearer_tokens: list[str]
    docs_enabled: bool
    docs_swagger_path: str
    docs_openapi_path: str
    docs_redoc_path: str
    docs_acl_enabled: bool
    docs_allow_ips: list[str]
    docs_allow_cidrs: list[str]
    docs_trust_x_forwarded_for: bool
    docs_auth_enabled: bool
    docs_auth_type: str
    docs_auth_username: str
    docs_auth_password: str
    docs_auth_header_name: str
    docs_auth_api_key: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}


def load_upload_config() -> UploadConfig:
    defaults = UploadConfig(
        upload_dir=Path("uploads/files"),
        chunk_dir=Path("uploads/chunks"),
        max_file_size_mb=51200,
        default_chunk_size_mb=10,
        min_chunk_size_mb=2,
        max_chunk_size_mb=32,
        max_concurrency=3,
        auto_chunk_enabled=True,
        auto_chunk_default_enabled=False,
        high_concurrency_threshold=20,
        mem_budget_per_upload_mb=32,
    )
    data = _load_yaml(UPLOAD_CONFIG_PATH)

    storage = data.get("storage", {}) or {}
    limits = data.get("limits", {}) or {}
    chunking = data.get("chunking", {}) or {}
    auto_chunk = data.get("autoChunk", {}) or {}

    upload_dir = str(storage.get("uploadDir", str(defaults.upload_dir))).strip()
    chunk_dir = str(storage.get("tempDir", str(defaults.chunk_dir))).strip()

    return UploadConfig(
        upload_dir=Path(upload_dir),
        chunk_dir=Path(chunk_dir),
        max_file_size_mb=int(limits.get("maxFileSizeMB", defaults.max_file_size_mb)),
        default_chunk_size_mb=int(chunking.get("defaultChunkSizeMB", defaults.default_chunk_size_mb)),
        min_chunk_size_mb=int(chunking.get("minChunkSizeMB", defaults.min_chunk_size_mb)),
        max_chunk_size_mb=int(chunking.get("maxChunkSizeMB", defaults.max_chunk_size_mb)),
        max_concurrency=int(chunking.get("maxConcurrency", defaults.max_concurrency)),
        auto_chunk_enabled=bool(auto_chunk.get("enabled", defaults.auto_chunk_enabled)),
        auto_chunk_default_enabled=bool(auto_chunk.get("defaultEnabled", defaults.auto_chunk_default_enabled)),
        high_concurrency_threshold=int(
            auto_chunk.get("highConcurrencyThreshold", defaults.high_concurrency_threshold)
        ),
        mem_budget_per_upload_mb=int(auto_chunk.get("memBudgetPerUploadMB", defaults.mem_budget_per_upload_mb)),
    )


def load_api_config() -> ApiConfig:
    defaults = ApiConfig(
        base_path="/api",
        default_version="v1",
        supported_versions=["v1"],
        enable_versionless_alias=True,
        pagination_default_limit=50,
        pagination_hard_cap=500,
        pagination_target_response_bytes=2 * 1024 * 1024,
        socketio_ping_interval=25,
        socketio_ping_timeout=120,
        socketio_cors_allowed_origins="*",
    )
    data = _load_yaml(API_CONFIG_PATH)

    api = data.get("api", {}) or {}
    pagination = data.get("pagination", {}) or {}
    socketio_conf = data.get("socketio", {}) or {}
    supported_versions = api.get("supported_versions", defaults.supported_versions)
    if not isinstance(supported_versions, list) or not supported_versions:
        supported_versions = defaults.supported_versions

    return ApiConfig(
        base_path=str(api.get("base_path", defaults.base_path)).strip() or defaults.base_path,
        default_version=str(api.get("default_version", defaults.default_version)).strip() or defaults.default_version,
        supported_versions=[str(v).strip() for v in supported_versions if str(v).strip()] or defaults.supported_versions,
        enable_versionless_alias=bool(api.get("enable_versionless_alias", defaults.enable_versionless_alias)),
        pagination_default_limit=int(pagination.get("default_limit", defaults.pagination_default_limit)),
        pagination_hard_cap=int(pagination.get("hard_cap", defaults.pagination_hard_cap)),
        pagination_target_response_bytes=int(
            pagination.get("target_response_bytes", defaults.pagination_target_response_bytes)
        ),
        socketio_ping_interval=int(socketio_conf.get("ping_interval", defaults.socketio_ping_interval)),
        socketio_ping_timeout=int(socketio_conf.get("ping_timeout", defaults.socketio_ping_timeout)),
        socketio_cors_allowed_origins=socketio_conf.get(
            "cors_allowed_origins",
            defaults.socketio_cors_allowed_origins,
        ),
    )


def load_security_config() -> SecurityConfig:
    defaults = SecurityConfig(
        auth_enabled=False,
        auth_mode="api_key",
        auth_header_name="X-API-Key",
        auth_api_keys=[],
        auth_bearer_tokens=[],
        docs_enabled=True,
        docs_swagger_path="/docs",
        docs_openapi_path="/openapi.json",
        docs_redoc_path="/redoc",
        docs_acl_enabled=True,
        docs_allow_ips=["127.0.0.1", "::1"],
        docs_allow_cidrs=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
        docs_trust_x_forwarded_for=False,
        docs_auth_enabled=False,
        docs_auth_type="basic",
        docs_auth_username="admin",
        docs_auth_password="change-me",
        docs_auth_header_name="X-Docs-Key",
        docs_auth_api_key="change-me",
    )
    data = _load_yaml(SECURITY_CONFIG_PATH)

    auth = data.get("auth", {}) or {}
    docs = data.get("docs", {}) or {}
    docs_paths = docs.get("paths", {}) or {}
    docs_acl = docs.get("access_control", {}) or {}
    docs_auth = docs.get("auth", {}) or {}

    keys_raw = auth.get("keys", [])
    api_keys: list[str] = []
    if isinstance(keys_raw, list):
        for item in keys_raw:
            if isinstance(item, dict):
                key_value = str(item.get("key_value", "")).strip()
                if key_value:
                    api_keys.append(key_value)
            else:
                key_value = str(item).strip()
                if key_value:
                    api_keys.append(key_value)

    tokens_raw = auth.get("bearer_tokens", [])
    bearer_tokens = [str(v).strip() for v in tokens_raw if str(v).strip()] if isinstance(tokens_raw, list) else []

    return SecurityConfig(
        auth_enabled=bool(auth.get("enabled", defaults.auth_enabled)),
        auth_mode=str(auth.get("mode", defaults.auth_mode)).strip() or defaults.auth_mode,
        auth_header_name=str(auth.get("headerName", defaults.auth_header_name)).strip() or defaults.auth_header_name,
        auth_api_keys=api_keys,
        auth_bearer_tokens=bearer_tokens,
        docs_enabled=bool(docs.get("enabled", defaults.docs_enabled)),
        docs_swagger_path=str(docs_paths.get("swagger_ui", defaults.docs_swagger_path)).strip() or defaults.docs_swagger_path,
        docs_openapi_path=str(docs_paths.get("openapi_json", defaults.docs_openapi_path)).strip()
        or defaults.docs_openapi_path,
        docs_redoc_path=str(docs_paths.get("redoc", defaults.docs_redoc_path)).strip() or defaults.docs_redoc_path,
        docs_acl_enabled=bool(docs_acl.get("enabled", defaults.docs_acl_enabled)),
        docs_allow_ips=[str(v).strip() for v in docs_acl.get("allow_ips", defaults.docs_allow_ips) if str(v).strip()],
        docs_allow_cidrs=[
            str(v).strip() for v in docs_acl.get("allow_cidrs", defaults.docs_allow_cidrs) if str(v).strip()
        ],
        docs_trust_x_forwarded_for=bool(
            docs_acl.get("trust_x_forwarded_for", defaults.docs_trust_x_forwarded_for)
        ),
        docs_auth_enabled=bool(docs_auth.get("enabled", defaults.docs_auth_enabled)),
        docs_auth_type=str(docs_auth.get("type", defaults.docs_auth_type)).strip() or defaults.docs_auth_type,
        docs_auth_username=str(docs_auth.get("username", defaults.docs_auth_username)).strip() or defaults.docs_auth_username,
        docs_auth_password=str(docs_auth.get("password", defaults.docs_auth_password)),
        docs_auth_header_name=str(docs_auth.get("header_name", defaults.docs_auth_header_name)).strip()
        or defaults.docs_auth_header_name,
        docs_auth_api_key=str(docs_auth.get("api_key", defaults.docs_auth_api_key)).strip()
        or defaults.docs_auth_api_key,
    )


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


@dataclass
class Message:
    msg_id: str
    user: str
    text: str
    ts: str
    kind: str = "text"
    file: dict | None = None
    attachments: list[dict] | None = None
    client_msg_id: str | None = None
    created_at: str = ""


messages: List[Message] = []
clients: Dict[str, str] = {}
terminal_sessions: Dict[str, dict] = {}
sid_to_terminal_session: Dict[str, str] = {}
upload_sessions: Dict[str, dict] = {}
uploaded_files: Dict[str, dict] = {}

_clients_lock = Lock()


@app.after_request
def disable_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _clean_upload_dirs() -> None:
    for path in (UPLOAD_CONFIG.upload_dir, UPLOAD_CONFIG.chunk_dir):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)


_clean_upload_dirs()
atexit.register(_clean_upload_dirs)


def _api_response(*, code: int, message: str, data: dict | list | None, status: int):
    return jsonify({"code": code, "message": message, "data": data}), status


def api_ok(data: dict | list | None = None, status: int = 200):
    return _api_response(code=0, message="ok", data=data, status=status)


def api_error(message: str, status: int, code: int = 1):
    return _api_response(code=code, message=message, data=None, status=status)


def _normalize_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _versioned_paths(path_suffix: str) -> list[str]:
    suffix = path_suffix if path_suffix.startswith("/") else f"/{path_suffix}"
    base = API_CONFIG.base_path.rstrip("/")
    version = API_CONFIG.default_version.strip("/")

    paths = [f"{base}/{version}{suffix}"]
    if API_CONFIG.enable_versionless_alias:
        paths.append(f"{base}{suffix}")

    unique_paths: list[str] = []
    for path in paths:
        if path not in unique_paths:
            unique_paths.append(path)
    return unique_paths


def register_api_route(path_suffix: str, methods: list[str], view_func, endpoint_prefix: str) -> None:
    for idx, path in enumerate(_versioned_paths(path_suffix)):
        app.add_url_rule(
            path,
            endpoint=f"{endpoint_prefix}_{idx}",
            view_func=view_func,
            methods=methods,
        )


def _download_path_for(file_id: str, versioned: bool = True) -> str:
    base = API_CONFIG.base_path.rstrip("/")
    if versioned:
        return f"{base}/{API_CONFIG.default_version}/download/{file_id}"
    return f"{base}/download/{file_id}"


def _choose_chunk_size(expected_size: int | None = None) -> int:
    chunk_size = UPLOAD_CONFIG.default_chunk_size_bytes
    if expected_size is not None and expected_size > 0:
        if expected_size < 100 * 1024 * 1024:
            chunk_size = 4 * 1024 * 1024
        elif expected_size > 1024 * 1024 * 1024:
            chunk_size = 16 * 1024 * 1024

    active_uploads = len(upload_sessions)
    if active_uploads >= UPLOAD_CONFIG.high_concurrency_threshold:
        chunk_size = max(4 * 1024 * 1024, chunk_size // 2)

    mem_cap = max(UPLOAD_CONFIG.min_chunk_size_bytes, UPLOAD_CONFIG.mem_budget_per_upload_bytes // 2)
    chunk_size = min(chunk_size, mem_cap)
    chunk_size = max(chunk_size, UPLOAD_CONFIG.min_chunk_size_bytes)
    chunk_size = min(chunk_size, UPLOAD_CONFIG.max_chunk_size_bytes)
    return chunk_size


def _save_stream_to_file(stream, destination: Path) -> int:
    total = 0
    with destination.open("wb") as output:
        while True:
            data = stream.read(1024 * 1024)
            if not data:
                break
            total += len(data)
            if total > UPLOAD_CONFIG.max_file_size_bytes:
                raise ValueError("file too large")
            output.write(data)
    return total


def _save_stream_as_chunks(stream, upload_id: str, expected_size: int | None = None) -> tuple[int, int]:
    chunk_size = _choose_chunk_size(expected_size)
    chunk_dir = UPLOAD_CONFIG.chunk_dir / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    total_chunks = 0
    while True:
        data = stream.read(chunk_size)
        if not data:
            break
        total_bytes += len(data)
        if total_bytes > UPLOAD_CONFIG.max_file_size_bytes:
            raise ValueError("file too large")
        chunk_path = chunk_dir / f"chunk_{total_chunks:06d}.part"
        with chunk_path.open("wb") as output:
            output.write(data)
        total_chunks += 1

    return total_chunks, total_bytes


def _merge_chunks(upload_id: str, total_chunks: int, destination: Path) -> int:
    chunk_dir = UPLOAD_CONFIG.chunk_dir / upload_id
    if not chunk_dir.exists():
        raise FileNotFoundError("chunk directory not found")

    bytes_written = 0
    tmp_destination = destination.with_suffix(destination.suffix + ".tmp")
    with tmp_destination.open("wb") as output:
        for index in range(total_chunks):
            chunk_path = chunk_dir / f"chunk_{index:06d}.part"
            if not chunk_path.exists():
                raise FileNotFoundError(f"missing chunk {index}")
            with chunk_path.open("rb") as chunk_file:
                while True:
                    data = chunk_file.read(1024 * 1024)
                    if not data:
                        break
                    bytes_written += len(data)
                    if bytes_written > UPLOAD_CONFIG.max_file_size_bytes:
                        raise ValueError("file too large")
                    output.write(data)

    tmp_destination.replace(destination)

    for chunk_path in chunk_dir.glob("chunk_*.part"):
        chunk_path.unlink(missing_ok=True)
    chunk_dir.rmdir()
    return bytes_written


def _store_uploaded_file(
    *,
    file_id: str,
    original_name: str,
    stored_name: str,
    size: int,
    mime: str,
    client_msg_id: str,
) -> dict:
    media_url = f"/media/{file_id}"
    download_url = _download_path_for(file_id, versioned=True)
    entry = {
        "file_id": file_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "size": size,
        "mime": mime,
        "uploaded_at": _utc_now_iso(),
        "client_msg_id": client_msg_id,
        # Legacy UI preview uses file.url directly, so keep inline media URL here.
        "url": media_url,
        "download_url": download_url,
        "alias_url": _download_path_for(file_id, versioned=False),
    }
    uploaded_files[file_id] = entry
    return entry


def _serialize_attachment(entry: dict) -> dict:
    return {
        "file_id": entry.get("file_id"),
        "filename": entry.get("original_name"),
        "size": entry.get("size"),
        "mime_type": entry.get("mime"),
        "url": entry.get("download_url")
        or _download_path_for(entry.get("file_id", ""), versioned=True),
    }


def _serialize_message(message: Message) -> dict:
    attachments = []
    source = message.attachments or ([] if message.file is None else [message.file])
    for entry in source:
        attachments.append(_serialize_attachment(entry))

    return {
        "id": message.msg_id,
        "user": message.user,
        "text": message.text,
        "kind": message.kind,
        "created_at": message.created_at,
        "attachments": attachments,
        "client_msg_id": message.client_msg_id,
    }


def _append_message(
    *,
    user: str,
    text: str,
    kind: str,
    attachments: list[dict] | None = None,
    client_msg_id: str | None = None,
    broadcast: bool = True,
) -> Message:
    msg = Message(
        msg_id=f"{int(time.time() * 1000)}-{uuid4().hex[:8]}",
        user=user,
        text=text,
        ts=time.strftime("%H:%M:%S"),
        kind=kind,
        file=(attachments[0] if attachments else None),
        attachments=attachments,
        client_msg_id=client_msg_id,
        created_at=_utc_now_iso(),
    )
    messages.append(msg)
    if broadcast:
        socketio.emit("message", asdict(msg))
    return msg


def _default_username() -> str:
    terminal_session_id = session.get("terminal_session_id")
    if terminal_session_id and terminal_session_id in terminal_sessions:
        return terminal_sessions[terminal_session_id].get("username", "Anonymous")
    return "Anonymous"


def _parse_utc(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _send_entry(entry: dict, *, as_attachment: bool):
    file_path = UPLOAD_CONFIG.upload_dir / entry["stored_name"]
    if not file_path.exists():
        return api_error("file not found", 404, 40401)

    return send_file(
        file_path,
        mimetype=entry.get("mime") or None,
        as_attachment=as_attachment,
        download_name=entry.get("original_name"),
        conditional=True,
    )


def append_client_log(payload: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with CLIENT_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _client_names() -> list[str]:
    with _clients_lock:
        return list(clients.values())


def emit_clients() -> None:
    socketio.emit("clients", _client_names())


def _request_ip() -> str:
    if SECURITY_CONFIG.docs_trust_x_forwarded_for:
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded_for:
            return forwarded_for
    return request.remote_addr or ""


def _docs_access_allowed() -> tuple[bool, tuple | None]:
    if not SECURITY_CONFIG.docs_enabled:
        return False, ("Not Found", 404)

    if SECURITY_CONFIG.docs_acl_enabled:
        ip_raw = _request_ip()
        try:
            ip_obj = ipaddress.ip_address(ip_raw)
        except ValueError:
            return False, ("Forbidden", 403)

        allowed = ip_raw in SECURITY_CONFIG.docs_allow_ips
        if not allowed:
            for cidr in SECURITY_CONFIG.docs_allow_cidrs:
                try:
                    if ip_obj in ipaddress.ip_network(cidr, strict=False):
                        allowed = True
                        break
                except ValueError:
                    continue

        if not allowed:
            return False, ("Forbidden", 403)

    if SECURITY_CONFIG.docs_auth_enabled:
        if SECURITY_CONFIG.docs_auth_type == "basic":
            auth = request.authorization
            if (
                not auth
                or auth.username != SECURITY_CONFIG.docs_auth_username
                or auth.password != SECURITY_CONFIG.docs_auth_password
            ):
                return False, ("Unauthorized", 401, {"WWW-Authenticate": "Basic realm=docs"})
        elif SECURITY_CONFIG.docs_auth_type == "api_key":
            provided = request.headers.get(SECURITY_CONFIG.docs_auth_header_name, "")
            if provided != SECURITY_CONFIG.docs_auth_api_key:
                return False, ("Unauthorized", 401)

    return True, None


@app.before_request
def enforce_api_auth():
    if not SECURITY_CONFIG.auth_enabled:
        return None

    path = request.path
    if not path.startswith(API_CONFIG.base_path.rstrip("/") + "/"):
        return None

    if path in {
        SECURITY_CONFIG.docs_openapi_path,
        SECURITY_CONFIG.docs_swagger_path,
        SECURITY_CONFIG.docs_redoc_path,
    }:
        return None

    if SECURITY_CONFIG.auth_mode == "none":
        return None

    if SECURITY_CONFIG.auth_mode == "api_key":
        provided = request.headers.get(SECURITY_CONFIG.auth_header_name, "").strip()
        if provided and provided in SECURITY_CONFIG.auth_api_keys:
            return None
        return api_error("unauthorized", 401, 40100)

    if SECURITY_CONFIG.auth_mode == "bearer":
        header = request.headers.get("Authorization", "").strip()
        if header.startswith("Bearer "):
            token = header[len("Bearer ") :].strip()
            if token and token in SECURITY_CONFIG.auth_bearer_tokens:
                return None
        return api_error("unauthorized", 401, 40100)

    return api_error("unauthorized", 401, 40100)


@app.route("/")
def index() -> str:
    if "terminal_session_id" not in session:
        session["terminal_session_id"] = str(uuid4())
    return render_template("index.html")


@app.get("/media/<file_id>")
def legacy_media(file_id: str):
    entry = uploaded_files.get(file_id)
    if not entry:
        return "Not Found", 404
    as_attachment = request.args.get("download") == "1"
    return _send_entry(entry, as_attachment=as_attachment)


def handle_get_messages():
    limit_raw = request.args.get("limit", str(API_CONFIG.pagination_default_limit)).strip()
    cursor_raw = request.args.get("cursor", "0").strip() or "0"
    since_raw = request.args.get("since", "").strip()

    try:
        limit = int(limit_raw)
        cursor = int(cursor_raw)
    except ValueError:
        return api_error("invalid pagination parameters", 400, 40001)

    if limit <= 0:
        return api_error("limit must be positive", 400, 40002)

    limit = min(limit, API_CONFIG.pagination_hard_cap)
    cursor = max(cursor, 0)

    filtered = messages
    if since_raw:
        since_dt = _parse_utc(since_raw)
        if since_dt is None:
            return api_error("invalid since timestamp", 400, 40003)
        filtered = [m for m in filtered if _parse_utc(m.created_at or "") and _parse_utc(m.created_at) >= since_dt]

    total = len(filtered)
    end = min(cursor + limit, total)
    page = filtered[cursor:end]

    next_cursor = str(end) if end < total else None
    payload = {
        "items": [_serialize_message(msg) for msg in page],
        "next_cursor": next_cursor,
        "limit": limit,
        "total": total,
    }
    return api_ok(payload)


def handle_post_messages():
    data = request.get_json(silent=True) or {}
    user = (data.get("user") or "").strip() or _default_username()
    text = (data.get("text") or "").strip()
    client_msg_id = (data.get("client_msg_id") or "").strip() or None
    attachment_ids_raw = data.get("attachment_ids") or []

    if not isinstance(attachment_ids_raw, list):
        return api_error("attachment_ids must be an array", 400, 40004)

    attachment_ids = [str(v).strip() for v in attachment_ids_raw if str(v).strip()]
    attachments: list[dict] = []
    for file_id in attachment_ids:
        entry = uploaded_files.get(file_id)
        if not entry:
            return api_error(f"attachment not found: {file_id}", 404, 40402)
        attachments.append(entry)

    if not text and not attachments:
        return api_error("text or attachment_ids is required", 400, 40005)

    kind = "text"
    if attachments and text:
        kind = "mixed"
    elif attachments:
        kind = "file"

    msg = _append_message(
        user=user,
        text=text,
        kind=kind,
        attachments=attachments or None,
        client_msg_id=client_msg_id,
        broadcast=True,
    )
    return api_ok({"message": _serialize_message(msg)}, status=201)


def handle_upload_init():
    data = request.get_json(silent=True) or {}
    filename = (data.get("filename") or "").strip()
    mime = (data.get("mime") or data.get("mime_type") or "").strip()
    client_msg_id = (data.get("client_msg_id") or "").strip()

    try:
        size = int(data.get("size") or 0)
    except (TypeError, ValueError):
        return api_error("invalid file size", 400, 40006)

    if not filename or size <= 0:
        return api_error("filename and size are required", 400, 40007)
    if size > UPLOAD_CONFIG.max_file_size_bytes:
        return api_error("file too large", 413, 41301)

    upload_id = str(uuid4())
    upload_sessions[upload_id] = {
        "filename": filename,
        "size": size,
        "mime": mime,
        "client_msg_id": client_msg_id,
        "created_at": _utc_now_iso(),
    }
    (UPLOAD_CONFIG.chunk_dir / upload_id).mkdir(parents=True, exist_ok=True)

    return api_ok(
        {
            "upload_id": upload_id,
            "chunk_size": _choose_chunk_size(size),
            "max_concurrency": UPLOAD_CONFIG.max_concurrency,
            "max_file_size_bytes": UPLOAD_CONFIG.max_file_size_bytes,
        }
    )


def handle_upload_chunk():
    upload_id = (request.form.get("upload_id") or "").strip()
    index_raw = (request.form.get("index") or "").strip()
    total_raw = (request.form.get("total_chunks") or "").strip()
    chunk_file = request.files.get("chunk")

    if not upload_id or upload_id not in upload_sessions:
        return api_error("upload session not found", 404, 40403)
    if not chunk_file or not index_raw or not total_raw:
        return api_error("invalid chunk request", 400, 40008)

    try:
        index = int(index_raw)
        total_chunks = int(total_raw)
    except ValueError:
        return api_error("invalid chunk index", 400, 40009)

    if index < 0 or total_chunks <= 0 or index >= total_chunks:
        return api_error("chunk index out of range", 400, 40010)

    chunk_dir = UPLOAD_CONFIG.chunk_dir / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"chunk_{index:06d}.part"

    with chunk_path.open("wb") as output:
        chunk_file.stream.seek(0)
        while True:
            data = chunk_file.stream.read(1024 * 1024)
            if not data:
                break
            output.write(data)

    return api_ok({"upload_id": upload_id, "index": index})


def handle_upload_complete():
    data = request.get_json(silent=True) or {}
    upload_id = (data.get("upload_id") or "").strip()

    try:
        total_chunks = int(data.get("total_chunks") or 0)
    except (TypeError, ValueError):
        return api_error("invalid total_chunks", 400, 40011)

    if not upload_id or upload_id not in upload_sessions:
        return api_error("upload session not found", 404, 40403)
    if total_chunks <= 0:
        return api_error("total_chunks must be positive", 400, 40012)

    session_info = upload_sessions.pop(upload_id)
    safe_name = secure_filename(session_info["filename"]) or f"{upload_id}.bin"
    stored_name = f"{upload_id}_{safe_name}"
    final_path = UPLOAD_CONFIG.upload_dir / stored_name

    try:
        merged_bytes = _merge_chunks(upload_id, total_chunks, final_path)
    except FileNotFoundError as exc:
        return api_error(str(exc), 400, 40013)
    except ValueError:
        return api_error("file too large", 413, 41301)

    declared_size = int(session_info.get("size") or 0)
    if declared_size > 0 and merged_bytes != declared_size:
        final_path.unlink(missing_ok=True)
        return api_error("merged size does not match declared size", 400, 40014)

    entry = _store_uploaded_file(
        file_id=upload_id,
        original_name=session_info["filename"],
        stored_name=stored_name,
        size=merged_bytes,
        mime=session_info.get("mime") or "",
        client_msg_id=session_info.get("client_msg_id") or "",
    )

    msg = _append_message(
        user=_default_username(),
        text=entry["original_name"],
        kind="file",
        attachments=[entry],
        client_msg_id=entry.get("client_msg_id") or None,
        broadcast=True,
    )

    return api_ok({"file": _serialize_attachment(entry), "message": _serialize_message(msg)})


def handle_upload_auto():
    upload_file = request.files.get("file")
    if not upload_file:
        return api_error("file is required", 400, 40015)

    chunked = _normalize_bool(request.form.get("chunked"), UPLOAD_CONFIG.auto_chunk_default_enabled)
    if chunked and not UPLOAD_CONFIG.auto_chunk_enabled:
        return api_error("auto chunk upload is disabled", 400, 40016)

    create_message = _normalize_bool(request.form.get("create_message"), False)
    client_msg_id = (request.form.get("client_msg_id") or "").strip()
    mime = (upload_file.mimetype or request.form.get("mime_type") or "").strip()
    expected_size = upload_file.content_length if upload_file.content_length and upload_file.content_length > 0 else None

    file_id = str(uuid4())
    safe_name = secure_filename(upload_file.filename or "") or f"{file_id}.bin"
    stored_name = f"{file_id}_{safe_name}"
    final_path = UPLOAD_CONFIG.upload_dir / stored_name

    try:
        if chunked:
            total_chunks, bytes_written = _save_stream_as_chunks(upload_file.stream, file_id, expected_size)
            if total_chunks == 0:
                return api_error("empty file", 400, 40017)
            merged_bytes = _merge_chunks(file_id, total_chunks, final_path)
            if merged_bytes != bytes_written:
                final_path.unlink(missing_ok=True)
                return api_error("merge verification failed", 500, 50001)
            actual_size = merged_bytes
        else:
            actual_size = _save_stream_to_file(upload_file.stream, final_path)
            if actual_size <= 0:
                final_path.unlink(missing_ok=True)
                return api_error("empty file", 400, 40017)
    except ValueError:
        final_path.unlink(missing_ok=True)
        return api_error("file too large", 413, 41301)

    entry = _store_uploaded_file(
        file_id=file_id,
        original_name=upload_file.filename or safe_name,
        stored_name=stored_name,
        size=actual_size,
        mime=mime,
        client_msg_id=client_msg_id,
    )

    if create_message:
        _append_message(
            user=_default_username(),
            text=entry["original_name"],
            kind="file",
            attachments=[entry],
            client_msg_id=client_msg_id or None,
            broadcast=True,
        )

    return api_ok(
        {
            "file": _serialize_attachment(entry),
            "upload": {
                "chunked": chunked,
                "chunk_size": _choose_chunk_size(expected_size),
            },
        },
        status=201,
    )


def handle_download(file_id: str):
    entry = uploaded_files.get(file_id)
    if not entry:
        return api_error("file not found", 404, 40401)

    inline = _normalize_bool(request.args.get("inline"), False)
    return _send_entry(entry, as_attachment=not inline)


def _openapi_spec() -> dict:
    base = API_CONFIG.base_path.rstrip("/")
    version = API_CONFIG.default_version
    api_root = f"{base}/{version}"

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "MyFileHelper API",
            "version": version,
            "description": "Versionless aliases are enabled. Example: /api/messages == /api/v1/messages",
        },
        "paths": {
            f"{api_root}/messages": {
                "get": {
                    "summary": "List messages",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                        {"name": "cursor", "in": "query", "schema": {"type": "integer", "default": 0}},
                        {"name": "since", "in": "query", "schema": {"type": "string", "format": "date-time"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                },
                "post": {
                    "summary": "Send message",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user": {"type": "string"},
                                        "text": {"type": "string"},
                                        "attachment_ids": {"type": "array", "items": {"type": "string"}},
                                        "client_msg_id": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                },
            },
            f"{api_root}/upload": {
                "post": {
                    "summary": "Auto upload file",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "file": {"type": "string", "format": "binary"},
                                        "chunked": {"type": "boolean", "default": False},
                                        "create_message": {"type": "boolean", "default": False},
                                        "client_msg_id": {"type": "string"},
                                    },
                                    "required": ["file"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/upload/init": {
                "post": {
                    "summary": "Init chunk upload",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/upload/chunk": {
                "post": {
                    "summary": "Upload chunk",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/upload/complete": {
                "post": {
                    "summary": "Complete chunk upload",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/download/{{file_id}}": {
                "get": {
                    "summary": "Download file",
                    "parameters": [
                        {"name": "file_id", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "inline", "in": "query", "schema": {"type": "boolean", "default": False}},
                    ],
                    "responses": {"200": {"description": "File stream"}},
                }
            },
        },
        "components": {
            "schemas": {
                "ApiResponse": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "integer"},
                        "message": {"type": "string"},
                        "data": {"type": "object", "nullable": True},
                    },
                }
            }
        },
    }


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
    append_client_log(entry)
    return "", 204


@app.get("/__health")
def healthcheck():
    return api_ok({"status": "ok", "version": API_CONFIG.default_version})


@app.get(SECURITY_CONFIG.docs_openapi_path)
def openapi_json():
    allowed, response = _docs_access_allowed()
    if not allowed:
        return response
    return jsonify(_openapi_spec())


@app.get(SECURITY_CONFIG.docs_swagger_path)
def swagger_ui():
    allowed, response = _docs_access_allowed()
    if not allowed:
        return response

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>MyFileHelper API Docs</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\" />
</head>
<body>
  <div id=\"swagger-ui\"></div>
  <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: '{SECURITY_CONFIG.docs_openapi_path}',
      dom_id: '#swagger-ui'
    }});
  </script>
</body>
</html>
"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get(SECURITY_CONFIG.docs_redoc_path)
def redoc_ui():
    allowed, response = _docs_access_allowed()
    if not allowed:
        return response

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>MyFileHelper ReDoc</title>
  <script src=\"https://unpkg.com/redoc@next/bundles/redoc.standalone.js\"></script>
</head>
<body>
  <redoc spec-url=\"{SECURITY_CONFIG.docs_openapi_path}\"></redoc>
</body>
</html>
"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


register_api_route("/messages", ["GET"], handle_get_messages, "api_messages_get")
register_api_route("/messages", ["POST"], handle_post_messages, "api_messages_post")
register_api_route("/upload", ["POST"], handle_upload_auto, "api_upload_auto")
register_api_route("/upload/init", ["POST"], handle_upload_init, "api_upload_init")
register_api_route("/upload/chunk", ["POST"], handle_upload_chunk, "api_upload_chunk")
register_api_route("/upload/complete", ["POST"], handle_upload_complete, "api_upload_complete")
register_api_route("/download/<file_id>", ["GET"], handle_download, "api_download")
register_api_route("/client-log", ["POST"], handle_client_log, "api_client_log")


@socketio.on("register")
def handle_register(data: dict) -> dict:
    username = ((data or {}).get("username") or "").strip()
    if not username:
        return {"ok": False, "error": "terminal name cannot be empty"}

    if len(username) > 24:
        return {"ok": False, "error": "terminal name cannot be longer than 24 characters"}

    terminal_session_id = session.get("terminal_session_id")
    if not terminal_session_id:
        terminal_session_id = str(uuid4())
        session["terminal_session_id"] = terminal_session_id

    with _clients_lock:
        terminal_record = terminal_sessions.setdefault(
            terminal_session_id,
            {"username": username, "sids": set()},
        )
        terminal_record["username"] = username
        terminal_record["sids"].add(request.sid)

        sid_to_terminal_session[request.sid] = terminal_session_id
        clients[request.sid] = username

    emit("history", [asdict(m) for m in messages])
    emit_clients()
    return {"ok": True}


@socketio.on("message")
def handle_message(data: dict) -> None:
    text = (data or {}).get("text", "").strip()
    if not text:
        return
    username = clients.get(request.sid, "Anonymous")
    _append_message(user=username, text=text, kind="text", broadcast=True)


@socketio.on("disconnect")
def handle_disconnect() -> None:
    removed = False
    with _clients_lock:
        if request.sid in clients:
            clients.pop(request.sid, None)
            removed = True

        terminal_session_id = sid_to_terminal_session.pop(request.sid, None)
        if terminal_session_id and terminal_session_id in terminal_sessions:
            terminal_record = terminal_sessions[terminal_session_id]
            terminal_record["sids"].discard(request.sid)
            if not terminal_record["sids"]:
                terminal_sessions.pop(terminal_session_id, None)

    if removed:
        emit_clients()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=80, debug=True, allow_unsafe_werkzeug=True)
