[中文](README.zh-CN.md)

# MyFileHelper

A LAN-based messaging and file-sharing tool built with Flask + Flask-SocketIO. It supports real-time synchronization in the web UI and RESTful API calls. Data is stored in memory only (no persistence).

## Features

- Real-time message synchronization (Socket.IO)
- File upload and download
- Manual chunk upload flow: `init -> chunk -> complete`
- Auto upload endpoint (optional server-side chunking)
- RESTful API
- OpenAPI 3 documentation (Swagger UI / ReDoc)

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

### 2) `config/api_config.yaml`

Controls API version path, pagination, and Socket.IO parameters.

Key fields:

- `api.default_version` (default `v1`)
- `api.enable_versionless_alias` (whether to enable versionless aliases)
- `pagination.default_limit`
- `socketio.ping_interval`
- `socketio.ping_timeout`

### 3) `config/security_config.yaml`

Controls API authentication and documentation access control.

Key fields:

- `auth.enabled` / `auth.mode` (`api_key` or `bearer`)
- `docs.access_control.allow_ips`
- `docs.access_control.allow_cidrs`
- `docs.auth.enabled`

## API Overview

All endpoints support two route styles:

- Versioned path: `/api/v1/...`
- Versionless alias: `/api/...`

### Messages

- `GET /api/v1/messages` (alias: `/api/messages`)
- `POST /api/v1/messages` (alias: `/api/messages`)

### Upload

- `POST /api/v1/upload` (auto upload, `multipart/form-data`)
- `POST /api/v1/upload/init`
- `POST /api/v1/upload/chunk`
- `POST /api/v1/upload/complete`

### Download

- `GET /api/v1/download/{file_id}` (alias: `/api/download/{file_id}`)

### Logs

- `POST /api/v1/client-log` (alias: `/api/client-log`)

## API Documentation

- OpenAPI JSON: `/openapi.json`
- Swagger UI: `/docs`
- ReDoc: `/redoc`

> Documentation page exposure and IP/CIDR restrictions are controlled by `config/security_config.yaml`.

## Frontend Integration Notes

- Frontend file preview uses inline media URLs (`/media/{file_id}`).
- Attachment fields in API message queries return download URLs (`/api/v1/download/{file_id}`).

## Known Behaviors and Limitations

- Messages and upload sessions are maintained in memory only and are not persisted.
- On service start and stop, upload directories are cleaned (`uploads/files` and `uploads/chunks`).
- On mobile devices (especially Android), backgrounding or locking can cause short Socket.IO disconnects and auto-reconnect.
- Auto upload (`/api/upload`) is a single-request upload and is not resumable upload. Use the 3-step chunk API for resumable transfer.

## Common Debugging

- Visit `/__health` to check service status.
- Check `logs/client.log` to troubleshoot frontend connection and upload issues.
