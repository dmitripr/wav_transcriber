"""FastAPI application for transcribing media with whisper.cpp."""

import logging
import re
import shutil
import subprocess
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

import config
from joblog import JobLogStore
from jobs import JobStore, now

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))
transcriptions = JobStore(config.TRANSCRIPTION_DB, ("input_path", "output_path"))
audio_jobs = JobStore(config.AUDIO_DB, ("path",))
job_logs = JobLogStore(
    config.JOB_LOG_DIR, config.MAX_LOG_LINES, config.MAX_LOG_BYTES
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _remove_file(path) -> None:
    """Delete a file if it exists, logging (rather than raising) failures."""
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not remove %s: %s", path, exc)


def _sanitize_name(value: str, fallback: str) -> str:
    """Return a filesystem-safe version of a user supplied name."""
    name = Path(value or "").name
    name = re.sub(config.UNSAFE_FILENAME_PATTERN, "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        return fallback
    if len(name) > config.MAX_FILENAME_LENGTH:
        suffix = Path(name).suffix[:16]
        stem = name[: config.MAX_FILENAME_LENGTH - len(suffix)].rstrip(" .")
        name = f"{stem}{suffix}"
    return name


def _reserve_path(directory: Path, filename: str, job_id: str) -> Path:
    """Atomically reserve a unique path, adding a job-id suffix if taken."""
    candidate = directory / filename
    stem = candidate.stem or "file"
    suffix = candidate.suffix
    names = [filename, f"{stem}-{job_id[:8]}{suffix}"]
    names.extend(
        f"{stem}-{job_id[:8]}-{index}{suffix}" for index in range(1, 100)
    )

    for name in names:
        path = directory / name
        try:
            path.touch(exist_ok=False)
        except FileExistsError:
            continue
        return path

    raise RuntimeError(f"Could not allocate a unique file name for {filename}")


def _run_command(command) -> subprocess.CompletedProcess:
    """Run a command, surfacing stderr in the raised error message."""
    try:
        return subprocess.run(
            command, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(detail or f"Command failed: {' '.join(command)}")
    except OSError as exc:
        raise RuntimeError(f"Could not run {command[0]}: {exc}")


def _fetch_youtube_title(url: str, job_id: str) -> str:
    command = [str(config.YTDLP_PATH), *config.YTDLP_TITLE_ARGS, url]
    job_logs.command(job_id, command)
    result = _run_command(command)
    title = result.stdout.strip() or config.DEFAULT_TITLE
    job_logs.write(job_id, f"Resolved title: {title}")
    return title


def _youtube_output_path(url: str, job_id: str, extension: str) -> Path:
    """Resolve a human-readable, unique output path for a YouTube download."""
    title = _fetch_youtube_title(url, job_id)
    if title.lower().endswith(extension):
        title = title[: -len(extension)]

    filename = _sanitize_name(
        f"{title}{extension}",
        f"{config.DEFAULT_TITLE}{extension}",
    )
    output_path = _reserve_path(config.UPLOAD_DIR, filename, job_id)
    job_logs.write(job_id, f"Output file: {output_path.name}")
    return output_path


def _download_youtube_audio(
    url: str, job_id: str, output_path: Path, extension: str
) -> None:
    """Download the audio track to ``output_path``."""
    temp_path = config.UPLOAD_DIR / f"{job_id}{extension}"
    args = (
        config.YTDLP_MP3_ARGS
        if extension == config.MP3_EXTENSION
        else config.YTDLP_M4A_ARGS
    )
    command = [
        str(config.YTDLP_PATH),
        *args,
        "--ffmpeg-location",
        str(config.FFMPEG_PATH),
        "-o",
        str(temp_path),
        url,
    ]

    try:
        job_logs.command(job_id, command)
        _run_command(command)
        if not temp_path.is_file():
            raise RuntimeError("yt-dlp did not produce an audio file")
        temp_path.replace(output_path)
        job_logs.write(job_id, f"Audio downloaded to {output_path.name}")
    except BaseException:
        _remove_file(temp_path)
        _remove_file(output_path)
        raise


def _download_name(filename: str) -> str:
    path = Path(filename or "transcript")
    if path.suffix.lower() == config.TRANSCRIPT_SUFFIX:
        return path.name
    return path.with_suffix(config.TRANSCRIPT_SUFFIX).name


def _job_summary(job_id: str, job: dict) -> dict:
    return {
        "job_id": job_id,
        "filename": job.get("filename"),
        "start": job.get("start"),
        "end": job.get("end"),
        "status": job.get("status"),
        "progress": job.get("progress", 0),
        "error": job.get("error"),
    }


# --------------------------------------------------------------------------
# Background work
# --------------------------------------------------------------------------
def run_transcription(job_id: str) -> None:
    """Convert a media file to WAV and transcribe it with whisper-cli."""
    job = transcriptions.get(job_id)
    if job is None:
        return

    original_path = Path(job["input_path"]) if job.get("input_path") else None
    wav_path: Optional[Path] = None
    try:
        job_logs.write(
            job_id,
            f"Transcription started for {job.get('filename') or 'unknown file'}",
        )
        if original_path is None or not original_path.is_file():
            raise RuntimeError("Input file is missing")

        wav_path = original_path.with_name(
            original_path.stem + config.TRANSCODED_SUFFIX
        )
        transcriptions.update(
            job_id, status=config.STATUS_CONVERTING, progress=0, error=None
        )
        job_logs.write(job_id, "Converting input to 16 kHz mono WAV")
        convert_command = [
            str(config.FFMPEG_PATH),
            *config.FFMPEG_ARGS,
            "-i",
            str(original_path),
            str(wav_path),
        ]
        job_logs.command(job_id, convert_command)
        _run_command(convert_command)
        job_logs.write(job_id, "Conversion finished")
        original_path.unlink(missing_ok=True)
        transcriptions.update(job_id, input_path=None)

        transcriptions.update(job_id, status=config.STATUS_RUNNING)
        output_base = original_path.with_suffix("")
        output_path = output_base.with_suffix(config.TRANSCRIPT_SUFFIX)
        _remove_file(output_path)
        command = [
            str(config.WHISPER_CLI),
            str(wav_path),
            "--model",
            str(config.WHISPER_MODEL),
            config.WHISPER_OUTPUT_ARG,
            str(output_base),
            *config.WHISPER_ARGS,
        ]

        job_logs.write(job_id, "Starting whisper-cli")
        job_logs.command(job_id, command)
        tail = deque(maxlen=20)
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as process:
            for line in process.stdout:
                text = line.rstrip()
                tail.append(text)
                if text:
                    job_logs.write(job_id, text)
                match = re.search(config.PROGRESS_PATTERN, line)
                if match:
                    progress = max(0, min(100, int(match.group(1))))
                    transcriptions.update(job_id, progress=progress)
            returncode = process.wait()

        if returncode != 0:
            details = "\n".join(tail)
            raise RuntimeError(f"whisper-cli failed:\n{details}")
        if not output_path.is_file():
            raise RuntimeError("whisper-cli finished without producing a transcript")

        transcriptions.update(
            job_id,
            output_path=output_path,
            status=config.STATUS_DONE,
            progress=100,
            end=now(),
            error=None,
        )
        job_logs.write(job_id, f"Transcript written to {output_path.name}")
        job_logs.write(job_id, "Finished successfully")
    except Exception as exc:
        logger.exception("Transcription job %s failed", job_id)
        job_logs.error(job_id, exc)
        transcriptions.update(
            job_id, status=config.STATUS_ERROR, error=str(exc), end=now()
        )
    finally:
        _remove_file(wav_path)
        transcriptions.save()


def run_audio_download(job_id: str, url: str) -> None:
    """Download a YouTube URL as an MP3."""
    try:
        job_logs.write(job_id, "Resolving video title")
        audio_jobs.update(job_id, status=config.STATUS_FETCHING)
        output_path = _youtube_output_path(url, job_id, config.MP3_EXTENSION)
        audio_jobs.update(
            job_id,
            filename=output_path.name,
            path=output_path,
            status=config.STATUS_DOWNLOADING,
        )
        job_logs.write(job_id, "Downloading MP3 audio")
        _download_youtube_audio(url, job_id, output_path, config.MP3_EXTENSION)
        audio_jobs.update(
            job_id,
            filename=output_path.name,
            path=output_path,
            status=config.STATUS_DONE,
            end=now(),
            error=None,
        )
        job_logs.write(job_id, "Finished successfully")
    except Exception as exc:
        logger.exception("Audio download job %s failed", job_id)
        job_logs.error(job_id, exc)
        audio_jobs.update(
            job_id, status=config.STATUS_ERROR, error=str(exc), end=now()
        )
    finally:
        audio_jobs.save()


def run_youtube_transcription(job_id: str, url: str) -> None:
    """Download a YouTube URL's audio and transcribe it."""
    try:
        job_logs.write(job_id, "Resolving video title")
        transcriptions.update(job_id, status=config.STATUS_FETCHING)
        output_path = _youtube_output_path(url, job_id, config.M4A_EXTENSION)
        transcriptions.update(
            job_id,
            filename=output_path.name,
            input_path=output_path,
            status=config.STATUS_DOWNLOADING,
        )
        job_logs.write(job_id, "Downloading M4A audio for transcription")
        _download_youtube_audio(url, job_id, output_path, config.M4A_EXTENSION)
        run_transcription(job_id)
    except Exception as exc:
        logger.exception("YouTube transcription job %s failed", job_id)
        job_logs.error(job_id, exc)
        transcriptions.update(
            job_id, status=config.STATUS_ERROR, error=str(exc), end=now()
        )
        transcriptions.save()


# --------------------------------------------------------------------------
# Startup
# --------------------------------------------------------------------------
def _initialize_storage() -> None:
    for directory in (config.UPLOAD_DIR, config.JOB_STORAGE, config.JOB_LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    transcriptions.load()
    audio_jobs.load()

    # Jobs cannot survive a process restart; mark stale ones as failed.
    for store in (transcriptions, audio_jobs):
        changed = False
        for job_id, job in store.items():
            if job.get("status") in config.IN_PROGRESS_STATUSES:
                store.update(
                    job_id,
                    status=config.STATUS_ERROR,
                    error="Interrupted by server restart",
                    end=now(),
                )
                job_logs.write(
                    job_id, "ERROR: Interrupted by server restart"
                )
                changed = True
        if changed:
            store.save()

    # Remove logs whose jobs no longer exist (e.g. from a crash mid-clear).
    known_jobs = {
        job_id
        for store in (transcriptions, audio_jobs)
        for job_id, _ in store.items()
    }
    for log_file in config.JOB_LOG_DIR.glob("*.log"):
        if log_file.stem not in known_jobs:
            _remove_file(log_file)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _initialize_storage()
    yield


app = FastAPI(title="Media Transcriber", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    filename = _sanitize_name(file.filename or "", "upload")
    input_path = _reserve_path(config.UPLOAD_DIR, filename, job_id)

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except BaseException:
        _remove_file(input_path)
        raise

    transcriptions.create(
        job_id,
        filename=input_path.name,
        input_path=input_path,
        status=config.STATUS_QUEUED,
        progress=0,
        start=now(),
        end=None,
        error=None,
    )
    transcriptions.save()
    job_logs.reset(job_id, f"uploaded file {input_path.name}")
    job_logs.write(job_id, "Queued for transcription")
    background_tasks.add_task(run_transcription, job_id)
    return RedirectResponse(url="/", status_code=303)


@app.get("/jobs")
def list_jobs():
    return [_job_summary(job_id, job) for job_id, job in transcriptions.items()]


@app.get("/progress/{job_id}")
def progress(job_id: str):
    job = transcriptions.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"progress": job.get("progress", 0), "status": job.get("status")}


@app.get("/download/{job_id}")
def download(job_id: str):
    job = transcriptions.get(job_id)
    if job is None or job.get("status") != config.STATUS_DONE:
        raise HTTPException(status_code=404, detail="Transcription not available")

    path = Path(job["output_path"]) if job.get("output_path") else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Transcription file not found")

    return FileResponse(
        path,
        filename=_download_name(job.get("filename", "")),
        media_type="text/plain",
    )


@app.get("/logs/{job_id}", response_class=PlainTextResponse)
def get_job_log(job_id: str):
    if transcriptions.get(job_id) is None and audio_jobs.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    content = job_logs.read(job_id)
    if content is None:
        content = "No log recorded for this job.\n"
    return PlainTextResponse(content)


@app.delete("/jobs/{job_id}")
def delete_transcription_job(job_id: str):
    job = transcriptions.remove(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    _remove_file(job.get("input_path"))
    _remove_file(job.get("output_path"))
    job_logs.delete(job_id)
    transcriptions.save()
    return {"status": "deleted"}


@app.post("/yt_download")
def yt_download(background_tasks: BackgroundTasks, url: str = Form(...)):
    job_id = str(uuid.uuid4())
    audio_jobs.create(
        job_id,
        filename="Fetching title...",
        status=config.STATUS_STARTING,
        start=now(),
        end=None,
        error=None,
    )
    audio_jobs.save()
    job_logs.reset(job_id, f"YouTube MP3 download: {url}")
    background_tasks.add_task(run_audio_download, job_id, url)
    return RedirectResponse(url="/", status_code=303)


@app.post("/yt_transcribe")
def yt_transcribe(background_tasks: BackgroundTasks, url: str = Form(...)):
    job_id = str(uuid.uuid4())
    transcriptions.create(
        job_id,
        filename=url,
        status=config.STATUS_STARTING,
        progress=0,
        start=now(),
        end=None,
        error=None,
    )
    transcriptions.save()
    job_logs.reset(job_id, f"YouTube transcription: {url}")
    background_tasks.add_task(run_youtube_transcription, job_id, url)
    return RedirectResponse(url="/", status_code=303)


@app.get("/audio_jobs")
def list_audio_jobs():
    return [_job_summary(job_id, job) for job_id, job in audio_jobs.items()]


@app.get("/download_mp3/{job_id}")
def download_mp3(job_id: str):
    job = audio_jobs.get(job_id)
    if job is None or job.get("status") != config.STATUS_DONE:
        raise HTTPException(status_code=404, detail="Audio download not available")

    path = Path(job["path"]) if job.get("path") else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(path, filename=path.name, media_type="audio/mpeg")


@app.delete("/audio_jobs/{job_id}")
def delete_audio_job(job_id: str):
    job = audio_jobs.remove(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    _remove_file(job.get("path"))
    job_logs.delete(job_id)
    audio_jobs.save()
    return {"status": "deleted"}


@app.delete("/clear_transcriptions")
def clear_transcriptions():
    for job_id, job in transcriptions.clear():
        _remove_file(job.get("input_path"))
        _remove_file(job.get("output_path"))
        job_logs.delete(job_id)
    transcriptions.save()
    return {"status": "cleared"}


@app.delete("/clear_audio_jobs")
def clear_audio_jobs():
    for job_id, job in audio_jobs.clear():
        _remove_file(job.get("path"))
        job_logs.delete(job_id)
    audio_jobs.save()
    return {"status": "cleared"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level=config.LOG_LEVEL.lower(),
    )
