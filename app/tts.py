import edge_tts
from app.config import settings


async def synthesize(text: str, voice: str | None = None) -> bytes:
    """Synthesize text to speech audio bytes using edge-tts."""
    if not text or not text.strip():
        return b""

    chosen_voice = voice or settings.tts_voice or "en-US-AriaNeural"
    communicate = edge_tts.Communicate(text, voice=chosen_voice)
    chunks = [c["data"] async for c in communicate.stream() if c["type"] == "audio"]
    return b"".join(chunks)
