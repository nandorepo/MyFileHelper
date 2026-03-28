from __future__ import annotations

from uuid import uuid4

from flask import send_file
from werkzeug.utils import secure_filename

from .error_codes import (
    ROUTE_MEDIA_FILE_NOT_FOUND,
    UPLOAD_EMPTY_FILE,
    UPLOAD_FILE_TOO_LARGE,
    UPLOAD_MERGE_VERIFICATION_FAILED,
)
from .message_service import append_message
from .response_utils import utc_now_iso
from .state import Message
from .upload_storage import (
    choose_chunk_size,
    create_upload_session,
    merge_chunks,
    save_stream_as_chunks,
    save_stream_to_file,
    save_upload_chunk,
)

__all__ = [
    "choose_chunk_size",
    "create_upload_session",
    "save_upload_chunk",
    "save_stream_to_file",
    "save_stream_as_chunks",
    "merge_chunks",
    "finalize_upload_session",
    "store_auto_uploaded_file",
    "store_uploaded_file",
    "serialize_attachment",
    "serialize_message",
    "map_auto_upload_error",
    "orchestrate_auto_upload",
    "send_entry",
]


def finalize_upload_session(
    upload_config, upload_sessions: dict, uploaded_files: dict, *, upload_id: str, total_chunks: int
) -> dict:
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


def map_auto_upload_error(exc: Exception) -> tuple[str, int, int]:
    if isinstance(exc, EOFError):
        return "empty file", 400, UPLOAD_EMPTY_FILE
    if isinstance(exc, RuntimeError):
        return "merge verification failed", 500, UPLOAD_MERGE_VERIFICATION_FAILED
    if isinstance(exc, ValueError):
        return "file too large", 413, UPLOAD_FILE_TOO_LARGE
    raise exc


def orchestrate_auto_upload(
    upload_config,
    state,
    socketio,
    *,
    upload_stream,
    filename: str,
    mime: str,
    client_msg_id: str,
    chunked: bool,
    create_message: bool,
    message_user: str,
    expected_size: int | None = None,
) -> tuple[dict | None, tuple[str, int, int] | None]:
    try:
        with state.uploads_lock:
            entry, chunk_size = store_auto_uploaded_file(
                upload_config,
                state.upload_sessions,
                state.uploaded_files,
                upload_stream=upload_stream,
                filename=filename,
                mime=mime,
                client_msg_id=client_msg_id,
                chunked=chunked,
                expected_size=expected_size,
            )
    except (EOFError, RuntimeError, ValueError) as exc:
        return None, map_auto_upload_error(exc)

    if create_message:
        append_message(
            state,
            socketio,
            user=message_user,
            text=entry["original_name"],
            kind="file",
            attachments=[entry],
            client_msg_id=client_msg_id or None,
            broadcast=True,
        )

    return {
        "file": serialize_attachment(entry),
        "upload": {
            "chunked": chunked,
            "chunk_size": chunk_size,
        },
    }, None


def send_entry(entry: dict, upload_config, error_response, *, as_attachment: bool):
    file_path = upload_config.upload_dir / entry["stored_name"]
    if not file_path.exists():
        return error_response("file not found", 404, ROUTE_MEDIA_FILE_NOT_FOUND)

    return send_file(
        file_path,
        mimetype=entry.get("mime") or None,
        as_attachment=as_attachment,
        download_name=entry.get("original_name"),
        conditional=True,
    )
