from __future__ import annotations

import atexit
import json
import shutil
import time
import yaml
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4
from typing import Dict, List

from flask import Flask, jsonify, render_template, request, session, send_file, url_for
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"

socketio = SocketIO(app, cors_allowed_origins="*")

LOG_DIR = Path("logs")
CLIENT_LOG_FILE = LOG_DIR / "client.log"
UPLOAD_CONFIG_PATH = Path("config/upload_config.yaml")


@app.after_request
def disable_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@dataclass
class UploadConfig:
    upload_dir: Path
    chunk_dir: Path
    max_file_size_mb: int
    default_chunk_size_mb: int
    min_chunk_size_mb: int
    max_chunk_size_mb: int
    max_concurrency: int

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def default_chunk_size_bytes(self) -> int:
        return self.default_chunk_size_mb * 1024 * 1024

    @property
    def max_chunk_size_bytes(self) -> int:
        return self.max_chunk_size_mb * 1024 * 1024


def load_upload_config() -> UploadConfig:
    defaults = UploadConfig(
        upload_dir=Path("uploads/files"),
        chunk_dir=Path("uploads/chunks"),
        max_file_size_mb=51200,
        default_chunk_size_mb=10,
        min_chunk_size_mb=2,
        max_chunk_size_mb=32,
        max_concurrency=3,
    )
    if not UPLOAD_CONFIG_PATH.exists():
        return defaults

    try:
        with UPLOAD_CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return defaults

    storage = data.get("storage", {}) or {}
    limits = data.get("limits", {}) or {}
    chunking = data.get("chunking", {}) or {}

    upload_dir = str(storage.get("uploadDir", "uploads/files")).strip()
    chunk_dir = str(storage.get("tempDir", "uploads/chunks")).strip()
    return UploadConfig(
        upload_dir=Path(upload_dir),
        chunk_dir=Path(chunk_dir),
        max_file_size_mb=int(limits.get("maxFileSizeMB", defaults.max_file_size_mb)),
        default_chunk_size_mb=int(chunking.get("defaultChunkSizeMB", defaults.default_chunk_size_mb)),
        min_chunk_size_mb=int(chunking.get("minChunkSizeMB", defaults.min_chunk_size_mb)),
        max_chunk_size_mb=int(chunking.get("maxChunkSizeMB", defaults.max_chunk_size_mb)),
        max_concurrency=int(chunking.get("maxConcurrency", defaults.max_concurrency)),
    )


UPLOAD_CONFIG = load_upload_config()
UPLOAD_CONFIG.upload_dir.mkdir(parents=True, exist_ok=True)
UPLOAD_CONFIG.chunk_dir.mkdir(parents=True, exist_ok=True)



@dataclass
class Message:
    msg_id: str
    user: str
    text: str
    ts: str
    kind: str = "text"
    file: dict | None = None
    client_msg_id: str | None = None


messages: List[Message] = []
clients: Dict[str, str] = {}
terminal_sessions: Dict[str, dict] = {}
sid_to_terminal_session: Dict[str, str] = {}
upload_sessions: Dict[str, dict] = {}
uploaded_files: Dict[str, dict] = {}

_clients_lock = Lock()


def _clean_upload_dirs() -> None:
    for path in (UPLOAD_CONFIG.upload_dir, UPLOAD_CONFIG.chunk_dir):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)


_clean_upload_dirs()
atexit.register(_clean_upload_dirs)


@app.route("/")
def index() -> str:
    if "terminal_session_id" not in session:
        session["terminal_session_id"] = str(uuid4())
    return render_template("index.html")


@app.get("/media/<file_id>")
def serve_media(file_id: str):
    download = request.args.get("download") == "1"
    entry = uploaded_files.get(file_id)
    if not entry:
        return "Not Found", 404

    file_path = UPLOAD_CONFIG.upload_dir / entry["stored_name"]
    if not file_path.exists():
        return "Not Found", 404

    return send_file(
        file_path,
        mimetype=entry.get("mime") or None,
        as_attachment=download,
        download_name=entry.get("original_name"),
        conditional=True,
    )


