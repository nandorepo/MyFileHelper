[中文](README.zh-CN.md)

# MyFileHelper

A LAN-based messaging and file-sharing tool built with Flask + Flask-SocketIO. It provides a browser UI with real-time synchronization. Data is stored in memory only (no persistence).

## Features

- Real-time message synchronization (Socket.IO)
- File upload and download
- Manual chunk upload flow: `init -> chunk -> complete`
- Auto upload in the browser UI (optional server-side chunking)

## Requirements

- Python 3.9+
- Windows / Linux / macOS

## Quick Start

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Default listen address: `0.0.0.0:80`

## Configuration Files

### 1) `config/upload_config.yaml`

Controls upload directory, file size limits, chunk parameters, and auto-chunk settings.

Key fields:

- `limits.maxFileSizeMB`
- `chunking.defaultChunkSizeMB`
- `chunking.maxConcurrency`
- `autoChunk.enabled`
- `autoChunk.defaultEnabled`

### 2) `config/server_config.yaml`

Controls UI pagination, Socket.IO, server logging, and the autoindex listing endpoint.

Key fields:

- `pagination.default_limit`
- `socketio.ping_interval`
- `socketio.ping_timeout`
- `logging.client_log.path`
- `logging.client_log.max_bytes`
- `autoindex.enabled`  (true/false) to allow `/files` autoindex listing
- `access_control.enabled`  (true/false) to turn on/off IP access control (default: false)
- `access_control.allowed_networks`  (CIDR list) to restrict access by client IP

## Frontend Integration Notes

- Frontend file preview uses inline media URLs (`/media/{file_id}`).
- Browser actions使用基于 Socket.IO 的实时消息，不再依赖 `/ui/*` REST API 端点。

## Known Behaviors and Limitations

- Messages and upload sessions are maintained in memory only and are not persisted.
- On service start and stop, upload directories are cleaned (`uploads/files` and `uploads/chunks`).
- On mobile devices (especially Android), backgrounding or locking can cause short Socket.IO disconnects and auto-reconnect.
- Browser auto upload (`/ui/upload`) is a single-request upload and supports server-side chunking for large files (客户端发送一次上传请求，服务端自动切片处理)。

## Common Debugging

- Check `logs/client.log` to troubleshoot frontend connection and upload issues.
