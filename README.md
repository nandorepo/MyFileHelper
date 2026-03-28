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
- Browser actions use Socket.IO for realtime sync and also expose `/ui/*` endpoints for HTTP integration.
- Frontend maintainability and learning notes: `docs/frontend-maintainability.md`

## API Response Contract

JSON API endpoints use a single envelope defined in `modules/response_utils.py`:

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

- `code = 0` means success
- `message` is a stable human-readable summary
- `data` carries the success payload; errors always return `null`

Error example:

```json
{
  "code": 40015,
  "message": "file is required",
  "data": null
}
```

Routes intentionally outside the JSON success contract:

- `/files` returns HTML
- `/media/<file_id>` returns file bytes on success and plain text `404` when the entry is unknown
- `/ui/client-log` returns HTTP `204 No Content`

## Error Codes

Error codes are defined in `modules/error_codes.py` and documented in detail at:

- `docs/error-codes.md`
- Endpoint-first lookup: `docs/error-codes.md#endpoint-reverse-lookup`

For quick checks, the JSON error envelope remains:

```json
{
  "code": 40015,
  "message": "file is required",
  "data": null
}
```

## Code Quality and Tests

```powershell
pip install -r quality/requirements-dev.txt
ruff check .
pytest
```

## Known Behaviors and Limitations

- Messages and upload sessions are maintained in memory only and are not persisted.
- On service start and stop, upload directories are cleaned (`uploads/files` and `uploads/chunks`).
- On mobile devices (especially Android), backgrounding or locking can cause short Socket.IO disconnects and auto-reconnect.
- Browser auto upload (`/ui/upload`) is a single-request upload and supports server-side chunking for large files (客户端发送一次上传请求，服务端自动切片处理)。

## Common Debugging

- Check `logs/client.log` to troubleshoot frontend connection and upload issues.
