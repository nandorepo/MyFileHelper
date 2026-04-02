from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class UploadSlot:
    acquired_at: float


class UploadQueueManager:
    """Simple upload concurrency gate with blocking wait semantics."""

    def __init__(self, max_active_uploads: int) -> None:
        self.max_active_uploads = max(1, int(max_active_uploads))
        self._semaphore = threading.BoundedSemaphore(self.max_active_uploads)
        self._lock = threading.Lock()
        self._active = 0

    def acquire_slot(self, timeout_seconds: int) -> UploadSlot | None:
        timeout = max(1, int(timeout_seconds))
        acquired = self._semaphore.acquire(timeout=timeout)
        if not acquired:
            return None

        with self._lock:
            self._active += 1
        return UploadSlot(acquired_at=time.time())

    def release_slot(self, slot: UploadSlot | None) -> None:
        if slot is None:
            return
        with self._lock:
            if self._active > 0:
                self._active -= 1
        self._semaphore.release()

    def get_stats(self) -> dict:
        with self._lock:
            active = self._active
        return {
            "max_active_uploads": self.max_active_uploads,
            "active_uploads": active,
            "available_slots": max(0, self.max_active_uploads - active),
        }

