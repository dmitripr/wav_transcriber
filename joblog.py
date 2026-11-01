"""Per-job process logs stored as plain text files."""

import logging
import shlex
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


class JobLogStore:
    """Thread-safe writer/reader for one log file per job."""

    def __init__(self, directory: Path, max_lines: int, max_bytes: int) -> None:
        self.directory = Path(directory)
        self.max_lines = max_lines
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def path(self, job_id: str) -> Path:
        return self.directory / f"{job_id}.log"

    def reset(self, job_id: str, title: str) -> None:
        """Start a fresh log for a newly created job."""
        try:
            with self._lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                self.path(job_id).write_text("", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not create log for %s: %s", job_id, exc)
        self.write(job_id, f"Job created: {title}")

    def write(self, job_id: str, message: str) -> None:
        timestamp = datetime.now().strftime(config.TIME_FORMAT)
        line = f"{timestamp}  {message}\n"
        try:
            with self._lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                path = self.path(job_id)
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(line)
                self._trim(path)
        except OSError as exc:
            logger.warning("Could not write log for %s: %s", job_id, exc)

    def command(self, job_id: str, command) -> None:
        self.write(job_id, f"$ {shlex.join(str(part) for part in command)}")

    def error(self, job_id: str, message) -> None:
        """Record an error without repeating a tool's own ``ERROR:`` prefix."""
        text = str(message).strip()
        while text.upper().startswith("ERROR:"):
            text = text[len("ERROR:") :].lstrip()
        self.write(job_id, f"ERROR: {text or 'Unknown error'}")

    def read(self, job_id: str) -> Optional[str]:
        with self._lock:
            path = self.path(job_id)
            if not path.is_file():
                return None
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return f"Could not read log: {exc}\n"

    def delete(self, job_id: str) -> None:
        with self._lock:
            try:
                self.path(job_id).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Could not remove log for %s: %s", job_id, exc)

    def _trim(self, path: Path) -> None:
        """Keep the log bounded, retaining the most recent lines and bytes."""
        try:
            if path.stat().st_size <= self.max_bytes:
                return
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            text = "\n".join(lines[-self.max_lines :]) + "\n"
            if len(text.encode("utf-8")) > self.max_bytes:
                tail = text.encode("utf-8")[-self.max_bytes :]
                text = tail.decode("utf-8", errors="ignore")
                newline = text.find("\n")
                text = text[newline + 1 :] if newline != -1 else ""
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not trim log %s: %s", path, exc)
