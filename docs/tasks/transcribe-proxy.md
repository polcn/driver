# Task: Add /transcribe Proxy Endpoint to Driver

## Overview
Add `POST /api/v1/transcribe` to the Driver FastAPI backend. This endpoint accepts an audio file upload, forwards it to the local Whisper service running on `http://127.0.0.1:8200/transcribe`, and returns the transcript. This allows McGrupp (running in Docker, on Tailscale) to reach the Whisper service indirectly via Driver.

## Architecture
```
McGrupp (Docker) 
  → https://craigs-mac-mini.tail3d8c4d.ts.net:8443/api/v1/transcribe
  → Driver backend (http://127.0.0.1:8100)
  → Whisper service (http://127.0.0.1:8200/transcribe)
  → returns {"text": "...", "language": "..."}
```

Whisper stays localhost-only. Driver is the only thing that talks to it.

## File to Create

### `backend/app/routers/transcribe.py`

```python
POST /transcribe
- Accepts: multipart file upload (field name: "file")
- Supported formats: .ogg, .mp4, .m4a, .mp3, .wav, .webm
- Forwards file to http://127.0.0.1:8200/transcribe via httpx
- Returns: {"text": "...", "language": "..."}
- On Whisper service unavailable (ConnectError): return 503 {"detail": "Whisper service unavailable"}
- On bad file type: return 400 {"detail": "Unsupported file type: {ext}"}
- Whisper URL configurable via env var WHISPER_URL (default: http://127.0.0.1:8200)
```

## File to Modify

### `backend/app/main.py`
Register the router:
```python
from .routers import transcribe
app.include_router(transcribe.router, prefix="/api/v1", tags=["transcribe"])
```

## Tests: `tests/test_transcribe.py`

1. POST valid audio file → forwards to Whisper mock → returns transcript
2. POST unsupported file type → 400
3. Whisper service unavailable → 503
4. WHISPER_URL env var overrides default

## Constraints
- Use httpx (already in requirements.txt) for the forwarding request
- No new dependencies
- Timeout: 60 seconds (transcription can take a few seconds on large files)
- Stream the file bytes through — don't buffer to disk in Driver
