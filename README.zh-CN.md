[English](README.md)

# MyFileHelper

基于 Flask + Flask-SocketIO 的局域网消息与文件共享工具（数据仅保存在内存中，不做持久化）。

## 功能

- 实时消息同步（Socket.IO）
- 文件上传与下载，支持拖放上传
- 上传大文件时，服务端自动分片

## 环境要求

- Python 3.9+
- Windows / Linux / macOS

## 快速开始

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

默认绑定地址：`0.0.0.0:80`

## 配置文件

- `config/upload_config.yaml`：上传目录、大小限制、分片与自动分片设置
- `config/server_config.yaml`：分页、Socket.IO、日志与访问控制设置

## 文件列表入口（`/files`）

- 访问 `http://<host>/files` 可浏览已上传文件（需在 `config/server_config.yaml` 中启用 `autoindex.enabled`）。
- 文件链接使用 URL alias：`/media/1`、`/media/2` ...，可用于预览或下载。
- wget 下载建议追加 `?download=1`，例如：`/media/1?download=1`。

## 错误码

- `docs/error-codes.md`
- `docs/error-codes.md#endpoint-reverse-lookup`

## 代码质量与测试

```powershell
pip install -r quality/requirements-dev.txt
python quality/quality_check.py
```

## 常见调试

- 查看 `logs/client.log` 排查前端连接和上传问题
