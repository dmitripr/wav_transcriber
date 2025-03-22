from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import os
import shutil
import subprocess
import uuid
from pathlib import Path

app = FastAPI()

UPLOAD_DIR = Path("uploads")
TRANSCRIBE_DIR = Path("transcriptions")
UPLOAD_DIR.mkdir(exist_ok=True)
TRANSCRIBE_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

progress = {}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    job_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{job_id}.wav"
    output_path = TRANSCRIBE_DIR / f"{job_id}.txt"
    progress[job_id] = "starting"

    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(run_transcription, job_id, upload_path, output_path)
    return {"job_id": job_id}

def run_transcription(job_id: str, input_path: Path, output_path: Path):
    progress[job_id] = "running"
    try:
        cmd = [
            "whisper-cli",
            str(input_path),
            "--output", str(output_path),
            "--model", "base.en"
        ]
        subprocess.run(cmd, check=True)
        progress[job_id] = "done"
    except subprocess.CalledProcessError:
        progress[job_id] = "error"

@app.get("/progress/{job_id}")
async def get_progress(job_id: str):
    return {"status": progress.get(job_id, "unknown")}

@app.get("/download/{job_id}")
async def download_transcript(job_id: str):
    output_path = TRANSCRIBE_DIR / f"{job_id}.txt"
    if output_path.exists():
        return FileResponse(output_path, filename=f"transcription_{job_id}.txt")
    return {"error": "File not found"}