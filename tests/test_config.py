from __future__ import annotations

from pathlib import Path

import modules.config as config_module


def test_load_upload_config_parses_string_booleans(tmp_path, monkeypatch) -> None:
    cfg_file = tmp_path / "upload.yaml"
    cfg_file.write_text(
        """
storage:
  uploadDir: uploads/files
  tempDir: uploads/chunks
autoChunk:
  enabled: "false"
  defaultEnabled: "true"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "UPLOAD_CONFIG_PATH", Path(cfg_file))

    cfg = config_module.load_upload_config()

    assert cfg.auto_chunk_enabled is False
    assert cfg.auto_chunk_default_enabled is True


def test_load_server_config_parses_string_booleans(tmp_path, monkeypatch) -> None:
    cfg_file = tmp_path / "server.yaml"
    cfg_file.write_text(
        """
autoindex:
  enabled: "false"
access_control:
  enabled: "true"
  allowed_networks:
    - 10.0.0.0/8
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "SERVER_CONFIG_PATH", Path(cfg_file))

    cfg = config_module.load_server_config()

    assert cfg.autoindex_enabled is False
    assert cfg.access_control_enabled is True
    assert cfg.allowed_networks == ["10.0.0.0/8"]


def test_load_server_config_uses_defaults_for_invalid_yaml(tmp_path, monkeypatch) -> None:
    cfg_file = tmp_path / "invalid-server.yaml"
    cfg_file.write_text("invalid: [\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "SERVER_CONFIG_PATH", Path(cfg_file))

    cfg = config_module.load_server_config()

    assert cfg.pagination_default_limit == 50
    assert cfg.socketio_ping_interval == 25
    assert cfg.access_control_enabled is False

