from __future__ import annotations

from modules.message_service import (
    list_messages,
    orchestrate_message_create,
    validate_message_create_payload,
)
from modules.state import AppState, Message


def _msg(msg_id: str, created_at: str) -> Message:
    return Message(msg_id=msg_id, user="u", text="t", ts="00:00:00", created_at=created_at)


class DummySocketIO:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def emit(self, event: str, payload: object) -> None:
        self.events.append((event, payload))


def test_list_messages_paginates() -> None:
    state = AppState(
        messages=[
            _msg("1", "2026-03-27T10:00:00Z"),
            _msg("2", "2026-03-27T10:01:00Z"),
            _msg("3", "2026-03-27T10:02:00Z"),
        ]
    )
    payload, error = list_messages(state, limit=2, cursor=0)

    assert error is None
    assert payload is not None
    assert len(payload["items"]) == 2
    assert payload["next_cursor"] == "2"
    assert payload["total"] == 3


def test_list_messages_rejects_invalid_since() -> None:
    payload, error = list_messages(AppState(), limit=10, cursor=0, since_raw="bad-ts")

    assert payload is None
    assert error == "invalid since timestamp"


def test_list_messages_filters_by_since() -> None:
    state = AppState(
        messages=[
            _msg("1", "2026-03-27T10:00:00Z"),
            _msg("2", "2026-03-27T10:05:00Z"),
        ]
    )
    payload, error = list_messages(state, limit=10, cursor=0, since_raw="2026-03-27T10:03:00Z")

    assert error is None
    assert payload is not None
    assert [m.msg_id for m in payload["items"]] == ["2"]


def test_validate_message_create_payload_rejects_non_array_attachment_ids() -> None:
    payload, error = validate_message_create_payload(
        {"text": "hello", "attachment_ids": "bad"},
        fallback_user="Anonymous",
    )

    assert payload is None
    assert error is not None
    assert error[2] == 40004


def test_orchestrate_message_create_rejects_missing_attachment() -> None:
    msg, error = orchestrate_message_create(
        AppState(),
        DummySocketIO(),
        user="u",
        text="",
        client_msg_id=None,
        attachment_ids=["missing"],
    )

    assert msg is None
    assert error is not None
    assert error[2] == 40402


def test_orchestrate_message_create_success_text_only() -> None:
    state = AppState()
    socketio = DummySocketIO()
    msg, error = orchestrate_message_create(
        state,
        socketio,
        user="u",
        text="hello",
        client_msg_id=None,
        attachment_ids=[],
    )

    assert error is None
    assert msg is not None
    assert msg.kind == "text"
    assert len(state.messages) == 1
    assert len(socketio.events) == 1

