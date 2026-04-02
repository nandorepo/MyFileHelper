from __future__ import annotations

from flask import request

from .error_codes import (
    UPLOAD_AUTO_CHUNK_DISABLED,
    UPLOAD_FILE_REQUIRED,
    UPLOAD_QUEUE_TIMEOUT,
)
from .message_service import default_username
from .response_utils import error_response, normalize_bool, ok_response
from .upload_service import orchestrate_auto_upload


def _parse_upload_file():
    upload_file = request.files.get("file")
    if not upload_file:
        return None, error_response("file is required", 400, UPLOAD_FILE_REQUIRED)
    return upload_file, None


def _parse_upload_flags(upload_config):
    chunked = normalize_bool(request.form.get("chunked"), upload_config.auto_chunk_default_enabled)
    if chunked and not upload_config.auto_chunk_enabled:
        return None, error_response("auto chunk upload is disabled", 400, UPLOAD_AUTO_CHUNK_DISABLED)
    create_message = normalize_bool(request.form.get("create_message"), False)
    return {
        "chunked": chunked,
        "create_message": create_message,
    }, None


def _parse_upload_payload(upload_file):
    client_msg_id = (request.form.get("client_msg_id") or "").strip()
    mime = (upload_file.mimetype or request.form.get("mime_type") or "").strip()
    expected_size = (
        upload_file.content_length
        if upload_file.content_length and upload_file.content_length > 0
        else None
    )
    return {
        "client_msg_id": client_msg_id,
        "mime": mime,
        "expected_size": expected_size,
    }, None


def register_upload_routes(app, socketio, upload_config, state) -> None:
    def handle_upload_auto():
        upload_file, error = _parse_upload_file()
        if error:
            return error

        flags, error = _parse_upload_flags(upload_config)
        if error:
            return error

        payload, error = _parse_upload_payload(upload_file)
        if error:
            return error

        slot = None
        queue_enabled = getattr(upload_config, "upload_queue_enabled", False)
        if queue_enabled:
            upload_manager = state.get_upload_manager(upload_config)
            timeout = getattr(upload_config, "upload_queue_timeout_seconds", 300)
            slot = upload_manager.acquire_slot(timeout)
            if slot is None:
                return error_response("upload queue timeout", 503, UPLOAD_QUEUE_TIMEOUT)

        chunked = flags["chunked"]
        create_message = flags["create_message"]
        try:
            result, service_error = orchestrate_auto_upload(
                upload_config,
                state,
                socketio,
                upload_stream=upload_file.stream,
                filename=upload_file.filename or "",
                mime=payload["mime"],
                client_msg_id=payload["client_msg_id"],
                chunked=chunked,
                create_message=create_message,
                message_user=default_username(state),
                expected_size=payload["expected_size"],
            )
        finally:
            if slot is not None:
                upload_manager.release_slot(slot)

        if service_error:
            message, status, code = service_error
            return error_response(message, status, code)

        return ok_response(result, status=201)

    app.add_url_rule("/ui/upload", endpoint="ui_upload_auto", view_func=handle_upload_auto, methods=["POST"])
