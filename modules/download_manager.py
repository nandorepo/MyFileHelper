from __future__ import annotations

import threading
import time
import logging
from queue import Queue, Empty
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """下载任务"""
    task_id: str = field(default_factory=lambda: str(uuid4()))
    file_id: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: str = "pending"  # pending, processing, completed, failed
    error: Optional[str] = None
    _ready_event: Optional[threading.Event] = field(default=None, init=False, repr=False)


class DownloadQueueManager:
    """下载队列管理器 - 控制并发下载数量"""

    def __init__(self, max_concurrent_downloads: int = 5):
        """
        Args:
            max_concurrent_downloads: 最大并发下载数
        """
        self.max_concurrent = max_concurrent_downloads
        self.queue: Queue[DownloadTask] = Queue()
        self.active_downloads: dict[str, DownloadTask] = {}
        self.completed_downloads: dict[str, DownloadTask] = {}

        # 锁和信号量
        self._lock = threading.RLock()
        self._semaphore = threading.Semaphore(max_concurrent_downloads)

        # 工作线程
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 启动工作线程
        self._start_worker()

    def _start_worker(self) -> None:
        """启动队列工作线程"""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="DownloadQueueWorker",
        )
        self._worker_thread.start()
        logger.info("Download queue worker started (max_concurrent=%d)", self.max_concurrent)

    def _worker_loop(self) -> None:
        """工作线程的主循环"""
        while not self._stop_event.is_set():
            try:
                # 从队列获取任务（超时避免一直等待）
                task = self.queue.get(timeout=1)

                # 获取信号量（等待可用的下载槽位）
                logger.debug("Waiting for download slot for task %s", task.task_id)
                self._semaphore.acquire()

                try:
                    # 标记为处理中
                    with self._lock:
                        task.status = "processing"
                        task.started_at = time.time()
                        self.active_downloads[task.task_id] = task

                    logger.info(
                        "Download started: file_id=%s, task_id=%s, queue_size=%d, active=%d",
                        task.file_id,
                        task.task_id,
                        self.queue.qsize(),
                        len(self.active_downloads),
                    )

                    # 发出信号告诉主线程可以开始下载
                    if task._ready_event:
                        task._ready_event.set()

                except Exception as e:
                    logger.error("Error in download worker: %s", e)
                    task.status = "failed"
                    task.error = str(e)
                    if task._ready_event:
                        task._ready_event.set()

            except Empty:
                continue
            except Exception as e:
                logger.error("Unexpected error in download worker: %s", e)

    def submit_download(self, file_id: str) -> DownloadTask:
        """
        提交下载任务到队列

        Args:
            file_id: 文件ID

        Returns:
            DownloadTask 对象
        """
        task = DownloadTask(file_id=file_id, status="pending")
        task._ready_event = threading.Event()  # 用于同步

        with self._lock:
            self.queue.put(task)

        logger.debug("Download task submitted: file_id=%s, task_id=%s", file_id, task.task_id)
        return task

    def wait_for_slot(self, task: DownloadTask, timeout: float = 300) -> bool:
        """
        等待下载开始（等待队列分配槽位）

        Args:
            task: 下载任务
            timeout: 超时时间（秒）

        Returns:
            True 如果成功获得槽位，False 如果超时
        """
        if task._ready_event is None:
            task._ready_event = threading.Event()

        ready = task._ready_event.wait(timeout=timeout)

        if not ready:
            logger.warning("Download slot wait timeout: file_id=%s, task_id=%s", task.file_id, task.task_id)
            task.status = "failed"
            task.error = "Download slot allocation timeout"

        return ready

    def mark_download_completed(self, task: DownloadTask) -> None:
        """标记下载完成"""
        with self._lock:
            task.status = "completed"
            task.completed_at = time.time()

            # 从活跃下载移到已完成
            self.active_downloads.pop(task.task_id, None)
            self.completed_downloads[task.task_id] = task

        # 释放信号量，允许下一个下载开始
        self._semaphore.release()

        elapsed = (task.completed_at - task.started_at) if task.started_at else 0
        logger.info(
            "Download completed: file_id=%s, task_id=%s, elapsed=%.2fs, queue_size=%d",
            task.file_id,
            task.task_id,
            elapsed,
            self.queue.qsize(),
        )

    def mark_download_failed(self, task: DownloadTask, error: str = "") -> None:
        """标记下载失败"""
        with self._lock:
            task.status = "failed"
            task.error = error
            self.active_downloads.pop(task.task_id, None)
            self.completed_downloads[task.task_id] = task

        # 释放信号量，允许下一个下载开始
        self._semaphore.release()

        logger.warning(
            "Download failed: file_id=%s, task_id=%s, error=%s",
            task.file_id,
            task.task_id,
            error,
        )

    def get_stats(self) -> dict:
        """获取队列统计信息"""
        with self._lock:
            return {
                "max_concurrent": self.max_concurrent,
                "queue_size": self.queue.qsize(),
                "active_downloads": len(self.active_downloads),
                "completed_downloads": len(self.completed_downloads),
                "active_tasks": [
                    {
                        "file_id": t.file_id,
                        "task_id": t.task_id,
                        "status": t.status,
                        "elapsed": time.time() - t.started_at if t.started_at else 0,
                    }
                    for t in self.active_downloads.values()
                ],
            }

    def shutdown(self) -> None:
        """关闭队列管理器"""
        logger.info("Shutting down download queue manager")
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        logger.info("Download queue manager shut down")

