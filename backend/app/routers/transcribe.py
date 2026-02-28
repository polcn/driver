import os
from pathlib import Path

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()

SUPPORTED_EXTENSIONS = {".ogg", ".mp4", ".m4a", ".mp3", ".wav", ".webm"}


def _whisper_url() -> str:
    return os.getenv("WHISPER_URL", "http://127.0.0.1:8200").rstrip("/")


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type: {extension}"
        )

    try:
        content = await file.read()
        response = httpx.post(
            f"{_whisper_url()}/transcribe",
            files={
                "file": (
                    file.filename or f"audio{extension}",
                    content,
                    file.content_type or "application/octet-stream",
                )
            },
            timeout=60.0,
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Whisper service unavailable")
    finally:
        await file.close()

    response.raise_for_status()
    payload = response.json()
    return {
        "text": payload.get("text", ""),
        "language": payload.get("language"),
    }
