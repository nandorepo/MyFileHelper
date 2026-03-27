from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import send_file
from werkzeug.utils import secure_filename

from .response_utils import utc_now_iso
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


def create_upload_session(upload_config, upload_sessions: dict, *, filename: str, size: int, mime: str, client_msg_id: str) -> dict:
    upload_id = str(uuid4())
    upload_sessions[upload_id] = {
        "filename": filename,
        "size": size,
        "mime": mime,
        "client_msg_id": client_msg_id,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    (upload_config.chunk_dir / upload_id).mkdir(parents=True, exist_ok=True)
    return {
        "upload_id": upload_id,
        "chunk_size": choose_chunk_size(upload_config, upload_sessions, size),
        "max_concurrency": upload_config.max_concurrency,
        "max_file_size_bytes": upload_config.max_file_size_bytes,
    }


def save_upload_chunk(upload_config, upload_sessions: dict, *, upload_id: str, index: int, total_chunks: int, chunk_stream) -> dict:
    if upload_id not in upload_sessions:
        raise KeyError("upload session not found")
    if index < 0 or total_chunks <= 0 or index >= total_chunks:
        raise IndexError("chunk index out of range")

    chunk_dir = upload_config.chunk_dir / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"chunk_{index:06d}.part"

    with chunk_path.open("wb") as output:
        chunk_stream.seek(0)
        while True:
            data = chunk_stream.read(1024 * 1024)
            if not data:
                break
            output.write(data)

    return {"upload_id": upload_id, "index": index}


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


def finalize_upload_session(upload_config, upload_sessions: dict, uploaded_files: dict, *, upload_id: str, total_chunks: int) -> dict:
    session_info = upload_sessions.pop(upload_id)
    safe_name = secure_filename(session_info["filename"]) or f"{upload_id}.bin"
    stored_name = f"{upload_id}_{safe_name}"
    final_path = upload_config.upload_dir / stored_name

    merged_bytes = merge_chunks(upload_id, total_chunks, final_path, upload_config)
    declared_size = int(session_info.get("size") or 0)
    if declared_size > 0 and merged_bytes != declared_size:
        final_path.unlink(missing_ok=True)
        raise RuntimeError("merged size does not match declared size")

    return store_uploaded_file(
        file_id=upload_id,
        original_name=session_info["filename"],
        stored_name=stored_name,
        size=merged_bytes,
        mime=session_info.get("mime") or "",
        client_msg_id=session_info.get("client_msg_id") or "",
        uploaded_files=uploaded_files,
    )


def store_auto_uploaded_file(
    upload_config,
    upload_sessions: dict,
    uploaded_files: dict,
    *,
    upload_stream,
    filename: str,
    mime: str,
    client_msg_id: str,
    chunked: bool,
    expected_size: int | None = None,
) -> tuple[dict, int]:
    file_id = str(uuid4())
    safe_name = secure_filename(filename or "") or f"{file_id}.bin"
    stored_name = f"{file_id}_{safe_name}"
    final_path = upload_config.upload_dir / stored_name

    try:
        if chunked:
            total_chunks, bytes_written = save_stream_as_chunks(
                upload_stream,
                file_id,
                upload_config,
                upload_sessions,
                expected_size,
            )
            if total_chunks == 0:
                raise EOFError("empty file")
            merged_bytes = merge_chunks(file_id, total_chunks, final_path, upload_config)
            if merged_bytes != bytes_written:
                final_path.unlink(missing_ok=True)
                raise RuntimeError("merge verification failed")
            actual_size = merged_bytes
        else:
            actual_size = save_stream_to_file(upload_stream, final_path, upload_config)
            if actual_size <= 0:
                final_path.unlink(missing_ok=True)
                raise EOFError("empty file")
    except Exception:
        if final_path.exists():
            final_path.unlink(missing_ok=True)
        raise

    entry = store_uploaded_file(
        file_id=file_id,
        original_name=filename or safe_name,
        stored_name=stored_name,
        size=actual_size,
        mime=mime,
        client_msg_id=client_msg_id,
        uploaded_files=uploaded_files,
    )
    return entry, choose_chunk_size(upload_config, upload_sessions, expected_size)


def store_uploaded_file(
    *,
    file_id: str,
    original_name: str,
    stored_name: str,
    size: int,
    mime: str,
    client_msg_id: str,
    uploaded_files: dict,
) -> dict:
    media_url = f"/media/{file_id}"
    download_url = f"/media/{file_id}?download=1"
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
        "alias_url": download_url,
    }
    uploaded_files[file_id] = entry
    return entry


def serialize_attachment(entry: dict) -> dict:
    return {
        "file_id": entry.get("file_id"),
        "filename": entry.get("original_name"),
        "size": entry.get("size"),
        "mime_type": entry.get("mime"),
        "url": entry.get("download_url") or f"/media/{entry.get('file_id', '')}?download=1",
        "download_url": entry.get("download_url") or f"/media/{entry.get('file_id', '')}?download=1",
        "alias_url": entry.get("alias_url") or f"/media/{entry.get('file_id', '')}?download=1",
        "inline_url": entry.get("url") or f"/media/{entry.get('file_id', '')}",
    }


def serialize_message(message: Message) -> dict:
    attachments = []
    source = message.attachments or ([] if message.file is None else [message.file])
    for entry in source:
        attachments.append(serialize_attachment(entry))

    return {
        "id": message.msg_id,
        "user": message.user,
        "text": message.text,
        "kind": message.kind,
        "created_at": message.created_at,
        "attachments": attachments,
        "client_msg_id": message.client_msg_id,
    }


def send_entry(entry: dict, upload_config, error_response, *, as_attachment: bool):
    file_path = upload_config.upload_dir / entry["stored_name"]
    if not file_path.exists():
        return error_response("file not found", 404, 40401)

    return send_file(
        file_path,
        mimetype=entry.get("mime") or None,
        as_attachment=as_attachment,
        download_name=entry.get("original_name"),
        conditional=True,
    )
