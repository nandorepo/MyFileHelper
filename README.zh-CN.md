# MyFileHelper

基于 Flask + Flask-SocketIO 的局域网消息与文件共享工具，提供带实时同步能力的网页界面，数据不做持久化。

## 功能概览

- 实时消息同步（Socket.IO）
- 文件上传与下载
- 手动分片上传：`init -> chunk -> complete`
- 浏览器自动上传（可选服务端自动分片）

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

### 2) `config/server_config.yaml`

控制界面分页、Socket.IO 与服务端日志。

关键项：

- `pagination.default_limit`
- `socketio.ping_interval`
- `socketio.ping_timeout`
- `logging.client_log.path`
- `logging.client_log.max_bytes`

## 与前端联动说明

- 前端文件预览使用内联媒体地址（`/media/{file_id}`）。
- 浏览器端通过 `/ui/*` 下的内部路由完成消息和上传操作。

## 已知行为与限制

- 消息与上传会话在内存中维护，不做持久化。
- 服务启动和退出时，会清理上传目录（`uploads/files` 与 `uploads/chunks`）。
- 移动端（尤其安卓）切后台/锁屏时，可能出现 Socket.IO 短暂断连并自动重连。
- 自动上传（`/ui/upload`）是单请求上传，不等同于断点续传；断点续传请使用分片三段式上传流程。

## 常见调试

- 查看 `logs/client.log` 排查前端连接与上传错误。
