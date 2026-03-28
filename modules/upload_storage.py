from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _iter_stream_chunks(stream, read_size: int):
    while True:
        data = stream.read(read_size)
        if not data:
            break
        yield data


def _write_chunk(output, data: bytes, *, bytes_written: int, max_bytes: int | None) -> int:
    bytes_written += len(data)
    if max_bytes is not None and bytes_written > max_bytes:
        raise ValueError("file too large")
    output.write(data)
    return bytes_written


def _copy_stream_to_output(
    stream, output, *, read_size: int, max_bytes: int | None, bytes_written: int = 0
) -> int:
    for data in _iter_stream_chunks(stream, read_size):
        bytes_written = _write_chunk(output, data, bytes_written=bytes_written, max_bytes=max_bytes)
    return bytes_written


def _chunk_path(chunk_dir: Path, index: int) -> Path:
    return chunk_dir / f"chunk_{index:06d}.part"


def _cleanup_chunk_dir(chunk_dir: Path) -> None:
    for chunk_path in chunk_dir.glob("chunk_*.part"):
        chunk_path.unlink(missing_ok=True)
    chunk_dir.rmdir()


def choose_chunk_size(upload_config, upload_sessions: dict, expected_size: int | None = None) -> int:
    chunk_size = upload_config.default_chunk_size_bytes
    if expected_size is not None and expected_size > 0:
        if expected_size < 100 * 1024 * 1024:
            chunk_size = 4 * 1024 * 1024
        elif expected_size > 1024 * 1024 * 1024:
            chunk_size = 16 * 1024 * 1024

    active_uploads = len(upload_sessions)
    if active_uploads >= upload_config.high_concurrency_threshold:
        chunk_size = max(4 * 1024 * 1024, chunk_size // 2)

    mem_cap = max(upload_config.min_chunk_size_bytes, upload_config.mem_budget_per_upload_bytes // 2)
    chunk_size = min(chunk_size, mem_cap)
    chunk_size = max(chunk_size, upload_config.min_chunk_size_bytes)
    chunk_size = min(chunk_size, upload_config.max_chunk_size_bytes)
    return chunk_size


def create_upload_session(
    upload_config,
    upload_sessions: dict,
    *,
    filename: str,
    size: int,
    mime: str,
    client_msg_id: str,
) -> dict:
    upload_id = str(uuid4())
    upload_sessions[upload_id] = {
        "filename": filename,
        "size": size,
        "mime": mime,
        "client_msg_id": client_msg_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    (upload_config.chunk_dir / upload_id).mkdir(parents=True, exist_ok=True)
    return {
        "upload_id": upload_id,
        "chunk_size": choose_chunk_size(upload_config, upload_sessions, size),
        "max_concurrency": upload_config.max_concurrency,
        "max_file_size_bytes": upload_config.max_file_size_bytes,
    }


def save_upload_chunk(
    upload_config,
    upload_sessions: dict,
    *,
    upload_id: str,
    index: int,
    total_chunks: int,
    chunk_stream,
) -> dict:
    if upload_id not in upload_sessions:
        raise KeyError("upload session not found")
    if index < 0 or total_chunks <= 0 or index >= total_chunks:
        raise IndexError("chunk index out of range")

    chunk_dir = upload_config.chunk_dir / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = _chunk_path(chunk_dir, index)

    with chunk_path.open("wb") as output:
        chunk_stream.seek(0)
        _copy_stream_to_output(
            chunk_stream,
            output,
            read_size=1024 * 1024,
            max_bytes=None,
        )

    return {"upload_id": upload_id, "index": index}


def save_stream_to_file(stream, destination: Path, upload_config) -> int:
    with destination.open("wb") as output:
        return _copy_stream_to_output(
            stream,
            output,
            read_size=1024 * 1024,
            max_bytes=upload_config.max_file_size_bytes,
        )


def save_stream_as_chunks(
    stream, upload_id: str, upload_config, upload_sessions: dict, expected_size: int | None = None
) -> tuple[int, int]:
    chunk_size = choose_chunk_size(upload_config, upload_sessions, expected_size)
    chunk_dir = upload_config.chunk_dir / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    total_chunks = 0
    for data in _iter_stream_chunks(stream, chunk_size):
        total_bytes += len(data)
        if total_bytes > upload_config.max_file_size_bytes:
            raise ValueError("file too large")
        chunk_path = _chunk_path(chunk_dir, total_chunks)
        with chunk_path.open("wb") as output:
            output.write(data)
        total_chunks += 1

    return total_chunks, total_bytes


def merge_chunks(upload_id: str, total_chunks: int, destination: Path, upload_config) -> int:
    chunk_dir = upload_config.chunk_dir / upload_id
    if not chunk_dir.exists():
        raise FileNotFoundError("chunk directory not found")

    bytes_written = 0
    tmp_destination = destination.with_suffix(destination.suffix + ".tmp")
    with tmp_destination.open("wb") as output:
        for index in range(total_chunks):
            chunk_path = _chunk_path(chunk_dir, index)
            if not chunk_path.exists():
                raise FileNotFoundError(f"missing chunk {index}")
            with chunk_path.open("rb") as chunk_file:
                bytes_written = _copy_stream_to_output(
                    chunk_file,
                    output,
                    read_size=1024 * 1024,
                    max_bytes=upload_config.max_file_size_bytes,
                    bytes_written=bytes_written,
                )

    tmp_destination.replace(destination)
    _cleanup_chunk_dir(chunk_dir)
    return bytes_written

