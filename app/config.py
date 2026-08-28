from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_api_key: str = ""
    groq_api_key: str = ""
    tts_voice: str = "en-US-AriaNeural"
    notion_mcp_url: str = "https://mcp.notion.com/mcp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
