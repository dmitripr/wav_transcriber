"""Thread-safe, JSON-backed storage for background jobs."""

import json
import logging
import os
import tempfile
import threading
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


def now() -> str:
    """Current timestamp in the configured format."""
    return datetime.now().strftime(config.TIME_FORMAT)


def _atomic_write(path: Path, payload: dict) -> None:
    """Write JSON to a temporary file, then replace the target atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


class JobStore:
    """A dict-like collection of jobs persisted to a JSON file.

    All public methods are safe to call from the request thread pool. Call
    ``save()`` after mutating jobs to persist them to disk.
    """

    def __init__(self, path: Path, path_fields: Iterable[str]) -> None:
        self.path = Path(path)
        self.path_fields = tuple(path_fields)
        self._jobs: dict[str, dict] = {}
        self._lock = threading.RLock()

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job is not None else None

    def create(self, job_id: str, **fields) -> dict:
        with self._lock:
            self._jobs[job_id] = dict(fields)
            return dict(self._jobs[job_id])

    def update(self, job_id: str, **fields) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.update(fields)
            return dict(job)

    def remove(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.pop(job_id, None)
            return dict(job) if job is not None else None

    def clear(self) -> list[tuple[str, dict]]:
        with self._lock:
            removed = [
                (job_id, dict(job)) for job_id, job in self._jobs.items()
            ]
            self._jobs.clear()
            return removed

    def items(self) -> list[tuple[str, dict]]:
        with self._lock:
            return [(job_id, dict(job)) for job_id, job in self._jobs.items()]

    def save(self) -> None:
        with self._lock:
            payload = {}
            for job_id, job in self._jobs.items():
                item = dict(job)
                for field in self.path_fields:
                    value = item.get(field)
                    item[field] = str(value) if value else None
                payload[job_id] = item
            _atomic_write(self.path, payload)

    def load(self) -> None:
        with self._lock:
            self._jobs.clear()
            if not self.path.exists():
                return
            try:
                with open(self.path, encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, ValueError) as exc:
                logger.error("Could not load jobs from %s: %s", self.path, exc)
                return

            if not isinstance(payload, dict):
                logger.error("Ignoring invalid job data in %s", self.path)
                return

            for job_id, job in payload.items():
                item = dict(job)
                for field in self.path_fields:
                    value = item.get(field)
                    item[field] = Path(value) if value else None
                self._jobs[job_id] = item
