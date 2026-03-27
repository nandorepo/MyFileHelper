from __future__ import annotations

import time
from dataclasses import asdict
from uuid import uuid4

from flask import session

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
    state.messages.append(msg)
    if broadcast:
        socketio.emit("message", asdict(msg))
    return msg


def default_username(state: AppState) -> str:
    terminal_session_id = session.get("terminal_session_id")
    if terminal_session_id and terminal_session_id in state.terminal_sessions:
        return state.terminal_sessions[terminal_session_id].get("username", "Anonymous")
    return "Anonymous"


def list_messages(state: AppState, *, limit: int, cursor: int, since_raw: str = "") -> tuple[dict | None, str | None]:
    filtered = state.messages
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


def resolve_attachments(uploaded_files: dict[str, dict], attachment_ids: list[str]) -> tuple[list[dict] | None, str | None]:
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
