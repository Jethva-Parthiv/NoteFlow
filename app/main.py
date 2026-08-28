import os
import traceback
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent import process_note
from app.config import settings
from app.stt import transcribe
from app.tts import synthesize

app = FastAPI(title="NoteFlow", description="Voice-to-Notion Personal Capture Agent")

# CORS middleware for local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for the latest audio confirmation
_latest_audio_bytes: bytes = b""

STATIC_DIR = Path(__file__).parent / "static"

@app.get("/api/health")
async def health_check():
    """Check system health and API key configuration status."""
    return {
        "status": "ok",
        "google_api_key_set": bool(settings.google_api_key),
        "groq_api_key_set": bool(settings.groq_api_key),
        "notion_mcp_url": settings.notion_mcp_url,
    }


@app.post("/api/voice-note")
async def voice_note(
    audio: UploadFile | None = File(None),
    text: str | None = Form(None),
):
    """
    Process a voice note or typed thought:
    1. STT (Groq whisper-large-v3-turbo) if audio is uploaded
    2. LangGraph ReAct agent + Notion MCP + Gemini 2.5 Flash to file note
    3. Edge TTS on confirmation text -> audio
    """
    global _latest_audio_bytes

    transcript = ""

    if audio is not None:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file received.")
        filename = audio.filename or "audio.webm"
        try:
            transcript = await transcribe(audio_bytes, filename=filename)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Speech-to-text error: {str(e)}",
            )
    elif text and text.strip():
        transcript = text.strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="Either an audio file or a text parameter must be provided.",
        )

    if not transcript.strip():
        raise HTTPException(
            status_code=400,
            detail="No speech could be detected in the provided audio.",
        )
    print("Transcript:", transcript)
    # 2. Agent filing via Notion MCP
    try:
        confirmation_text = await process_note(transcript)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Agent filing error: {str(e)}",
        )

    # 3. Spoken confirmation TTS
    audio_url = ""
    try:
        _latest_audio_bytes = await synthesize(confirmation_text)
        if _latest_audio_bytes:
            audio_url = "/api/audio/latest.mp3"
    except Exception as e:
        # If TTS fails, still return confirmation text
        print(f"Warning: TTS synthesis failed: {e}")
        audio_url = ""

    return {
        "transcript": transcript,
        "confirmation_text": confirmation_text,
        "confirmation_audio_url": audio_url,
    }


@app.get("/api/audio/latest.mp3")
async def get_latest_audio():
    """Stream the latest synthesized confirmation audio."""
    global _latest_audio_bytes
    if not _latest_audio_bytes:
        raise HTTPException(status_code=404, detail="No audio available.")
    return Response(content=_latest_audio_bytes, media_type="audio/mpeg")


# Serve static frontend files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve main web UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "NoteFlow Backend Running"}
