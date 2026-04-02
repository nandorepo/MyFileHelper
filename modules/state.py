from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock, RLock
from typing import Dict, List, Optional


@dataclass
class Message:
    msg_id: str
    user: str
    text: str
    ts: str
    kind: str = "text"
    file: dict | None = None
    attachments: list[dict] | None = None
    client_msg_id: str | None = None
    created_at: str = ""


@dataclass
class AppState:
    messages: List[Message] = field(default_factory=list)
    clients: Dict[str, str] = field(default_factory=dict)
    terminal_sessions: Dict[str, dict] = field(default_factory=dict)
    sid_to_terminal_session: Dict[str, str] = field(default_factory=dict)
    upload_sessions: Dict[str, dict] = field(default_factory=dict)
    uploaded_files: Dict[str, dict] = field(default_factory=dict)
    clients_lock: Lock = field(default_factory=Lock)
    messages_lock: RLock = field(default_factory=RLock)
    uploads_lock: RLock = field(default_factory=RLock)
    
    # 下载队列管理器（延迟初始化）
    download_manager: Optional[object] = field(default=None, init=False)
    upload_manager: Optional[object] = field(default=None, init=False)

    def get_download_manager(self):
        """获取下载管理器（延迟初始化）"""
        if self.download_manager is None:
            from .download_manager import DownloadQueueManager
            self.download_manager = DownloadQueueManager(max_concurrent_downloads=5)
        return self.download_manager

    def get_upload_manager(self, upload_config):
        """获取上传队列管理器（延迟初始化）"""
        if self.upload_manager is None:
            from .upload_manager import UploadQueueManager
            self.upload_manager = UploadQueueManager(
                max_active_uploads=upload_config.max_active_uploads
            )
        return self.upload_manager
