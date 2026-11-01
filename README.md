# WAV Transcriber Web Server (FastAPI + Whisper.cpp + FFmpeg)

This project provides a flexible web-based transcription tool that allows users to upload media files (e.g., `.mp3`, `.mp4`, `.wav`, `.m4a`, `.mov`, etc.), or paste a YouTube link to download and transcribe or extract audio. It uses `ffmpeg` to convert input to 16-bit mono WAV files, then transcribes them using [whisper.cpp](https://github.com/ggerganov/whisper.cpp)'s `whisper-cli`.

Built for deployment inside a FreeBSD jail (e.g., on TrueNAS CORE), but portable to any environment with Python, `ffmpeg`, and `whisper-cli`.

## Features

- Upload audio/video files directly from browser
- Paste a YouTube URL to:
  - Transcribe the video
  - Or just download the MP3 audio
- Automatic conversion to 16-bit mono WAV using `ffmpeg`
- Transcription via `whisper-cli`
- Downloadable `.txt` transcription output
- Per-job process logs with captured commands, progress and errors
- Clear or delete individual jobs without clearing everything
- Supports multiple simultaneous jobs
- Job metadata persisted across restarts

## Requirements

- Python 3.9+
- Python packages:
  - fastapi, uvicorn, jinja2, python-multipart (see `requirements.txt`)
- System tools:
  - ffmpeg
  - yt-dlp
- Compiled version of [whisper.cpp](https://github.com/ggerganov/whisper.cpp)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourname/wav_transcriber.git
cd wav_transcriber
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg and yt-dlp

```bash
pkg install ffmpeg yt-dlp
```

Or if unavailable via pkg:

```bash
pip install yt-dlp
```

### 4. Build whisper.cpp

Note: depending on your OS, you may need to install 'cmake' package. 

```bash
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build
cmake --build build --config Release
```

Download a model file:

```bash
./models/download-ggml-model.sh base.en
```

Place model in a known directory, e.g.:

```
~/code/whisper.cpp/models/
```

## Configuration

All paths, executables and tunables are defined in [`config.py`](config.py).
You can either edit that file or override each value with an environment
variable, which is preferred for deployments:

| Setting | Environment variable | Default |
| --- | --- | --- |
| whisper-cli binary | `WAV_WHISPER_CLI` | `/root/code/whisper.cpp/build/bin/whisper-cli` |
| Whisper model | `WAV_WHISPER_MODEL` | `/root/code/whisper.cpp/models/ggml-small.en.bin` |
| ffmpeg binary | `WAV_FFMPEG` | `/usr/local/bin/ffmpeg` |
| yt-dlp binary | `WAV_YTDLP` | `/usr/local/bin/yt-dlp` |
| Upload directory | `WAV_UPLOAD_DIR` | `./uploads` |
| Job metadata directory | `WAV_JOB_DIR` | `./jobs` |
| Process log directory | `WAV_LOG_DIR` | `./jobs/logs` |
| Templates directory | `WAV_TEMPLATES_DIR` | `./templates` |
| Static files directory | `WAV_STATIC_DIR` | `./static` |
| Listen host | `WAV_HOST` | `0.0.0.0` |
| Listen port | `WAV_PORT` | `8000` |
| Auto-reload | `WAV_RELOAD` | `false` |
| Log level | `WAV_LOG_LEVEL` | `INFO` |

Relative paths are resolved against the project directory, so the app can be
started from anywhere. Example:

```bash
WAV_WHISPER_CLI=/usr/local/bin/whisper-cli \
WAV_WHISPER_MODEL=/models/ggml-base.en.bin \
WAV_UPLOAD_DIR=/var/lib/wavtranscriber/uploads \
WAV_JOB_DIR=/var/lib/wavtranscriber/jobs \
python3 main.py
```

## Running the App

```bash
python3 main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

```
http://localhost:8000
```

## Project layout

- `main.py` — FastAPI routes and background transcription/download jobs
- `config.py` — all configuration values and paths
- `jobs.py` — thread-safe, atomically persisted job store
- `joblog.py` — per-job process logs
- `templates/`, `static/` — web UI
- `uploads/`, `jobs/` — runtime data (ignored by git)

## Optional: Autostart in FreeBSD Jail

1. Create an RC script in `/usr/local/etc/rc.d/wavtranscriber`
2. Enable the service:

```bash
sysrc wavtranscriber_enable=YES
```

3. Configure it to start `python3 main.py` (or `uvicorn`) at boot

## Output

- Transcriptions are saved as `.txt` in the upload directory (default `uploads/`)
- Filenames are based on the original upload or YouTube title
- Uploads and downloads with duplicate names get a short job ID suffix
- Audio download jobs output `.mp3` files with clean names
- Deleted jobs also remove associated files
- Process logs are stored under `jobs/logs/` and available from the **Log** button

## Credits

- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp) by Georgi Gerganov
- [FFmpeg](https://ffmpeg.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## License

MIT — use freely, modify boldly.
