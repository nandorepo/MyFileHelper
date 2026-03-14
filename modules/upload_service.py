from __future__ import annotations

from pathlib import Path

from flask import send_file

from .api_utils import download_path_for, utc_now_iso
from .state import Message


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


def save_stream_to_file(stream, destination: Path, upload_config) -> int:
    total = 0
    with destination.open("wb") as output:
        while True:
            data = stream.read(1024 * 1024)
            if not data:
                break
            total += len(data)
            if total > upload_config.max_file_size_bytes:
                raise ValueError("file too large")
            output.write(data)
    return total


def save_stream_as_chunks(stream, upload_id: str, upload_config, upload_sessions: dict, expected_size: int | None = None) -> tuple[int, int]:
    chunk_size = choose_chunk_size(upload_config, upload_sessions, expected_size)
    chunk_dir = upload_config.chunk_dir / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    total_chunks = 0
    while True:
        data = stream.read(chunk_size)
        if not data:
            break
        total_bytes += len(data)
        if total_bytes > upload_config.max_file_size_bytes:
            raise ValueError("file too large")
        chunk_path = chunk_dir / f"chunk_{total_chunks:06d}.part"
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
            chunk_path = chunk_dir / f"chunk_{index:06d}.part"
            if not chunk_path.exists():
                raise FileNotFoundError(f"missing chunk {index}")
            with chunk_path.open("rb") as chunk_file:
                while True:
                    data = chunk_file.read(1024 * 1024)
                    if not data:
                        break
                    bytes_written += len(data)
                    if bytes_written > upload_config.max_file_size_bytes:
                        raise ValueError("file too large")
                    output.write(data)

    tmp_destination.replace(destination)

    for chunk_path in chunk_dir.glob("chunk_*.part"):
        chunk_path.unlink(missing_ok=True)
    chunk_dir.rmdir()
    return bytes_written


def store_uploaded_file(
    *,
    file_id: str,
    original_name: str,
    stored_name: str,
    size: int,
    mime: str,
    client_msg_id: str,
    uploaded_files: dict,
    api_config,
) -> dict:
    media_url = f"/media/{file_id}"
    download_url = download_path_for(file_id, api_config, versioned=True)
    entry = {
        "file_id": file_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "size": size,
        "mime": mime,
        "uploaded_at": utc_now_iso(),
        "client_msg_id": client_msg_id,
        # Legacy UI preview uses file.url directly, so keep inline media URL here.
        "url": media_url,
        "download_url": download_url,
        "alias_url": download_path_for(file_id, api_config, versioned=False),
    }
    uploaded_files[file_id] = entry
    return entry


def serialize_attachment(entry: dict, api_config) -> dict:
    return {
        "file_id": entry.get("file_id"),
        "filename": entry.get("original_name"),
        "size": entry.get("size"),
        "mime_type": entry.get("mime"),
        "url": entry.get("download_url")
        or download_path_for(entry.get("file_id", ""), api_config, versioned=True),
    }


def serialize_message(message: Message, api_config) -> dict:
    attachments = []
    source = message.attachments or ([] if message.file is None else [message.file])
    for entry in source:
        attachments.append(serialize_attachment(entry, api_config))

    return {
        "id": message.msg_id,
        "user": message.user,
        "text": message.text,
        "kind": message.kind,
        "created_at": message.created_at,
        "attachments": attachments,
        "client_msg_id": message.client_msg_id,
    }


def send_entry(entry: dict, upload_config, api_config, api_error, *, as_attachment: bool):
    file_path = upload_config.upload_dir / entry["stored_name"]
    if not file_path.exists():
        return api_error("file not found", 404, 40401)

    return send_file(
        file_path,
        mimetype=entry.get("mime") or None,
        as_attachment=as_attachment,
        download_name=entry.get("original_name"),
        conditional=True,
    )
