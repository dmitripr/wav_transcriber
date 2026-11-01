"""Central configuration for the WAV transcriber.

Every path, executable and tunable value used by the Python code lives in this
module. Each setting can be overridden with the environment variable noted in
the comment, so deployments can change paths without editing source files.

Example:
    WAV_WHISPER_CLI=/usr/local/bin/whisper-cli \
    WAV_WHISPER_MODEL=/models/ggml-base.en.bin \
    python3 main.py
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default) -> Path:
    """Return an absolute path from an env var, resolving relatives to BASE_DIR."""
    value = os.environ.get(name)
    path = Path(value).expanduser() if value else Path(default)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


# --- Server ---------------------------------------------------------------
HOST = _env("WAV_HOST", "0.0.0.0")  # WAV_HOST
PORT = _env_int("WAV_PORT", 8000)  # WAV_PORT
RELOAD = _env_bool("WAV_RELOAD", False)  # WAV_RELOAD
LOG_LEVEL = _env("WAV_LOG_LEVEL", "INFO")  # WAV_LOG_LEVEL

# --- Directories ----------------------------------------------------------
UPLOAD_DIR = _env_path("WAV_UPLOAD_DIR", BASE_DIR / "uploads")  # WAV_UPLOAD_DIR
JOB_STORAGE = _env_path("WAV_JOB_DIR", BASE_DIR / "jobs")  # WAV_JOB_DIR
TEMPLATES_DIR = _env_path("WAV_TEMPLATES_DIR", BASE_DIR / "templates")  # WAV_TEMPLATES_DIR
STATIC_DIR = _env_path("WAV_STATIC_DIR", BASE_DIR / "static")  # WAV_STATIC_DIR

# --- Persistence ----------------------------------------------------------
TRANSCRIPTION_DB = JOB_STORAGE / "transcriptions.json"
AUDIO_DB = JOB_STORAGE / "audio_jobs.json"
JOB_LOG_DIR = _env_path("WAV_LOG_DIR", JOB_STORAGE / "logs")  # WAV_LOG_DIR

# --- Process logs ---------------------------------------------------------
MAX_LOG_LINES = _env_int("WAV_MAX_LOG_LINES", 1000)  # WAV_MAX_LOG_LINES
MAX_LOG_BYTES = _env_int("WAV_MAX_LOG_BYTES", 256 * 1024)  # WAV_MAX_LOG_BYTES

# --- External executables -------------------------------------------------
WHISPER_CLI = _env_path(
    "WAV_WHISPER_CLI", "/root/code/whisper.cpp/build/bin/whisper-cli"
)  # WAV_WHISPER_CLI
WHISPER_MODEL = _env_path(
    "WAV_WHISPER_MODEL", "/root/code/whisper.cpp/models/ggml-small.en.bin"
)  # WAV_WHISPER_MODEL
FFMPEG_PATH = _env_path("WAV_FFMPEG", "/usr/local/bin/ffmpeg")  # WAV_FFMPEG
YTDLP_PATH = _env_path("WAV_YTDLP", "/usr/local/bin/yt-dlp")  # WAV_YTDLP

# --- Media processing -----------------------------------------------------
TRANSCODED_SUFFIX = ".transcoded.wav"
TRANSCRIPT_SUFFIX = ".txt"
FFMPEG_ARGS = (
    "-y",
    "-loglevel",
    "error",
    "-vn",
    "-acodec",
    "pcm_s16le",
    "-ac",
    "1",
    "-ar",
    "16000",
)
WHISPER_ARGS = ("-otxt", "-pp")
WHISPER_OUTPUT_ARG = "-of"
PROGRESS_PATTERN = r"progress\s*=\s*(\d+)%"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_FILENAME_LENGTH = 120
UNSAFE_FILENAME_PATTERN = r'[\\/:*?"<>|\x00-\x1f]'

# --- YouTube / yt-dlp -----------------------------------------------------
YTDLP_TITLE_ARGS = ("--get-title",)
YTDLP_MP3_ARGS = ("-x", "--audio-format", "mp3")
YTDLP_M4A_ARGS = ("-f", "bestaudio", "--extract-audio", "--audio-format", "m4a")
MP3_EXTENSION = ".mp3"
M4A_EXTENSION = ".m4a"
DEFAULT_TITLE = "audio"

# --- Job statuses ---------------------------------------------------------
STATUS_QUEUED = "queued"
STATUS_STARTING = "starting"
STATUS_FETCHING = "fetching title"
STATUS_DOWNLOADING = "downloading"
STATUS_CONVERTING = "converting"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"

IN_PROGRESS_STATUSES = frozenset(
    {
        STATUS_QUEUED,
        STATUS_STARTING,
        STATUS_FETCHING,
        STATUS_DOWNLOADING,
        STATUS_CONVERTING,
        STATUS_RUNNING,
    }
)
