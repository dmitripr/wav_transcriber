from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import shutil
import subprocess
import uuid
import re
from pathlib import Path

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

transcription_jobs = {}
audio_jobs = {}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    job_id = str(uuid.uuid4())
    original_filename = Path(file.filename).name
    input_path = UPLOAD_DIR / original_filename

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    transcription_jobs[job_id] = {
        "status": "starting",
        "input_path": input_path,
        "filename": original_filename
    }

    background_tasks.add_task(run_transcription, job_id)
    return RedirectResponse(url="/", status_code=303)

def run_transcription(job_id: str):
    job = transcription_jobs[job_id]
    original_path = job["input_path"]
    wav_path = original_path.with_name(original_path.stem + ".transcoded.wav")

    try:
        subprocess.run([
            "/usr/local/bin/ffmpeg", "-y", "-i", str(original_path),
            "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
            str(wav_path)
        ], check=True)
        original_path.unlink()

        output_path = wav_path.with_name(wav_path.name + ".txt")
        job["status"] = "running"
        job["progress"] = 0

        cmd = [
            "/root/code/whisper.cpp/bin/whisper-cli",
            wav_path.name,
            "--model", "/root/code/whisper.cpp/models/ggml-base.en.bin",
            "-otxt",
            "-pp"
        ]

        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=wav_path.parent, text=True) as proc:
            for line in proc.stdout:
                match = re.search(r"progress\s*=\s*(\d+)%", line)
                if match:
                    job["progress"] = int(match.group(1))

        proc.wait()
        final_output = original_path.with_suffix(".txt")
        Path(output_path).rename(final_output)
        wav_path.unlink()

        job["output_path"] = final_output
        job["status"] = "done"
        job["progress"] = 100
    except Exception as e:
        job["status"] = "error"
        print(f"[ERROR] Transcription job {job_id}: {e}")

@app.get("/jobs")
def list_jobs():
    return [
        {"job_id": job_id, "filename": job["filename"], "status": job["status"]}
        for job_id, job in transcription_jobs.items()
    ]

@app.get("/progress/{job_id}")
def progress(job_id: str):
    job = transcription_jobs.get(job_id)
    if not job:
        return {"progress": 0, "status": "not_found"}
    return {"progress": job.get("progress", 0), "status": job["status"]}

@app.get("/download/{job_id}")
def download(job_id: str):
    job = transcription_jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    output_path = job.get("output_path")
    if not output_path or not output_path.exists():
        return {"error": "Transcript not found"}
    return FileResponse(output_path, filename=output_path.name)

@app.post("/yt_transcribe")
async def yt_transcribe(url: str = Form(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    job_id = str(uuid.uuid4())
    transcription_jobs[job_id] = {"status": "downloading", "filename": url}
    background_tasks.add_task(download_and_transcribe_youtube, job_id, url)
    return RedirectResponse(url="/", status_code=303)

def download_and_transcribe_youtube(job_id: str, url: str):
    try:
        job = transcription_jobs[job_id]
        filename_base = f"yt_{job_id}"
        download_path = UPLOAD_DIR / f"{filename_base}.m4a"

        subprocess.run([
            "yt-dlp", "-f", "bestaudio", "--extract-audio",
            "--audio-format", "m4a", "-o", str(download_path),
            url
        ], check=True)

        job["input_path"] = download_path
        job["filename"] = f"YouTube: {url}"
        run_transcription(job_id)
    except Exception as e:
        job["status"] = "error"
        print(f"[ERROR] YouTube transcription {job_id}: {e}")

@app.post("/yt_download")
async def yt_download(url: str = Form(...)):
    job_id = str(uuid.uuid4())
    try:
        filename = f"yt_{job_id}.mp3"
        output_path = UPLOAD_DIR / filename

        subprocess.run([
            "yt-dlp", "-x", "--audio-format", "mp3",
            "-o", str(output_path),
            url
        ], check=True)

        audio_jobs[job_id] = {
            "filename": filename,
            "path": output_path
        }
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        print(f"[ERROR] YouTube download {job_id}: {e}")
        return {"error": "Download failed"}

@app.get("/audio_jobs")
def list_audio_jobs():
    return [
        {"job_id": job_id, "filename": job["filename"]}
        for job_id, job in audio_jobs.items()
    ]

@app.get("/download_mp3/{job_id}")
def download_mp3(job_id: str):
    job = audio_jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    path = job["path"]
    if not path.exists():
        return {"error": "MP3 not found"}
    return FileResponse(path, filename=path.name)

@app.delete("/audio_jobs/{job_id}")
def delete_audio_job(job_id: str):
    job = audio_jobs.pop(job_id, None)
    if job:
        try:
            job["path"].unlink()
        except Exception as e:
            print(f"[WARN] Could not delete file: {e}")
    return {"status": "deleted"}