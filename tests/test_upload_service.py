from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from modules.error_codes import UPLOAD_EMPTY_FILE, UPLOAD_FILE_TOO_LARGE, UPLOAD_MERGE_VERIFICATION_FAILED
from modules.state import AppState
from modules.upload_service import map_auto_upload_error, orchestrate_auto_upload, serialize_attachment
from modules.upload_storage import (
    choose_chunk_size,
    create_upload_session,
    merge_chunks,
    save_stream_as_chunks,
    save_stream_to_file,
    save_upload_chunk,
)
from modules.upload_service import finalize_upload_session, store_auto_uploaded_file


def _cfg(tmp_path=None, *, max_file_size_bytes: int = 1024 * 1024) -> SimpleNamespace:
    base_dir = tmp_path if tmp_path is not None else None
    upload_dir = (base_dir / "files") if base_dir is not None else None
    chunk_dir = (base_dir / "chunks") if base_dir is not None else None
    if upload_dir is not None:
        upload_dir.mkdir(parents=True, exist_ok=True)
    if chunk_dir is not None:
        chunk_dir.mkdir(parents=True, exist_ok=True)

    return SimpleNamespace(
        upload_dir=upload_dir,
        chunk_dir=chunk_dir,
        default_chunk_size_bytes=8 * 1024 * 1024,
        high_concurrency_threshold=10,
        min_chunk_size_bytes=2 * 1024 * 1024,
        max_chunk_size_bytes=32 * 1024 * 1024,
        mem_budget_per_upload_bytes=20 * 1024 * 1024,
        max_file_size_bytes=max_file_size_bytes,
        max_concurrency=4,
    )


class DummySocketIO:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def emit(self, event: str, payload: object) -> None:
        self.events.append((event, payload))


def test_choose_chunk_size_prefers_small_for_small_files() -> None:
    size = choose_chunk_size(_cfg(), {}, expected_size=50 * 1024 * 1024)
    assert size == 4 * 1024 * 1024


def test_choose_chunk_size_prefers_large_for_very_big_files() -> None:
    size = choose_chunk_size(_cfg(), {}, expected_size=2 * 1024 * 1024 * 1024)
    assert size == 10 * 1024 * 1024


def test_choose_chunk_size_reduces_on_high_concurrency() -> None:
    sessions = {str(i): {} for i in range(10)}
    size = choose_chunk_size(_cfg(), sessions, expected_size=None)
    assert size == 4 * 1024 * 1024


