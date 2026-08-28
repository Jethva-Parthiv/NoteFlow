import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ for LangSmith and standard libraries
load_dotenv(override=True)


class Settings(BaseSettings):
    google_api_key: str = ""
    groq_api_key: str = ""
    notion_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    tts_voice: str = "en-US-AriaNeural"
    notion_mcp_url: str = "https://mcp.notion.com/mcp"

    # LangSmith Tracing
    langchain_tracing_v2: str = "false"
    langchain_api_key: str = ""
    langchain_project: str = "NoteFlow"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure LangSmith environment variables are explicitly set in os.environ
if settings.langchain_tracing_v2.lower() in ("true", "1", "yes"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    if settings.langchain_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    if settings.langchain_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
