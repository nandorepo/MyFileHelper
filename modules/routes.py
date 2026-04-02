from __future__ import annotations

from ipaddress import ip_address, ip_network
from uuid import uuid4
import logging

from flask import render_template, request, session

from .error_codes import ROUTE_ACCESS_FORBIDDEN

logger = logging.getLogger(__name__)
from .log_routes import register_log_routes
from .message_routes import register_message_routes
from .upload_routes import register_upload_routes
from .upload_service import send_entry
from .response_utils import error_response


def is_ip_allowed(remote_ip: str, allowed_networks: list[str]) -> bool:
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


def _extract_remote_ip() -> tuple[str | None, str]:
    xff = request.headers.get("X-Forwarded-For", "")
    remote_ip = xff.split(",")[0].strip() if xff else request.remote_addr
    return remote_ip, xff


def _is_request_allowed(server_config, remote_ip: str | None) -> bool:
    if not server_config.access_control_enabled or not server_config.allowed_networks:
        return True
    return is_ip_allowed(str(remote_ip), server_config.allowed_networks)


def _register_request_hooks(app, server_config) -> None:
    @app.before_request
    def enforce_ip_allowlist():
        logger = logging.getLogger(__name__)
        remote_ip, xff = _extract_remote_ip()
        logger.debug(
            "access_control: enabled=%s allowed_networks=%s remote_ip=%s xff=%s",
            server_config.access_control_enabled,
            server_config.allowed_networks,
            remote_ip,
            xff,
        )

        if not _is_request_allowed(server_config, remote_ip):
            return error_response("forbidden", 403, ROUTE_ACCESS_FORBIDDEN)

    @app.after_request
    def disable_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


def _escape_html(text: str) -> str:
    import html

    return html.escape(str(text), quote=True)


def _resolve_media_entry_by_ref(state, file_ref: str) -> dict | None:
    with state.uploads_lock:
        direct_entry = state.uploaded_files.get(file_ref)
        if direct_entry:
            return direct_entry

        if not file_ref.isdigit():
            return None

        alias_index = int(file_ref)
        if alias_index <= 0:
            return None

        # Alias order follows files_index order to keep /files and /media/N consistent.
        items = list(state.uploaded_files.values())

    items.sort(key=lambda x: (x.get("uploaded_at", ""), x.get("file_id", "")))
    if alias_index > len(items):
        return None
    return items[alias_index - 1]


def _build_files_index_html(entries: list[dict]) -> str:
    rows = []
    for index, entry in enumerate(entries, start=1):
        file_id = entry.get("file_id", "")
        original_name = entry.get("original_name", "")
        size = entry.get("size", 0)
        uploaded_at = entry.get("uploaded_at", "")
        alias_url = f"/media/{index}"
        rows.append(
            f"<tr><td>{_escape_html(original_name)}</td>"
            f"<td>{_escape_html(file_id)}</td>"
            f"<td>{_escape_html(size)}</td>"
            f"<td>{_escape_html(uploaded_at)}</td>"
            f"<td><a href=\"{_escape_html(alias_url)}\">{_escape_html(alias_url)}</a></td></tr>"
        )

    return """
        <!doctype html>
        <html lang="en">
        <head><meta charset="utf-8"><title>Uploaded Files</title></head>
        <body>
          <h1>Uploaded Files</h1>
          <table border="1" cellpadding="5" cellspacing="0">
            <thead><tr><th>Name</th><th>File ID</th><th>Size</th><th>Uploaded At</th><th>URL Alias</th></tr></thead>
            <tbody>
        """ + "\n".join(rows) + """
            </tbody>
          </table>
        </body>
        </html>
        """


def _register_page_routes(app, upload_config, server_config, state) -> None:

    @app.route("/")
    def index() -> str:
        if "terminal_session_id" not in session:
            session["terminal_session_id"] = str(uuid4())
        return render_template("index.html")

    @app.get("/media/<file_id>")
    def media(file_id: str):
        """
        下载文件 - 带队列管理
        查询参数：
            - download=1: 以附件方式下载
            - queue=0: 跳过队列（仅用于内联预览）
        """
        entry = _resolve_media_entry_by_ref(state, file_id)
        if not entry:
            return "Not Found", 404
        
        # 获取查询参数
        as_attachment = request.args.get("download") == "1"
        use_queue = request.args.get("queue") != "0"  # 默认使用队列
        
        # 如果是下载请求且启用队列，则使用队列
        if as_attachment and use_queue and server_config.download_config.enable_queue:
            download_manager = state.get_download_manager()
            
            # 提交下载任务
            task = download_manager.submit_download(file_id)
            
            # 等待获得下载槽位
            timeout = server_config.download_config.download_timeout_seconds
            ready = download_manager.wait_for_slot(task, timeout=timeout)
            
            if not ready:
                logger.warning("Download timeout for file_id=%s", file_id)
                return error_response(
                    "download queue timeout",
                    503,
                    code=5001
                )
            
            try:
                # 执行下载
                response = send_entry(entry, upload_config, error_response, as_attachment=as_attachment)
                
                # 标记下载完成
                download_manager.mark_download_completed(task)
                
                return response
                
            except Exception as e:
                # 标记下载失败
                download_manager.mark_download_failed(task, str(e))
                logger.error("Download error for file_id=%s: %s", file_id, e)
                raise
        else:
            # 不使用队列（内联预览或禁用队列）
            return send_entry(entry, upload_config, error_response, as_attachment=as_attachment)

    @app.get("/files")
    def files_index():
        if not server_config.autoindex_enabled:
            return "Not Found", 404

        with state.uploads_lock:
            items = list(state.uploaded_files.values())
        items.sort(key=lambda x: (x.get("uploaded_at", ""), x.get("file_id", "")))

        return _build_files_index_html(items)
    

def register_routes(app, socketio, upload_config, server_config, state, client_log_config) -> None:
    _register_request_hooks(app, server_config)
    _register_page_routes(app, upload_config, server_config, state)

    register_upload_routes(app, socketio, upload_config, state)
    register_message_routes(app, socketio, server_config, state)
    register_log_routes(app, client_log_config)
