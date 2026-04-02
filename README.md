[中文](README.zh-CN.md)

# MyFileHelper

A LAN messaging and file-sharing tool built with Flask + Flask-SocketIO (data is in-memory only, not persisted).

## Features

- Real-time message sync (Socket.IO)
- File upload and download with drag-and-drop support
- Server-side automatic chunking for large uploads

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

Default bind: `0.0.0.0:80`

## Configuration Files

- `config/upload_config.yaml`: upload directories, size limits, chunking and auto-chunk settings
- `config/server_config.yaml`: pagination, Socket.IO, logging, and access-control settings

## Files Index Entry (`/files`)

- Visit `http://<host>/files` to browse uploaded files (requires `autoindex.enabled` in `config/server_config.yaml`).
- File links use URL aliases (`/media/1`, `/media/2`, ...) and can be used for preview or download.
- For `wget` downloads, append `?download=1`, for example: `/media/1?download=1`.

## Error Codes

- `docs/error-codes.md`
- `docs/error-codes.md#endpoint-reverse-lookup`

## Code Quality and Tests

```powershell
pip install -r quality/requirements-dev.txt
python quality/quality_check.py
```

## Common Debugging

- Check `logs/client.log` for frontend connection and upload issues
