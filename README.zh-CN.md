# MyFileHelper

基于 Flask + Flask-SocketIO 的局域网消息与文件共享工具，支持网页端实时同步，RESTful API 调用，数据不做持久化。

## 功能概览

- 实时消息同步（Socket.IO）
- 文件上传与下载
- 手动分片上传：`init -> chunk -> complete`
- 自动上传接口（可选服务端自动分片）
- RESTful API
- OpenAPI 3 文档（Swagger UI / ReDoc）

## 运行环境

- Python 3.9+
- Windows / Linux / macOS

## 快速启动

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

默认监听：`0.0.0.0:80`

## 配置文件

### 1) `config/upload_config.yaml`

控制上传目录、大小限制、分片参数、自动分片参数。

关键项：

- `limits.maxFileSizeMB`
- `chunking.defaultChunkSizeMB`
- `chunking.maxConcurrency`
- `autoChunk.enabled`
- `autoChunk.defaultEnabled`

### 2) `config/api_config.yaml`

控制 API 路径版本、分页、Socket.IO 参数。

关键项：

- `api.default_version`（默认 `v1`）
- `api.enable_versionless_alias`（是否启用无版本别名）
- `pagination.default_limit`
- `socketio.ping_interval`
- `socketio.ping_timeout`

### 3) `config/security_config.yaml`

控制 API 鉴权与文档访问控制。

关键项：

- `auth.enabled` / `auth.mode`（`api_key` 或 `bearer`）
- `docs.access_control.allow_ips`
- `docs.access_control.allow_cidrs`
- `docs.auth.enabled`

## API 概览

以下接口均支持两种形式：

- 版本路径：`/api/v1/...`
- 无版本别名：`/api/...`

### 消息

- `GET /api/v1/messages`（等价 `/api/messages`）
- `POST /api/v1/messages`（等价 `/api/messages`）

### 上传

- `POST /api/v1/upload`（自动上传，`multipart/form-data`）
- `POST /api/v1/upload/init`
- `POST /api/v1/upload/chunk`
- `POST /api/v1/upload/complete`

### 下载

- `GET /api/v1/download/{file_id}`（等价 `/api/download/{file_id}`）

### 日志

- `POST /api/v1/client-log`（等价 `/api/client-log`）

## API 文档

- OpenAPI JSON：`/openapi.json`
- Swagger UI：`/docs`
- ReDoc：`/redoc`

> 文档页面访问是否放开、IP/CIDR 鉴权，由 `config/security_config.yaml` 控制。

## 与前端联动说明

- 前端文件预览使用内联媒体地址（`/media/{file_id}`）。
- API 消息查询中的附件字段返回下载地址（`/api/v1/download/{file_id}`）。

## 已知行为与限制

- 消息与上传会话在内存中维护，不做持久化。
- 服务启动和退出时，会清理上传目录（`uploads/files` 与 `uploads/chunks`）。
- 移动端（尤其安卓）切后台/锁屏时，可能出现 Socket.IO 短暂断连并自动重连。
- 自动上传（`/api/upload`）是单请求上传，不等同于断点续传；断点续传请使用分片三段式接口。

## 常见调试

- 访问 `/__health` 检查服务状态。
- 查看 `logs/client.log` 排查前端连接与上传错误。


