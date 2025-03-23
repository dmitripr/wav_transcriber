from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import shutil
import subprocess
import uuid
from pathlib import Path

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

job_map = {}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    job_id = str(uuid.uuid4())
    original_filename = Path(file.filename).name
    upload_path = UPLOAD_DIR / original_filename
    output_path = upload_path.with_suffix(".txt")

    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job_map[job_id] = {
        "status": "starting",
        "input_path": upload_path,
        "output_path": output_path,
        "filename": original_filename
    }

    background_tasks.add_task(run_transcription, job_id)

    return RedirectResponse(url="/", status_code=303)

def run_transcription(job_id: str):
    job = job_map[job_id]
    original_path = job["input_path"]
    wav_path = original_path.with_suffix(".wav")


    job["status"] = "running"
    try:
        # Transcode to 16-bit mono WAV using ffmpeg
        job["status"] = "converting"
        cmd_ffmpeg = [
            "/usr/local/bin/ffmpeg", "-y", "-i", str(original_path), # using full path to ffmpeg binary
            "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
            str(wav_path)
        ]
        subprocess.run(cmd_ffmpeg, check=True)
        
        # Delete original file after conversion
        original_path.unlink()
        
        # Prepare final output path (WAV name + .txt)
        output_path = wav_path.with_name(wav_path.name + ".txt")

        # Run transcription using whisper.cpp
        job["status"] = "transcribing"
        cmd_whisper = [
            "/root/code/whisper.cpp/bin/whisper-cli",
            wav_path.name,
            "--model", "/root/code/whisper.cpp/models/ggml-base.en.bin",
            "-otxt"
        ]
        subprocess.run(cmd_whisper, check=True, cwd=wav_path.parent)

        job["output_path"] = output_path
        job["status"] = "done"
    except subprocess.CalledProcessError:
        job["status"] = "error"

@app.get("/jobs")
def list_jobs():
    return [
        {
            "job_id": job_id,
            "filename": job["filename"],
            "status": job["status"]
        }
        for job_id, job in job_map.items()
    ]

@app.get("/download/{job_id}")
def download(job_id: str):
    job = job_map.get(job_id)
    if not job:
        return {"error": "Job ID not found"}

    output_path = job["output_path"]
    if not output_path.exists():
        return {"error": "Transcript not found"}

    return FileResponse(output_path, filename=output_path.name)