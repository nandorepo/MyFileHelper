from __future__ import annotations

import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
import logging
from uuid import uuid4

from flask import jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from .api_utils import api_error, api_ok, normalize_bool, parse_utc, register_api_route
from .docs_service import docs_access_allowed, openapi_spec
from .message_service import append_message, default_username
from .upload_service import (
    choose_chunk_size,
    merge_chunks,
    save_stream_as_chunks,
    save_stream_to_file,
    send_entry,
    serialize_attachment,
    serialize_message,
    store_uploaded_file,
)


def register_routes(app, socketio, upload_config, api_config, security_config, state, client_log_config) -> None:
    client_log_config.path.parent.mkdir(parents=True, exist_ok=True)
    client_log_handler = RotatingFileHandler(
        client_log_config.path,
        maxBytes=client_log_config.max_bytes,
        backupCount=client_log_config.backup_count,
        encoding="utf-8",
    )
    client_log_handler.setLevel(0)
    client_log_handler.setFormatter(None)
    client_log_logger = logging.getLogger("client_log")
    client_log_logger.propagate = False
    client_log_logger.addHandler(client_log_handler)
    @app.after_request
    def disable_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.before_request
    def enforce_api_auth():
        if not security_config.auth_enabled:
            return None

        path = request.path
        if not path.startswith(api_config.base_path.rstrip("/") + "/"):
            return None

        if path in {
            security_config.docs_openapi_path,
            security_config.docs_swagger_path,
            security_config.docs_redoc_path,
        }:
            return None

        if security_config.auth_mode == "none":
            return None

        if security_config.auth_mode == "api_key":
            provided = request.headers.get(security_config.auth_header_name, "").strip()
            if provided and provided in security_config.auth_api_keys:
                return None
            return api_error("unauthorized", 401, 40100)

        if security_config.auth_mode == "bearer":
            header = request.headers.get("Authorization", "").strip()
            if header.startswith("Bearer "):
                token = header[len("Bearer ") :].strip()
                if token and token in security_config.auth_bearer_tokens:
                    return None
            return api_error("unauthorized", 401, 40100)

        return api_error("unauthorized", 401, 40100)

    @app.route("/")
    def index() -> str:
        if "terminal_session_id" not in session:
            session["terminal_session_id"] = str(uuid4())
        return render_template("index.html")

    @app.get("/media/<file_id>")
    def legacy_media(file_id: str):
        entry = state.uploaded_files.get(file_id)
        if not entry:
            return "Not Found", 404
        as_attachment = request.args.get("download") == "1"
        return send_entry(entry, upload_config, api_config, api_error, as_attachment=as_attachment)

    def handle_get_messages():
        limit_raw = request.args.get("limit", str(api_config.pagination_default_limit)).strip()
        cursor_raw = request.args.get("cursor", "0").strip() or "0"
        since_raw = request.args.get("since", "").strip()

        try:
            limit = int(limit_raw)
            cursor = int(cursor_raw)
        except ValueError:
            return api_error("invalid pagination parameters", 400, 40001)

        if limit <= 0:
            return api_error("limit must be positive", 400, 40002)

        limit = min(limit, api_config.pagination_hard_cap)
        cursor = max(cursor, 0)

        filtered = state.messages
        if since_raw:
            since_dt = parse_utc(since_raw)
            if since_dt is None:
                return api_error("invalid since timestamp", 400, 40003)
            filtered = [m for m in filtered if parse_utc(m.created_at or "") and parse_utc(m.created_at) >= since_dt]

        total = len(filtered)
        end = min(cursor + limit, total)
        page = filtered[cursor:end]

        next_cursor = str(end) if end < total else None
        payload = {
            "items": [serialize_message(msg, api_config) for msg in page],
            "next_cursor": next_cursor,
            "limit": limit,
            "total": total,
        }
        return api_ok(payload)

    def handle_post_messages():
        data = request.get_json(silent=True) or {}
        user = (data.get("user") or "").strip() or default_username(state)
        text = (data.get("text") or "").strip()
        client_msg_id = (data.get("client_msg_id") or "").strip() or None
        attachment_ids_raw = data.get("attachment_ids") or []

        if not isinstance(attachment_ids_raw, list):
            return api_error("attachment_ids must be an array", 400, 40004)

        attachment_ids = [str(v).strip() for v in attachment_ids_raw if str(v).strip()]
        attachments: list[dict] = []
        for file_id in attachment_ids:
            entry = state.uploaded_files.get(file_id)
            if not entry:
                return api_error(f"attachment not found: {file_id}", 404, 40402)
            attachments.append(entry)

        if not text and not attachments:
            return api_error("text or attachment_ids is required", 400, 40005)

        kind = "text"
        if attachments and text:
            kind = "mixed"
        elif attachments:
            kind = "file"

        msg = append_message(
            state,
            socketio,
            user=user,
            text=text,
            kind=kind,
            attachments=attachments or None,
            client_msg_id=client_msg_id,
            broadcast=True,
        )
        return api_ok({"message": serialize_message(msg, api_config)}, status=201)

    def handle_upload_init():
        data = request.get_json(silent=True) or {}
        filename = (data.get("filename") or "").strip()
        mime = (data.get("mime") or data.get("mime_type") or "").strip()
        client_msg_id = (data.get("client_msg_id") or "").strip()

        try:
            size = int(data.get("size") or 0)
        except (TypeError, ValueError):
            return api_error("invalid file size", 400, 40006)

        if not filename or size <= 0:
            return api_error("filename and size are required", 400, 40007)
        if size > upload_config.max_file_size_bytes:
            return api_error("file too large", 413, 41301)

        upload_id = str(uuid4())
        state.upload_sessions[upload_id] = {
            "filename": filename,
            "size": size,
            "mime": mime,
            "client_msg_id": client_msg_id,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        (upload_config.chunk_dir / upload_id).mkdir(parents=True, exist_ok=True)

        return api_ok(
            {
                "upload_id": upload_id,
                "chunk_size": choose_chunk_size(upload_config, state.upload_sessions, size),
                "max_concurrency": upload_config.max_concurrency,
                "max_file_size_bytes": upload_config.max_file_size_bytes,
            }
        )

    def handle_upload_chunk():
        upload_id = (request.form.get("upload_id") or "").strip()
        index_raw = (request.form.get("index") or "").strip()
        total_raw = (request.form.get("total_chunks") or "").strip()
        chunk_file = request.files.get("chunk")

        if not upload_id or upload_id not in state.upload_sessions:
            return api_error("upload session not found", 404, 40403)
        if not chunk_file or not index_raw or not total_raw:
            return api_error("invalid chunk request", 400, 40008)

        try:
            index = int(index_raw)
            total_chunks = int(total_raw)
        except ValueError:
            return api_error("invalid chunk index", 400, 40009)

        if index < 0 or total_chunks <= 0 or index >= total_chunks:
            return api_error("chunk index out of range", 400, 40010)

        chunk_dir = upload_config.chunk_dir / upload_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_path = chunk_dir / f"chunk_{index:06d}.part"

        with chunk_path.open("wb") as output:
            chunk_file.stream.seek(0)
            while True:
                data = chunk_file.stream.read(1024 * 1024)
                if not data:
                    break
                output.write(data)

        return api_ok({"upload_id": upload_id, "index": index})

    def handle_upload_complete():
        data = request.get_json(silent=True) or {}
        upload_id = (data.get("upload_id") or "").strip()

        try:
            total_chunks = int(data.get("total_chunks") or 0)
        except (TypeError, ValueError):
            return api_error("invalid total_chunks", 400, 40011)

        if not upload_id or upload_id not in state.upload_sessions:
            return api_error("upload session not found", 404, 40403)
        if total_chunks <= 0:
            return api_error("total_chunks must be positive", 400, 40012)

        session_info = state.upload_sessions.pop(upload_id)
        safe_name = secure_filename(session_info["filename"]) or f"{upload_id}.bin"
        stored_name = f"{upload_id}_{safe_name}"
        final_path = upload_config.upload_dir / stored_name

        try:
            merged_bytes = merge_chunks(upload_id, total_chunks, final_path, upload_config)
        except FileNotFoundError as exc:
            return api_error(str(exc), 400, 40013)
        except ValueError:
            return api_error("file too large", 413, 41301)

        declared_size = int(session_info.get("size") or 0)
        if declared_size > 0 and merged_bytes != declared_size:
            final_path.unlink(missing_ok=True)
            return api_error("merged size does not match declared size", 400, 40014)

        entry = store_uploaded_file(
            file_id=upload_id,
            original_name=session_info["filename"],
            stored_name=stored_name,
            size=merged_bytes,
            mime=session_info.get("mime") or "",
            client_msg_id=session_info.get("client_msg_id") or "",
            uploaded_files=state.uploaded_files,
            api_config=api_config,
        )

        msg = append_message(
            state,
            socketio,
            user=default_username(state),
            text=entry["original_name"],
            kind="file",
            attachments=[entry],
            client_msg_id=entry.get("client_msg_id") or None,
            broadcast=True,
        )

        return api_ok({"file": serialize_attachment(entry, api_config), "message": serialize_message(msg, api_config)})

    def handle_upload_auto():
        upload_file = request.files.get("file")
        if not upload_file:
            return api_error("file is required", 400, 40015)

        chunked = normalize_bool(request.form.get("chunked"), upload_config.auto_chunk_default_enabled)
        if chunked and not upload_config.auto_chunk_enabled:
            return api_error("auto chunk upload is disabled", 400, 40016)

        create_message = normalize_bool(request.form.get("create_message"), False)
        client_msg_id = (request.form.get("client_msg_id") or "").strip()
        mime = (upload_file.mimetype or request.form.get("mime_type") or "").strip()
        expected_size = upload_file.content_length if upload_file.content_length and upload_file.content_length > 0 else None

        file_id = str(uuid4())
        safe_name = secure_filename(upload_file.filename or "") or f"{file_id}.bin"
        stored_name = f"{file_id}_{safe_name}"
        final_path = upload_config.upload_dir / stored_name

        try:
            if chunked:
                total_chunks, bytes_written = save_stream_as_chunks(
                    upload_file.stream,
                    file_id,
                    upload_config,
                    state.upload_sessions,
                    expected_size,
                )
                if total_chunks == 0:
                    return api_error("empty file", 400, 40017)
                merged_bytes = merge_chunks(file_id, total_chunks, final_path, upload_config)
                if merged_bytes != bytes_written:
                    final_path.unlink(missing_ok=True)
                    return api_error("merge verification failed", 500, 50001)
                actual_size = merged_bytes
            else:
                actual_size = save_stream_to_file(upload_file.stream, final_path, upload_config)
                if actual_size <= 0:
                    final_path.unlink(missing_ok=True)
                    return api_error("empty file", 400, 40017)
        except ValueError:
            final_path.unlink(missing_ok=True)
            return api_error("file too large", 413, 41301)

        entry = store_uploaded_file(
            file_id=file_id,
            original_name=upload_file.filename or safe_name,
            stored_name=stored_name,
            size=actual_size,
            mime=mime,
            client_msg_id=client_msg_id,
            uploaded_files=state.uploaded_files,
            api_config=api_config,
        )

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

        return api_ok(
            {
                "file": serialize_attachment(entry, api_config),
                "upload": {
                    "chunked": chunked,
                    "chunk_size": choose_chunk_size(upload_config, state.upload_sessions, expected_size),
                },
            },
            status=201,
        )

    def handle_download(file_id: str):
        entry = state.uploaded_files.get(file_id)
        if not entry:
            return api_error("file not found", 404, 40401)

        inline = normalize_bool(request.args.get("inline"), False)
        return send_entry(entry, upload_config, api_config, api_error, as_attachment=not inline)

    def handle_client_log() -> tuple[str, int]:
        data = request.get_json(silent=True) or {}
        entry = {
            "server_ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "level": data.get("level", "info"),
            "args": data.get("args", []),
            "page": data.get("page", request.path),
            "ua": request.headers.get("User-Agent", ""),
        }
        client_log_logger.info(json.dumps(entry, ensure_ascii=False))
        return "", 204

    @app.get("/__health")
    def healthcheck():
        return api_ok({"status": "ok", "version": api_config.default_version})

    @app.get(security_config.docs_openapi_path)
    def openapi_json():
        allowed, response = docs_access_allowed(security_config)
        if not allowed:
            return response
        return jsonify(openapi_spec(api_config))

    @app.get(security_config.docs_swagger_path)
    def swagger_ui():
        allowed, response = docs_access_allowed(security_config)
        if not allowed:
            return response

        html = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>MyFileHelper API Docs</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\" />
</head>
<body>
  <div id=\"swagger-ui\"></div>
  <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: '{security_config.docs_openapi_path}',
      dom_id: '#swagger-ui'
    }});
  </script>
