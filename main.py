from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil
import subprocess
import uuid
import re
import os
import json
from pathlib import Path
from datetime import datetime

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
JOB_STORAGE = Path("jobs")
JOB_STORAGE.mkdir(exist_ok=True)
TRANSCRIPTION_FILE = JOB_STORAGE / "transcriptions.json"
AUDIO_FILE = JOB_STORAGE / "audio_jobs.json"

WHISPER_CLI = "/root/code/whisper.cpp/bin/whisper-cli"
WHISPER_MODEL = "/root/code/whisper.cpp/models/ggml-small.en-tdrz.bin"
FFMPEG_PATH = "/usr/local/bin/ffmpeg"
YTDLP_PATH = "/usr/local/bin/yt-dlp"

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

transcription_jobs = {}
audio_jobs = {}

def save_jobs():
    with open(TRANSCRIPTION_FILE, "w") as f:
        json.dump({k: {**v, "input_path": str(v.get("input_path", "")), "output_path": str(v.get("output_path", ""))} for k, v in transcription_jobs.items()}, f)
    with open(AUDIO_FILE, "w") as f:
        json.dump({k: {**v, "path": str(v.get("path", ""))} for k, v in audio_jobs.items()}, f)

def load_jobs():
    if TRANSCRIPTION_FILE.exists():
        with open(TRANSCRIPTION_FILE) as f:
            data = json.load(f)
            for k, v in data.items():
                v["input_path"] = Path(v["input_path"]) if v.get("input_path") else None
                v["output_path"] = Path(v["output_path"]) if v.get("output_path") else None
                transcription_jobs[k] = v

    if AUDIO_FILE.exists():
        with open(AUDIO_FILE) as f:
            data = json.load(f)
            for k, v in data.items():
                v["path"] = Path(v["path"]) if v.get("path") else None
                audio_jobs[k] = v

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    job_id = str(uuid.uuid4())
    input_path = UPLOAD_DIR / file.filename
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    transcription_jobs[job_id] = {
        "filename": file.filename,
        "input_path": input_path,
        "status": "queued",
        "start": datetime.now().isoformat(),
        "end": None
    }
    background_tasks.add_task(run_transcription, job_id)
    return RedirectResponse(url="/", status_code=303)

def run_transcription(job_id):
    job = transcription_jobs[job_id]
    original_path = job["input_path"]
    wav_path = original_path.with_name(original_path.stem + ".transcoded.wav")
    subprocess.run([FFMPEG_PATH, "-y", "-i", str(original_path), "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", str(wav_path)], check=True)
    original_path.unlink(missing_ok=True)
    output_path = wav_path.with_suffix(".txt")
    job["status"] = "running"
    cmd = [WHISPER_CLI, wav_path.name, "--model", WHISPER_MODEL, "-otxt", "-pp","-tdrz"]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=UPLOAD_DIR, text=True) as proc:
        for line in proc.stdout:
            match = re.search(r"progress\s*=\s*(\d+)%", line)
            if match:
                job["progress"] = int(match.group(1))
    if Path(output_path).exists():
        job["output_path"] = output_path
        job["status"] = "done"
        job["end"] = datetime.now().isoformat()
    wav_path.unlink(missing_ok=True)
    save_jobs()

@app.get("/jobs")
def list_jobs():
    return [{"job_id": k, "filename": v["filename"], "start": v.get("start"), "end": v.get("end"), "status": v["status"]} for k, v in transcription_jobs.items()]

@app.get("/progress/{job_id}")
def progress(job_id: str):
    job = transcription_jobs.get(job_id)
    return {"progress": job.get("progress", 0), "status": job["status"]}

@app.get("/download/{job_id}")
def download(job_id: str):
    job = transcription_jobs.get(job_id)
    path = job.get("output_path")
    return FileResponse(path, filename=path.name)

@app.post("/yt_download")
async def yt_download(url: str = Form(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    job_id = str(uuid.uuid4())
    audio_jobs[job_id] = {"filename": "Fetching title...", "status": "starting", "start": datetime.now().isoformat()}
    def run_download():
        try:
            title = subprocess.run([YTDLP_PATH, "--get-title", url], capture_output=True, text=True).stdout.strip()
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
            filename = f"{safe_title}.mp3"
            output_path = UPLOAD_DIR / filename
            audio_jobs[job_id].update({"filename": filename, "status": "downloading", "path": output_path})
            subprocess.run([YTDLP_PATH, "-x", "--audio-format", "mp3", "--ffmpeg-location", FFMPEG_PATH, "-o", str(output_path), url], check=True)
            audio_jobs[job_id]["status"] = "done"
            audio_jobs[job_id]["end"] = datetime.now().isoformat()
        except Exception as e:
            audio_jobs[job_id]["status"] = "error"
        save_jobs()
    background_tasks.add_task(run_download)
    return RedirectResponse(url="/", status_code=303)

@app.post("/yt_transcribe")
async def yt_transcribe(url: str = Form(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    job_id = str(uuid.uuid4())
    transcription_jobs[job_id] = {"status": "fetching title", "filename": url, "start": datetime.now().isoformat()}
    def run_transcribe():
        try:
            title = subprocess.run([YTDLP_PATH, "--get-title", url], capture_output=True, text=True).stdout.strip()
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
            filename = f"{safe_title}.m4a"
            download_path = UPLOAD_DIR / filename
            transcription_jobs[job_id].update({"filename": filename, "input_path": download_path, "status": "downloading"})
            subprocess.run([YTDLP_PATH, "-f", "bestaudio", "--extract-audio", "--audio-format", "m4a", "--ffmpeg-location", FFMPEG_PATH, "-o", str(download_path), url], check=True)
            run_transcription(job_id)
        except Exception as e:
            transcription_jobs[job_id]["status"] = "error"
        save_jobs()
    background_tasks.add_task(run_transcribe)
    return RedirectResponse(url="/", status_code=303)

@app.get("/audio_jobs")
def list_audio_jobs():
    return [{"job_id": k, "filename": v["filename"], "start": v.get("start"), "end": v.get("end"), "status": v["status"]} for k, v in audio_jobs.items()]

@app.get("/download_mp3/{job_id}")
def download_mp3(job_id: str):
    job = audio_jobs.get(job_id)
    return FileResponse(job["path"], filename=job["path"].name)

@app.delete("/audio_jobs/{job_id}")
def delete_audio_job(job_id: str):
    job = audio_jobs.pop(job_id, None)
    if job and job.get("path"):
        Path(job["path"]).unlink(missing_ok=True)
    save_jobs()
    return {"status": "deleted"}

@app.delete("/clear_transcriptions")
def clear_transcriptions():
    for job in transcription_jobs.values():
        for path in [job.get("input_path"), job.get("output_path")]:
            if path:
                Path(path).unlink(missing_ok=True)
    transcription_jobs.clear()
    save_jobs()
    return {"status": "cleared"}

@app.delete("/clear_audio_jobs")
def clear_audio_jobs():
    for job in audio_jobs.values():
        if job.get("path"):
            Path(job["path"]).unlink(missing_ok=True)
    audio_jobs.clear()
    save_jobs()
    return {"status": "cleared"}

load_jobs()