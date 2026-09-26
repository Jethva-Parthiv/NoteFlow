from groq import AsyncGroq
from app.config import settings

STT_PROMPT_HINT = (
    "NoteFlow, Notion, notes, tasks, pages, database, to-do list, journal, ideas, meeting notes, project."
)


async def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes using Groq Whisper Large v3 Turbo with English anchoring and low temperature."""
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not set in environment or .env file.")

    client = AsyncGroq(api_key=settings.groq_api_key)
    result = await client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3-turbo",
        language=settings.stt_language,
        temperature=0.0,
        prompt=STT_PROMPT_HINT,
    )
    return result.text
