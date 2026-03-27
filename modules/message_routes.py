from __future__ import annotations

from flask import request

from .message_service import append_message, default_username, determine_message_kind, list_messages, resolve_attachments
from .response_utils import error_response, ok_response
from .upload_service import serialize_message


def register_message_routes(app, socketio, server_config, state) -> None:
    def handle_get_messages():
        limit_raw = request.args.get("limit", str(server_config.pagination_default_limit)).strip()
        cursor_raw = request.args.get("cursor", "0").strip() or "0"
        since_raw = request.args.get("since", "").strip()

        try:
            limit = int(limit_raw)
            cursor = int(cursor_raw)
        except ValueError:
            return error_response("invalid pagination parameters", 400, 40001)

        if limit <= 0:
            return error_response("limit must be positive", 400, 40002)

        limit = min(limit, server_config.pagination_hard_cap)
        cursor = max(cursor, 0)

        payload, error = list_messages(state, limit=limit, cursor=cursor, since_raw=since_raw)
        if error:
            return error_response(error, 400, 40003)
        assert payload is not None
        payload["items"] = [serialize_message(msg) for msg in payload["items"]]
        return ok_response(payload)

    def handle_post_messages():
        data = request.get_json(silent=True) or {}
        user = (data.get("user") or "").strip() or default_username(state)
        text = (data.get("text") or "").strip()
        client_msg_id = (data.get("client_msg_id") or "").strip() or None
        attachment_ids_raw = data.get("attachment_ids") or []

        if not isinstance(attachment_ids_raw, list):
            return error_response("attachment_ids must be an array", 400, 40004)

        attachment_ids = [str(v).strip() for v in attachment_ids_raw if str(v).strip()]
        attachments, missing_file_id = resolve_attachments(state.uploaded_files, attachment_ids)
        if missing_file_id:
            return error_response(f"attachment not found: {missing_file_id}", 404, 40402)
        attachments = attachments or []

        if not text and not attachments:
            return error_response("text or attachment_ids is required", 400, 40005)

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
        return ok_response({"message": serialize_message(msg)}, status=201)

    app.add_url_rule("/ui/messages", endpoint="ui_messages_get", view_func=handle_get_messages, methods=["GET"])
    app.add_url_rule("/ui/messages", endpoint="ui_messages_post", view_func=handle_post_messages, methods=["POST"])
