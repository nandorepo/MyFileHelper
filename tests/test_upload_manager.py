from __future__ import annotations

from modules.upload_manager import UploadQueueManager


def test_upload_manager_acquire_and_release() -> None:
    manager = UploadQueueManager(max_active_uploads=2)

    slot = manager.acquire_slot(timeout_seconds=1)
    assert slot is not None
    assert manager.get_stats()["active_uploads"] == 1

    manager.release_slot(slot)
    assert manager.get_stats()["active_uploads"] == 0


def test_upload_manager_timeout_when_full() -> None:
    manager = UploadQueueManager(max_active_uploads=1)

    slot = manager.acquire_slot(timeout_seconds=1)
    assert slot is not None

    second = manager.acquire_slot(timeout_seconds=1)
    assert second is None

    manager.release_slot(slot)

