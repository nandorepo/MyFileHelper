from __future__ import annotations

from ipaddress import ip_address, ip_network
from uuid import uuid4
import logging

from flask import render_template, request, session

from .upload_routes import register_upload_routes
from .upload_service import send_entry
from .response_utils import error_response


def register_routes(app, socketio, upload_config, server_config, state, client_log_config) -> None:
    def _is_ip_allowed(remote_ip: str, allowed_networks: list[str]) -> bool:
        if not remote_ip:
            return False
        try:
            ipvalue = ip_address(remote_ip)
        except ValueError:
            return False

        for network in allowed_networks:
            try:
                net = ip_network(network, strict=False)
            except ValueError:
                continue
            if ipvalue in net:
                return True
        return False

    @app.before_request
    def enforce_ip_allowlist():
        logger = logging.getLogger(__name__)
        xff = request.headers.get("X-Forwarded-For", "")
        remote_ip = xff.split(",")[0].strip() if xff else request.remote_addr
        logger.debug("access_control: enabled=%s allowed_networks=%s remote_ip=%s xff=%s",
                     server_config.access_control_enabled,
                     server_config.allowed_networks,
                     remote_ip,
                     xff)

        if not server_config.access_control_enabled or not server_config.allowed_networks:
            return

        xff = request.headers.get("X-Forwarded-For", "")
        remote_ip = xff.split(",")[0].strip() if xff else request.remote_addr

        if not _is_ip_allowed(str(remote_ip), server_config.allowed_networks):
            return error_response("forbidden", 403, 40301)

    @app.after_request
    def disable_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route("/")
    def index() -> str:
        if "terminal_session_id" not in session:
            session["terminal_session_id"] = str(uuid4())
        return render_template("index.html")

    @app.get("/media/<file_id>")
    def media(file_id: str):
        entry = state.uploaded_files.get(file_id)
        if not entry:
            return "Not Found", 404
        as_attachment = request.args.get("download") == "1"
        return send_entry(entry, upload_config, error_response, as_attachment=as_attachment)

    @app.get("/files")
    def files_index():
        if not server_config.autoindex_enabled:
            return "Not Found", 404

        def _escape(text: str) -> str:
            import html

            return html.escape(str(text), quote=True)

        items = list(state.uploaded_files.values())
        items.sort(key=lambda x: x.get("uploaded_at", ""))

        rows = []
        for entry in items:
            file_id = entry.get("file_id", "")
            original_name = entry.get("original_name", "")
            size = entry.get("size", 0)
            uploaded_at = entry.get("uploaded_at", "")
            url = f"/media/{file_id}"
            download_url = f"{url}?download=1"
            rows.append(
                f"<tr><td>{_escape(file_id)}</td>"
                f"<td>{_escape(original_name)}</td>"
                f"<td>{_escape(size)}</td>"
                f"<td>{_escape(uploaded_at)}</td>"
                f"<td><a href=\"{_escape(url)}\">view</a> | <a href=\"{_escape(download_url)}\">download</a></td></tr>"
            )

        html_page = """
        <!doctype html>
        <html lang="en">
        <head><meta charset="utf-8"><title>Uploaded Files</title></head>
        <body>
          <h1>Uploaded Files</h1>
          <table border="1" cellpadding="5" cellspacing="0">
            <thead><tr><th>File ID</th><th>Name</th><th>Size</th><th>Uploaded At</th><th>Actions</th></tr></thead>
            <tbody>
        """ + "\n".join(rows) + """
            </tbody>
          </table>
        </body>
        </html>
        """

        return html_page

    register_upload_routes(app, socketio, upload_config, state)