</body>
</html>
"""
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get(security_config.docs_redoc_path)
    def redoc_ui():
        allowed, response = docs_access_allowed(security_config)
        if not allowed:
            return response

        html = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>MyFileHelper ReDoc</title>
  <script src=\"https://unpkg.com/redoc@next/bundles/redoc.standalone.js\"></script>
</head>
<body>
  <redoc spec-url=\"{security_config.docs_openapi_path}\"></redoc>
</body>
</html>
"""
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    register_api_route(app, "/messages", ["GET"], handle_get_messages, "api_messages_get", api_config)
    register_api_route(app, "/messages", ["POST"], handle_post_messages, "api_messages_post", api_config)
    register_api_route(app, "/upload", ["POST"], handle_upload_auto, "api_upload_auto", api_config)
    register_api_route(app, "/upload/init", ["POST"], handle_upload_init, "api_upload_init", api_config)
    register_api_route(app, "/upload/chunk", ["POST"], handle_upload_chunk, "api_upload_chunk", api_config)
    register_api_route(app, "/upload/complete", ["POST"], handle_upload_complete, "api_upload_complete", api_config)
    register_api_route(app, "/download/<file_id>", ["GET"], handle_download, "api_download", api_config)
    register_api_route(app, "/client-log", ["POST"], handle_client_log, "api_client_log", api_config)