def test_create_upload_session_initializes_session_state(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    sessions: dict[str, dict] = {}

    payload = create_upload_session(
        cfg,
        sessions,
        filename="a.txt",
        size=10,
        mime="text/plain",
        client_msg_id="abc",
    )

    upload_id = payload["upload_id"]
    assert upload_id in sessions
    assert sessions[upload_id]["filename"] == "a.txt"
    assert (cfg.chunk_dir / upload_id).exists()


def test_save_upload_chunk_persists_data(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    sessions = {"u1": {}}

    payload = save_upload_chunk(
        cfg,
        sessions,
        upload_id="u1",
        index=0,
        total_chunks=1,
        chunk_stream=BytesIO(b"hello"),
    )

    assert payload == {"upload_id": "u1", "index": 0}
    assert (cfg.chunk_dir / "u1" / "chunk_000000.part").read_bytes() == b"hello"


def test_save_stream_to_file_writes_content(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    destination = tmp_path / "file.bin"

    size = save_stream_to_file(BytesIO(b"hello"), destination, cfg)

    assert size == 5
    assert destination.read_bytes() == b"hello"


def test_save_stream_to_file_rejects_oversize(tmp_path) -> None:
    cfg = _cfg(tmp_path, max_file_size_bytes=3)

    with pytest.raises(ValueError, match="file too large"):
        save_stream_to_file(BytesIO(b"hello"), tmp_path / "file.bin", cfg)


def test_save_stream_as_chunks_creates_multiple_parts(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    cfg.default_chunk_size_bytes = 4
    cfg.min_chunk_size_bytes = 1
    cfg.max_chunk_size_bytes = 8
    cfg.mem_budget_per_upload_bytes = 8

    total_chunks, total_bytes = save_stream_as_chunks(
        BytesIO(b"abcdef"),
        "u2",
        cfg,
        {},
        expected_size=200 * 1024 * 1024,
    )

    assert total_chunks == 2
    assert total_bytes == 6
    assert (cfg.chunk_dir / "u2" / "chunk_000000.part").read_bytes() == b"abcd"
    assert (cfg.chunk_dir / "u2" / "chunk_000001.part").read_bytes() == b"ef"


def test_merge_chunks_merges_and_cleans_up(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    chunk_dir = cfg.chunk_dir / "u3"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / "chunk_000000.part").write_bytes(b"ab")
    (chunk_dir / "chunk_000001.part").write_bytes(b"cd")
    destination = cfg.upload_dir / "merged.bin"

    size = merge_chunks("u3", 2, destination, cfg)

    assert size == 4
    assert destination.read_bytes() == b"abcd"
    assert not chunk_dir.exists()


def test_merge_chunks_raises_for_missing_chunk(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    chunk_dir = cfg.chunk_dir / "u4"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / "chunk_000000.part").write_bytes(b"ab")

    with pytest.raises(FileNotFoundError, match="missing chunk 1"):
        merge_chunks("u4", 2, cfg.upload_dir / "merged.bin", cfg)


def test_finalize_upload_session_merges_and_stores_entry(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    sessions = {
        "u5": {
            "filename": "hello.txt",
            "size": 4,
            "mime": "text/plain",
            "client_msg_id": "abc",
        }
    }
    uploaded_files: dict[str, dict] = {}
    chunk_dir = cfg.chunk_dir / "u5"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / "chunk_000000.part").write_bytes(b"ab")
    (chunk_dir / "chunk_000001.part").write_bytes(b"cd")

    entry = finalize_upload_session(cfg, sessions, uploaded_files, upload_id="u5", total_chunks=2)

    assert entry["file_id"] == "u5"
    assert entry["stored_name"].endswith("hello.txt")
    assert uploaded_files["u5"]["size"] == 4
    assert not chunk_dir.exists()


def test_store_auto_uploaded_file_direct_success(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    uploaded_files: dict[str, dict] = {}

    entry, chunk_size = store_auto_uploaded_file(
        cfg,
        {},
        uploaded_files,
        upload_stream=BytesIO(b"hello"),
        filename="hello.txt",
        mime="text/plain",
        client_msg_id="abc",
        chunked=False,
    )

    assert entry["original_name"] == "hello.txt"
    assert (cfg.upload_dir / entry["stored_name"]).read_bytes() == b"hello"
    assert chunk_size >= cfg.min_chunk_size_bytes


def test_store_auto_uploaded_file_chunked_success(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    cfg.default_chunk_size_bytes = 4
    cfg.min_chunk_size_bytes = 1
    cfg.max_chunk_size_bytes = 8
    cfg.mem_budget_per_upload_bytes = 8
    uploaded_files: dict[str, dict] = {}

    entry, _chunk_size = store_auto_uploaded_file(
        cfg,
        {},
        uploaded_files,
        upload_stream=BytesIO(b"abcdef"),
        filename="hello.txt",
        mime="text/plain",
        client_msg_id="abc",
        chunked=True,
        expected_size=200 * 1024 * 1024,
    )

    assert (cfg.upload_dir / entry["stored_name"]).read_bytes() == b"abcdef"
    assert not any(cfg.chunk_dir.iterdir())


def test_store_auto_uploaded_file_empty_file_cleans_up(tmp_path) -> None:
    cfg = _cfg(tmp_path)

    with pytest.raises(EOFError, match="empty file"):
        store_auto_uploaded_file(
            cfg,
            {},
            {},
            upload_stream=BytesIO(b""),
            filename="empty.txt",
            mime="text/plain",
            client_msg_id="",
            chunked=False,
        )

    assert list(cfg.upload_dir.iterdir()) == []


def test_serialize_attachment_uses_fallback_urls() -> None:
    payload = serialize_attachment({"file_id": "f1", "original_name": "a.txt", "size": 3, "mime": "text/plain"})

    assert payload["download_url"] == "/media/f1?download=1"
    assert payload["inline_url"] == "/media/f1"


def test_map_auto_upload_error_maps_supported_exceptions() -> None:
    assert map_auto_upload_error(EOFError())[2] == UPLOAD_EMPTY_FILE
    assert map_auto_upload_error(ValueError())[2] == UPLOAD_FILE_TOO_LARGE
    assert map_auto_upload_error(RuntimeError())[2] == UPLOAD_MERGE_VERIFICATION_FAILED


def test_orchestrate_auto_upload_returns_service_error_for_empty_file(tmp_path) -> None:
    with patch("modules.upload_service.store_auto_uploaded_file", side_effect=EOFError):
        result, error = orchestrate_auto_upload(
            _cfg(tmp_path),
            AppState(),
            DummySocketIO(),
            upload_stream=object(),
            filename="a.txt",
            mime="text/plain",
            client_msg_id="",
            chunked=True,
            create_message=False,
            message_user="Anonymous",
        )

    assert result is None
    assert error is not None
    assert error[2] == UPLOAD_EMPTY_FILE


def test_orchestrate_auto_upload_success_with_message_creation(tmp_path) -> None:
    fake_entry = {
        "file_id": "f1",
        "original_name": "a.txt",
        "stored_name": "f1_a.txt",
        "size": 3,
        "mime": "text/plain",
        "url": "/media/f1",
        "download_url": "/media/f1?download=1",
        "alias_url": "/media/f1?download=1",
    }
    state = AppState()

    with (
        patch("modules.upload_service.store_auto_uploaded_file", return_value=(fake_entry, 4096)),
        patch("modules.upload_service.append_message") as append_mock,
    ):
        result, error = orchestrate_auto_upload(
            _cfg(tmp_path),
            state,
            DummySocketIO(),
            upload_stream=object(),
            filename="a.txt",
            mime="text/plain",
            client_msg_id="",
            chunked=True,
            create_message=True,
            message_user="Anonymous",
        )

    assert error is None
    assert result is not None
    assert result["file"]["file_id"] == "f1"
    assert result["upload"]["chunk_size"] == 4096
    append_mock.assert_called_once()


