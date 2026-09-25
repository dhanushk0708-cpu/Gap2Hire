from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Gap2Hire API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str
    jwt_secret_key: str
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    storage_dir: str = "uploads"
    max_resume_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    enable_demo_import: bool = True

    # Voice / Audio Settings
    stt_provider: str = "groq"
    stt_api_key: str = ""
    stt_model: str = "whisper-large-v3"
    tts_provider: str = "openai"
    tts_api_key: str = ""
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    max_voice_message_size_bytes: int = 5 * 1024 * 1024  # 5 MB

    # Source Inspection & Discovery Settings
    source_inspection_timeout_seconds: float = 10.0
    source_inspection_max_response_bytes: int = 2 * 1024 * 1024  # 2 MB
    source_inspection_max_text_chars: int = 50000
    source_discovery_max_links: int = 50
    max_research_iterations: int = 10


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()