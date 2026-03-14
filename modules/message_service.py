from __future__ import annotations

import time
from dataclasses import asdict
from uuid import uuid4

from flask import session

from .api_utils import utc_now_iso
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


def client_names(state: AppState) -> list[str]:
    with state.clients_lock:
        return list(state.clients.values())


def emit_clients(state: AppState, socketio) -> None:
    socketio.emit("clients", client_names(state))
