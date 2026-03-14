from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

LOGGING_CONFIG_PATH = Path("config/logging_config.yaml")


@dataclass
class ClientLogConfig:
    path: Path
    max_bytes: int
    backup_count: int


@dataclass
class LoggingConfig:
    client_log: ClientLogConfig


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}


def load_logging_config() -> LoggingConfig:
    defaults = LoggingConfig(
        client_log=ClientLogConfig(
            path=Path("logs/client.log"),
            max_bytes=10 * 1024 * 1024,
            backup_count=5,
        )
    )
    data = _load_yaml(LOGGING_CONFIG_PATH)
    logging_conf = data.get("logging", {}) or {}
    client_conf = logging_conf.get("client_log", {}) or {}

    path_raw = str(client_conf.get("path", defaults.client_log.path)).strip() or str(defaults.client_log.path)
    max_bytes = int(client_conf.get("max_bytes", defaults.client_log.max_bytes))
    backup_count = int(client_conf.get("backup_count", defaults.client_log.backup_count))

    return LoggingConfig(
        client_log=ClientLogConfig(
            path=Path(path_raw),
            max_bytes=max_bytes,
            backup_count=backup_count,
        )
    )
