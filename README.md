# 消息传输助手

基于 Flask + Socket.IO 的网页消息及文件同步工具，不做消息持久化。

## 运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

访问 `http://ip:port`（app.py设置ip与port）打开多个浏览器/终端即可同步。