@app.post("/api/upload/init")
def upload_init() -> tuple[str, int]:
    data = request.get_json(silent=True) or {}
    filename = (data.get("filename") or "").strip()
    size = int(data.get("size") or 0)
    mime = (data.get("mime") or "").strip()
    client_msg_id = (data.get("client_msg_id") or "").strip()

    if not filename or size <= 0:
        return jsonify({"ok": False, "error": "文件信息不完整"}), 400

    if size > UPLOAD_CONFIG.max_file_size_bytes:
        return jsonify({"ok": False, "error": "文件超过大小限制"}), 413

    upload_id = str(uuid4())
    upload_sessions[upload_id] = {
        "filename": filename,
        "size": size,
        "mime": mime,
        "client_msg_id": client_msg_id,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    (UPLOAD_CONFIG.chunk_dir / upload_id).mkdir(parents=True, exist_ok=True)

    return (
        jsonify(
            {
                "ok": True,
                "upload_id": upload_id,
                "chunk_size": UPLOAD_CONFIG.default_chunk_size_bytes,
                "max_concurrency": UPLOAD_CONFIG.max_concurrency,
                "max_file_size": UPLOAD_CONFIG.max_file_size_bytes,
            }
        ),
        200,
    )


@app.post("/api/upload/chunk")
def upload_chunk() -> tuple[str, int]:
    upload_id = (request.form.get("upload_id") or "").strip()
    index_raw = (request.form.get("index") or "").strip()
    total_raw = (request.form.get("total_chunks") or "").strip()
    chunk_file = request.files.get("chunk")

    if not upload_id or upload_id not in upload_sessions:
        return jsonify({"ok": False, "error": "上传会话不存在"}), 404
    if not chunk_file or not index_raw or not total_raw:
        return jsonify({"ok": False, "error": "分片信息不完整"}), 400

    try:
        index = int(index_raw)
        total_chunks = int(total_raw)
    except ValueError:
        return jsonify({"ok": False, "error": "分片序号非法"}), 400

    if index < 0 or total_chunks <= 0 or index >= total_chunks:
        return jsonify({"ok": False, "error": "分片序号越界"}), 400

    chunk_dir = UPLOAD_CONFIG.chunk_dir / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"chunk_{index:06d}.part"

    with chunk_path.open("wb") as f:
        chunk_file.stream.seek(0)
        while True:
            data = chunk_file.stream.read(1024 * 1024)
            if not data:
                break
            f.write(data)

    return jsonify({"ok": True}), 200


@app.post("/api/upload/complete")
def upload_complete() -> tuple[str, int]:
    data = request.get_json(silent=True) or {}
    upload_id = (data.get("upload_id") or "").strip()
    total_chunks = int(data.get("total_chunks") or 0)

    if not upload_id or upload_id not in upload_sessions:
        return jsonify({"ok": False, "error": "上传会话不存在"}), 404
    if total_chunks <= 0:
        return jsonify({"ok": False, "error": "分片数量非法"}), 400

    session_info = upload_sessions.pop(upload_id)
    chunk_dir = UPLOAD_CONFIG.chunk_dir / upload_id
    if not chunk_dir.exists():
        return jsonify({"ok": False, "error": "分片目录不存在"}), 404

    for index in range(total_chunks):
        if not (chunk_dir / f"chunk_{index:06d}.part").exists():
            return jsonify({"ok": False, "error": "分片不完整"}), 400

    safe_name = secure_filename(session_info["filename"]) or f"{upload_id}.bin"
    stored_name = f"{upload_id}_{safe_name}"
    final_path = UPLOAD_CONFIG.upload_dir / stored_name

    with final_path.open("wb") as output:
        for index in range(total_chunks):
            chunk_path = chunk_dir / f"chunk_{index:06d}.part"
            with chunk_path.open("rb") as f:
                while True:
                    data = f.read(1024 * 1024)
                    if not data:
                        break
                    output.write(data)

    for chunk_path in chunk_dir.glob("chunk_*.part"):
        chunk_path.unlink(missing_ok=True)
    chunk_dir.rmdir()

    entry = {
        "file_id": upload_id,
        "original_name": session_info["filename"],
        "stored_name": stored_name,
        "size": session_info["size"],
        "mime": session_info["mime"],
        "uploaded_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "client_msg_id": session_info.get("client_msg_id") or "",
    }
    entry["url"] = url_for("serve_media", file_id=upload_id)
    uploaded_files[upload_id] = entry

    terminal_session_id = session.get("terminal_session_id")
    username = "Anonymous"
    if terminal_session_id and terminal_session_id in terminal_sessions:
        username = terminal_sessions[terminal_session_id].get("username", username)

    msg = Message(
        msg_id=f"{int(time.time() * 1000)}-{upload_id}",
        user=username,
        text=entry["original_name"],
        ts=time.strftime("%H:%M:%S"),
        kind="file",
        file=entry,
        client_msg_id=entry.get("client_msg_id") or None,
    )
    messages.append(msg)
    socketio.emit("message", asdict(msg))
    return jsonify({"ok": True, "file": entry}), 200


def append_client_log(payload: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with CLIENT_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _client_names() -> list[str]:
    with _clients_lock:
        return list(clients.values())


def emit_clients() -> None:
    socketio.emit("clients", _client_names())


@app.post("/api/client-log")
def client_log() -> tuple[str, int]:
    data = request.get_json(silent=True) or {}
    entry = {
        "server_ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
        "level": data.get("level", "info"),
        "args": data.get("args", []),
        "page": data.get("page", request.path),
        "ua": request.headers.get("User-Agent", ""),
    }
    append_client_log(entry)
    return "", 204


@socketio.on("register")
def handle_register(data: dict) -> dict:
    username = ((data or {}).get("username") or "").strip()
    if not username:
        return {"ok": False, "error": "终端名称不能为空"}

    if len(username) > 24:
        return {"ok": False, "error": "终端名称不能超过 24 个字符"}

    terminal_session_id = session.get("terminal_session_id")
    if not terminal_session_id:
        terminal_session_id = str(uuid4())
        session["terminal_session_id"] = terminal_session_id

    with _clients_lock:
        terminal_record = terminal_sessions.setdefault(
            terminal_session_id,
            {"username": username, "sids": set()},
        )
        terminal_record["username"] = username
        terminal_record["sids"].add(request.sid)

        sid_to_terminal_session[request.sid] = terminal_session_id
        clients[request.sid] = username

    emit("history", [asdict(m) for m in messages])
    emit_clients()
    return {"ok": True}


@socketio.on("message")
def handle_message(data: dict) -> None:
    text = (data or {}).get("text", "").strip()
    if not text:
        return
    username = clients.get(request.sid, "Anonymous")
    msg = Message(
        msg_id=f"{int(time.time() * 1000)}-{request.sid}",
        user=username,
        text=text,
        ts=time.strftime("%H:%M:%S"),
    )
    messages.append(msg)
    socketio.emit("message", asdict(msg))


@socketio.on("disconnect")
def handle_disconnect() -> None:
    removed = False
    with _clients_lock:
        if request.sid in clients:
            clients.pop(request.sid, None)
            removed = True

        terminal_session_id = sid_to_terminal_session.pop(request.sid, None)
        if terminal_session_id and terminal_session_id in terminal_sessions:
            terminal_record = terminal_sessions[terminal_session_id]
            terminal_record["sids"].discard(request.sid)
            if not terminal_record["sids"]:
                terminal_sessions.pop(terminal_session_id, None)

    if removed:
        emit_clients()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=80, debug=True, allow_unsafe_werkzeug=True)
