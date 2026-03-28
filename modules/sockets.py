from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from flask import request, session
from flask_socketio import emit

from .message_service import append_message, emit_clients


def register_socket_handlers(socketio, state) -> None:
    @socketio.on("register")
    def handle_register(data: dict) -> dict:
        username = ((data or {}).get("username") or "").strip()
        if not username:
            return {"ok": False, "error": "terminal name cannot be empty"}

        if len(username) > 24:
            return {"ok": False, "error": "terminal name cannot be longer than 24 characters"}

        terminal_session_id = session.get("terminal_session_id")
        if not terminal_session_id:
            terminal_session_id = str(uuid4())
            session["terminal_session_id"] = terminal_session_id

        with state.clients_lock:
            terminal_record = state.terminal_sessions.setdefault(
                terminal_session_id,
                {"username": username, "sids": set()},
            )
            terminal_record["username"] = username
            terminal_record["sids"].add(request.sid)

            state.sid_to_terminal_session[request.sid] = terminal_session_id
            state.clients[request.sid] = username

        with state.messages_lock:
            history = [asdict(m) for m in state.messages]
        emit("history", history)
        emit_clients(state, socketio)
        return {"ok": True}

    @socketio.on("message")
    def handle_message(data: dict) -> None:
        text = (data or {}).get("text", "").strip()
        if not text:
            return
        with state.clients_lock:
            username = state.clients.get(request.sid, "Anonymous")
        append_message(state, socketio, user=username, text=text, kind="text", broadcast=True)

    @socketio.on("disconnect")
    def handle_disconnect() -> None:
        removed = False
        with state.clients_lock:
            if request.sid in state.clients:
                state.clients.pop(request.sid, None)
                removed = True

            terminal_session_id = state.sid_to_terminal_session.pop(request.sid, None)
            if terminal_session_id and terminal_session_id in state.terminal_sessions:
                terminal_record = state.terminal_sessions[terminal_session_id]
                terminal_record["sids"].discard(request.sid)
                if not terminal_record["sids"]:
                    state.terminal_sessions.pop(terminal_session_id, None)

        if removed:
            emit_clients(state, socketio)
