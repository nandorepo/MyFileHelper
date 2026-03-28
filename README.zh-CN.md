# MyFileHelper

基于 Flask + Flask-SocketIO 的局域网消息与文件共享工具（数据仅保存在内存，不持久化）。

## 功能

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

- `config/upload_config.yaml`：上传目录、大小限制、分片与自动分片参数
- `config/server_config.yaml`：分页、Socket.IO、日志、访问控制等参数

## 错误码

- `docs/error-codes.md`
- `docs/error-codes.md#endpoint-reverse-lookup`

## 代码质量与测试

```powershell
pip install -r quality/requirements-dev.txt
python quality/quality_check.py
```

## 常见调试

- 查看 `logs/client.log` 排查前端连接与上传问题
