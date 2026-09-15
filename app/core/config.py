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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()