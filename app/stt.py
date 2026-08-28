from groq import AsyncGroq
from app.config import settings


async def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes using Groq Whisper Large v3 Turbo."""
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not set in environment or .env file.")

    client = AsyncGroq(api_key=settings.groq_api_key)
    result = await client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3-turbo",
    )
    return result.text
