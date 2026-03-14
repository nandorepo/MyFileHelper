from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

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
