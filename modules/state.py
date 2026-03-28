from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock, RLock
from typing import Dict, List


@dataclass
class Message:
    msg_id: str
    user: str
    text: str
    ts: str
    kind: str = "text"
    file: dict | None = None
    attachments: list[dict] | None = None
    client_msg_id: str | None = None
    created_at: str = ""


@dataclass
class AppState:
    messages: List[Message] = field(default_factory=list)
    clients: Dict[str, str] = field(default_factory=dict)
    terminal_sessions: Dict[str, dict] = field(default_factory=dict)
    sid_to_terminal_session: Dict[str, str] = field(default_factory=dict)
    upload_sessions: Dict[str, dict] = field(default_factory=dict)
    uploaded_files: Dict[str, dict] = field(default_factory=dict)
    clients_lock: Lock = field(default_factory=Lock)
    messages_lock: RLock = field(default_factory=RLock)
    uploads_lock: RLock = field(default_factory=RLock)
