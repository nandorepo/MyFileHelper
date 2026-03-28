from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import yaml

LOG_DIR = Path("logs")
CLIENT_LOG_FILE = LOG_DIR / "client.log"
UPLOAD_CONFIG_PATH = Path("config/upload_config.yaml")
SERVER_CONFIG_PATH = Path("config/server_config.yaml")


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
class ClientLogConfig:
    path: Path
    max_bytes: int
    backup_count: int


@dataclass
class ServerConfig:
    pagination_default_limit: int
    pagination_hard_cap: int
    pagination_target_response_bytes: int
    socketio_ping_interval: int
    socketio_ping_timeout: int
    socketio_cors_allowed_origins: str | list[str]
    client_log: ClientLogConfig
    autoindex_enabled: bool
    access_control_enabled: bool
    allowed_networks: list[str]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        logging.getLogger(__name__).warning("failed to load config file %s: %s", path, exc)
        return {}


def _as_bool(raw, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return raw != 0

    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


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
        auto_chunk_enabled=_as_bool(auto_chunk.get("enabled"), defaults.auto_chunk_enabled),
        auto_chunk_default_enabled=_as_bool(auto_chunk.get("defaultEnabled"), defaults.auto_chunk_default_enabled),
        high_concurrency_threshold=int(
            auto_chunk.get("highConcurrencyThreshold", defaults.high_concurrency_threshold)
        ),
        mem_budget_per_upload_mb=int(auto_chunk.get("memBudgetPerUploadMB", defaults.mem_budget_per_upload_mb)),
    )


def load_server_config() -> ServerConfig:
    defaults = ServerConfig(
        pagination_default_limit=50,
        pagination_hard_cap=500,
        pagination_target_response_bytes=2 * 1024 * 1024,
        socketio_ping_interval=25,
        socketio_ping_timeout=120,
        socketio_cors_allowed_origins="*",
        client_log=ClientLogConfig(
            path=Path("logs/client.log"),
            max_bytes=10 * 1024 * 1024,
            backup_count=5,
        ),
        autoindex_enabled=False,
        access_control_enabled=False,
        allowed_networks=[],
    )
    data = _load_yaml(SERVER_CONFIG_PATH)

    pagination = data.get("pagination", {}) or {}
    socketio_conf = data.get("socketio", {}) or {}
    logging_conf = data.get("logging", {}) or {}
    client_conf = logging_conf.get("client_log", {}) or {}

    path_raw = str(client_conf.get("path", defaults.client_log.path)).strip() or str(defaults.client_log.path)
    max_bytes = int(client_conf.get("max_bytes", defaults.client_log.max_bytes))
    backup_count = int(client_conf.get("backup_count", defaults.client_log.backup_count))

    autoindex_conf = data.get("autoindex", {}) or {}
    access_control = data.get("access_control", {}) or {}

    return ServerConfig(
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
        client_log=ClientLogConfig(
            path=Path(path_raw),
            max_bytes=max_bytes,
            backup_count=backup_count,
        ),
        autoindex_enabled=_as_bool(autoindex_conf.get("enabled"), defaults.autoindex_enabled),
        access_control_enabled=_as_bool(access_control.get("enabled"), defaults.access_control_enabled),
        allowed_networks=list(access_control.get("allowed_networks", defaults.allowed_networks) or []),
    )
