from __future__ import annotations

import threading
import time
from modules.download_manager import DownloadQueueManager, DownloadTask


def test_download_queue_basic() -> None:
    """测试基本队列功能"""
    manager = DownloadQueueManager(max_concurrent_downloads=2)

    # 提交3个下载任务
    tasks = [manager.submit_download(f"file_{i}") for i in range(3)]

    assert len(tasks) == 3
    assert all(t.status == "pending" for t in tasks)

    manager.shutdown()


def test_download_queue_task_properties() -> None:
    """测试下载任务属性"""
    manager = DownloadQueueManager(max_concurrent_downloads=2)

    task = manager.submit_download("test_file_id")

    assert task.file_id == "test_file_id"
    assert task.status == "pending"
    assert task.error is None
    assert task.created_at > 0
    assert task._ready_event is not None

    manager.shutdown()


def test_download_queue_concurrency_limit() -> None:
    """测试并发限制"""
    manager = DownloadQueueManager(max_concurrent_downloads=2)

    completed = []
    lock = threading.Lock()

    def simulate_download(file_id: str) -> None:
        task = manager.submit_download(file_id)
        ready = manager.wait_for_slot(task, timeout=10)
        assert ready, f"Failed to get slot for {file_id}"
        
        time.sleep(0.2)  # 模拟下载时间
        
        manager.mark_download_completed(task)
        with lock:
            completed.append(file_id)

    # 同时启动5个下载
    threads = []
    for i in range(5):
        t = threading.Thread(target=simulate_download, args=(f"file_{i}",))
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join(timeout=15)

    # 验证所有下载都完成了
    assert len(completed) == 5

    manager.shutdown()


def test_download_queue_stats() -> None:
    """测试统计功能"""
    manager = DownloadQueueManager(max_concurrent_downloads=3)

    # 提交一些任务
    for i in range(5):
        manager.submit_download(f"file_{i}")

    stats = manager.get_stats()

    assert stats["max_concurrent"] == 3
    assert stats["queue_size"] > 0
    assert "active_tasks" in stats
    assert isinstance(stats["active_tasks"], list)

    manager.shutdown()


def test_download_queue_mark_completed() -> None:
    """测试标记下载完成"""
    manager = DownloadQueueManager(max_concurrent_downloads=2)

    task = manager.submit_download("file_1")
    manager.wait_for_slot(task, timeout=5)

    # 此时应该在活跃下载中
    assert task.task_id in manager.active_downloads
    assert task.status == "processing"

    # 标记完成
    manager.mark_download_completed(task)

    # 应该移到已完成
    assert task.task_id in manager.completed_downloads
    assert task.task_id not in manager.active_downloads
    assert task.status == "completed"
    assert task.completed_at is not None

    manager.shutdown()


def test_download_queue_mark_failed() -> None:
    """测试标记下载失败"""
    manager = DownloadQueueManager(max_concurrent_downloads=2)

    task = manager.submit_download("file_1")
    manager.wait_for_slot(task, timeout=5)

    # 标记失败
    manager.mark_download_failed(task, "Network error")

    # 应该移到已完成
    assert task.task_id in manager.completed_downloads
    assert task.status == "failed"
    assert task.error == "Network error"

    manager.shutdown()


def test_download_queue_timeout() -> None:
    """测试超时功能"""
    manager = DownloadQueueManager(max_concurrent_downloads=1)

    # 占用唯一的槽位
    task1 = manager.submit_download("file_1")
    assert manager.wait_for_slot(task1, timeout=2)

    time.sleep(0.5)

    # 尝试在很短的超时内获得槽位（应该失败）
    task2 = manager.submit_download("file_2")
    ready = manager.wait_for_slot(task2, timeout=0.5)

    assert not ready
    assert task2.status == "failed"
    assert "timeout" in task2.error.lower()

    # 清理
    manager.mark_download_completed(task1)
    manager.shutdown()


def test_download_queue_multiple_managers() -> None:
    """测试多个管理器实例独立运作"""
    manager1 = DownloadQueueManager(max_concurrent_downloads=2)
    manager2 = DownloadQueueManager(max_concurrent_downloads=3)

    task1 = manager1.submit_download("file_1")
    task2 = manager2.submit_download("file_2")

    assert manager1.get_stats()["max_concurrent"] == 2
    assert manager2.get_stats()["max_concurrent"] == 3

    manager1.shutdown()
    manager2.shutdown()


def test_download_queue_stats_active_tasks_detail() -> None:
    """测试活跃任务详细信息"""
    manager = DownloadQueueManager(max_concurrent_downloads=2)

    task = manager.submit_download("test_file")
    manager.wait_for_slot(task, timeout=5)

    time.sleep(0.1)

    stats = manager.get_stats()
    active_tasks = stats["active_tasks"]

    assert len(active_tasks) > 0
    active_task = active_tasks[0]
    assert active_task["file_id"] == "test_file"
    assert active_task["task_id"] == task.task_id
    assert active_task["status"] == "processing"
    assert active_task["elapsed"] > 0

    manager.mark_download_completed(task)
    manager.shutdown()

