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
- Supports multiple simultaneous jobs
- Job metadata persisted across restarts

## Requirements

- Python 3.9+
- Python packages:
  - fastapi, uvicorn, jinja2
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
pip install fastapi uvicorn jinja2
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

```bash
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make
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

Edit paths in main.py to reflect your environment:

```python
WHISPER_CLI = "/root/code/whisper.cpp/bin/whisper-cli"
WHISPER_MODEL = "/root/code/whisper.cpp/models/ggml-base.en.bin"
FFMPEG_PATH = "/usr/local/bin/ffmpeg"
YTDLP_PATH = "/usr/local/bin/yt-dlp"
UPLOAD_DIR = "uploads"
```

## Running the App

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

```
http://localhost:8000
```

## Optional: Autostart in FreeBSD Jail

1. Create an RC script in `/usr/local/etc/rc.d/wavtranscriber`
2. Enable the service:

```bash
sysrc wavtranscriber_enable=YES
```

3. Configure it to start `uvicorn` at boot

## Output

- Transcriptions are saved as `.txt` in the `uploads/` folder
- Filenames are based on the original upload or YouTube title
- Audio download jobs output `.mp3` files with clean names
- Deleted jobs also remove associated files

## Credits

- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp) by Georgi Gerganov
- [FFmpeg](https://ffmpeg.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## License

MIT — use freely, modify boldly.