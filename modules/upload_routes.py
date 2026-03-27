from __future__ import annotations

from flask import request

from .message_service import append_message, default_username
from .response_utils import error_response, normalize_bool, ok_response
from .upload_service import (
    create_upload_session,
    finalize_upload_session,
    save_upload_chunk,
    serialize_attachment,
    serialize_message,
    store_auto_uploaded_file,
)


def register_upload_routes(app, socketio, upload_config, state) -> None:
    def handle_upload_auto():
        upload_file = request.files.get("file")
        if not upload_file:
            return error_response("file is required", 400, 40015)

        chunked = normalize_bool(request.form.get("chunked"), upload_config.auto_chunk_default_enabled)
        if chunked and not upload_config.auto_chunk_enabled:
            return error_response("auto chunk upload is disabled", 400, 40016)

        create_message = normalize_bool(request.form.get("create_message"), False)
        client_msg_id = (request.form.get("client_msg_id") or "").strip()
        mime = (upload_file.mimetype or request.form.get("mime_type") or "").strip()
        expected_size = upload_file.content_length if upload_file.content_length and upload_file.content_length > 0 else None

        try:
            entry, chunk_size = store_auto_uploaded_file(
                upload_config,
                state.upload_sessions,
                state.uploaded_files,
                upload_stream=upload_file.stream,
                filename=upload_file.filename or "",
                mime=mime,
                client_msg_id=client_msg_id,
                chunked=chunked,
                expected_size=expected_size,
            )
        except EOFError:
            return error_response("empty file", 400, 40017)
        except RuntimeError:
            return error_response("merge verification failed", 500, 50001)
        except ValueError:
            return error_response("file too large", 413, 41301)

        if create_message:
            append_message(
                state,
                socketio,
                user=default_username(state),
                text=entry["original_name"],
                kind="file",
                attachments=[entry],
                client_msg_id=client_msg_id or None,
                broadcast=True,
            )

        return ok_response(
            {
                "file": serialize_attachment(entry),
                "upload": {
                    "chunked": chunked,
                    "chunk_size": chunk_size,
                },
            },
            status=201,
        )

    app.add_url_rule("/ui/upload", endpoint="ui_upload_auto", view_func=handle_upload_auto, methods=["POST"])
