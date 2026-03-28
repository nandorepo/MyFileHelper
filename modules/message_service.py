from __future__ import annotations

import time
from dataclasses import asdict
from uuid import uuid4

from flask import session

from .error_codes import (
    MSG_ATTACHMENT_IDS_NOT_ARRAY,
    MSG_ATTACHMENT_NOT_FOUND,
    MSG_TEXT_OR_ATTACHMENTS_REQUIRED,
)
from .response_utils import parse_utc, utc_now_iso
from .state import AppState, Message


def append_message(
    state: AppState,
    socketio,
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
        created_at=utc_now_iso(),
    )
    with state.messages_lock:
        state.messages.append(msg)
    if broadcast:
        socketio.emit("message", asdict(msg))
    return msg


def default_username(state: AppState) -> str:
    terminal_session_id = session.get("terminal_session_id")
    with state.clients_lock:
        if terminal_session_id and terminal_session_id in state.terminal_sessions:
            return state.terminal_sessions[terminal_session_id].get("username", "Anonymous")
    return "Anonymous"


def list_messages(state: AppState, *, limit: int, cursor: int, since_raw: str = "") -> tuple[dict | None, str | None]:
    with state.messages_lock:
        filtered = list(state.messages)
    if since_raw:
        since_dt = parse_utc(since_raw)
        if since_dt is None:
            return None, "invalid since timestamp"
        filtered = [m for m in filtered if parse_utc(m.created_at or "") and parse_utc(m.created_at) >= since_dt]

    total = len(filtered)
    end = min(cursor + limit, total)
    page = filtered[cursor:end]
    next_cursor = str(end) if end < total else None

    return {
        "items": page,
        "next_cursor": next_cursor,
        "limit": limit,
        "total": total,
    }, None


def resolve_attachments(
    uploaded_files: dict[str, dict], attachment_ids: list[str]
) -> tuple[list[dict] | None, str | None]:
    attachments: list[dict] = []
    for file_id in attachment_ids:
        entry = uploaded_files.get(file_id)
        if not entry:
            return None, file_id
        attachments.append(entry)
    return attachments, None


def determine_message_kind(text: str, attachments: list[dict]) -> str:
    if attachments and text:
        return "mixed"
    if attachments:
        return "file"
    return "text"


def client_names(state: AppState) -> list[str]:
    with state.clients_lock:
        return list(state.clients.values())


def emit_clients(state: AppState, socketio) -> None:
    socketio.emit("clients", client_names(state))


def validate_message_create_payload(
    data: dict,
    *,
    fallback_user: str,
) -> tuple[dict | None, tuple[str, int, int] | None]:
    user = (data.get("user") or "").strip() or fallback_user
    text = (data.get("text") or "").strip()
    client_msg_id = (data.get("client_msg_id") or "").strip() or None
    attachment_ids_raw = data.get("attachment_ids") or []

    if not isinstance(attachment_ids_raw, list):
        return None, ("attachment_ids must be an array", 400, MSG_ATTACHMENT_IDS_NOT_ARRAY)

    attachment_ids = [str(v).strip() for v in attachment_ids_raw if str(v).strip()]
    return {
        "user": user,
        "text": text,
        "client_msg_id": client_msg_id,
        "attachment_ids": attachment_ids,
    }, None


def orchestrate_message_create(
    state: AppState,
    socketio,
    *,
    user: str,
    text: str,
    client_msg_id: str | None,
    attachment_ids: list[str],
) -> tuple[Message | None, tuple[str, int, int] | None]:
    with state.uploads_lock:
        attachments, missing_file_id = resolve_attachments(state.uploaded_files, attachment_ids)
    if missing_file_id:
        return None, (f"attachment not found: {missing_file_id}", 404, MSG_ATTACHMENT_NOT_FOUND)

    attachments = attachments or []
    if not text and not attachments:
        return None, ("text or attachment_ids is required", 400, MSG_TEXT_OR_ATTACHMENTS_REQUIRED)

    msg = append_message(
        state,
        socketio,
        user=user,
        text=text,
        kind=determine_message_kind(text, attachments),
        attachments=attachments or None,
        client_msg_id=client_msg_id,
        broadcast=True,
    )
    return msg, None
