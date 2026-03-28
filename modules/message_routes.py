from __future__ import annotations

from flask import request

from .error_codes import (
    MSG_INVALID_PAGINATION,
    MSG_INVALID_SINCE,
    MSG_LIMIT_NOT_POSITIVE,
)
from .message_service import (
    default_username,
    list_messages,
    orchestrate_message_create,
    validate_message_create_payload,
)
from .response_utils import error_response, ok_response
from .upload_service import serialize_message


def _parse_list_query(server_config):
    limit_raw = request.args.get("limit", str(server_config.pagination_default_limit)).strip()
    cursor_raw = request.args.get("cursor", "0").strip() or "0"
    since_raw = request.args.get("since", "").strip()

    try:
        limit = int(limit_raw)
        cursor = int(cursor_raw)
    except ValueError:
        return None, error_response("invalid pagination parameters", 400, MSG_INVALID_PAGINATION)

    if limit <= 0:
        return None, error_response("limit must be positive", 400, MSG_LIMIT_NOT_POSITIVE)

    return {
        "limit": min(limit, server_config.pagination_hard_cap),
        "cursor": max(cursor, 0),
        "since_raw": since_raw,
    }, None


def _parse_create_payload(state):
    data = request.get_json(silent=True) or {}
    payload, service_error = validate_message_create_payload(data, fallback_user=default_username(state))
    if service_error:
        message, status, code = service_error
        return None, error_response(message, status, code)
    return payload, None


def register_message_routes(app, socketio, server_config, state) -> None:
    def handle_get_messages():
        query, error = _parse_list_query(server_config)
        if error:
            return error

        payload, error = list_messages(
            state,
            limit=query["limit"],
            cursor=query["cursor"],
            since_raw=query["since_raw"],
        )
        if error:
            return error_response(error, 400, MSG_INVALID_SINCE)
        assert payload is not None
        payload["items"] = [serialize_message(msg) for msg in payload["items"]]
        return ok_response(payload)

    def handle_post_messages():
        payload_data, error = _parse_create_payload(state)
        if error:
            return error

        user = payload_data["user"]
        text = payload_data["text"]
        client_msg_id = payload_data["client_msg_id"]
        attachment_ids = payload_data["attachment_ids"]
        msg, service_error = orchestrate_message_create(
            state,
            socketio,
            user=user,
            text=text,
            client_msg_id=client_msg_id,
            attachment_ids=attachment_ids,
        )
        if service_error:
            message, status, code = service_error
            return error_response(message, status, code)

        assert msg is not None
        return ok_response({"message": serialize_message(msg)}, status=201)

    app.add_url_rule("/ui/messages", endpoint="ui_messages_get", view_func=handle_get_messages, methods=["GET"])
    app.add_url_rule("/ui/messages", endpoint="ui_messages_post", view_func=handle_post_messages, methods=["POST"])
