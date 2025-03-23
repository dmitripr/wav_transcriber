# 🎧 WAV Transcriber Web Server (FastAPI + Whisper.cpp + FFmpeg)

This project provides a simple and clean web-based transcription tool that allows users to upload audio or video files (e.g. `.mp3`, `.mp4`, `.wav`, `.m4a`, `.mov`, etc.), automatically transcodes them to 16-bit mono WAV using `ffmpeg`, and transcribes them using [whisper.cpp](https://github.com/ggerganov/whisper.cpp)'s `whisper-cli`.

Built to run inside a **FreeBSD jail** (e.g., on TrueNAS CORE), but portable to any environment with Python, `ffmpeg`, and `whisper-cli`.

---

## 🚀 Features

- Upload audio or video files via browser
- Converts uploaded files to 16-bit mono WAV with `ffmpeg`
- Transcribes them using `whisper-cli`
- Automatically deletes original upload after conversion
- Downloadable `.txt` transcription output
- Lightweight UI (HTML + CSS, no frontend framework)

---

## 📦 Requirements

- Python 3.9+
- `fastapi`, `uvicorn`, `jinja2` (see `requirements.txt`)
- `ffmpeg` installed (e.g., `pkg install ffmpeg` on FreeBSD)
- [`whisper.cpp`](https://github.com/ggerganov/whisper.cpp) compiled and accessible

---

## 🛠 Setup

### 1. Clone the repo

```sh
git clone https://github.com/yourname/wav_transcriber.git
cd wav_transcriber
```

### 2. Install Python dependencies

```sh
pip install fastapi uvicorn jinja2
```

### 3. Install FFmpeg (if not already)

```sh
pkg install ffmpeg
```

### 4. Build or download `whisper.cpp`

Clone [whisper.cpp](https://github.com/ggerganov/whisper.cpp) and follow its build instructions:

```sh
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make
```

Download a model (e.g., `ggml-base.en.bin`) and place it in a folder like:

```
~/code/whisper.cpp/models/
```

---

## ⚙ Configuration Notes

### Default paths used in `main.py` (edit if needed):

```python
WHISPER_CLI = "/root/code/whisper.cpp/bin/whisper-cli"
MODEL_PATH = "/root/code/whisper.cpp/models/ggml-base.en.bin"
UPLOAD_DIR = "/root/wav_transcriber/uploads"
```

> 🔧 Update these paths if your jail or system uses different directories.

---

## ▶ Run the App

```sh
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Visit your browser at: [http://localhost:8000](http://localhost:8000)

---

## 🧼 Autostart in FreeBSD Jail (optional)

1. Create an RC script in `/usr/local/etc/rc.d/wavtranscriber`
2. Enable with: `sysrc wavtranscriber_enable=YES`
3. Add service logic to auto-start `uvicorn` in the app directory

---

## 📁 Output Files

- Transcripts are saved as `.txt` in the `uploads/` directory
- Filenames are cleaned to match the original media name (e.g., `interview.mp4 → interview.txt`)

---

## 🙌 Credits

- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp) by Georgi Gerganov
- [FFmpeg](https://ffmpeg.org/)
- [FastAPI](https://fastapi.tiangolo.com/)

---

## 🛡 License

MIT — use freely, modify boldly!