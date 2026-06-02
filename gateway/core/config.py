from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "NexusLLM Gateway"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    database_url: str = "postgresql+asyncpg://nexus:nexus@db:5432/nexusllm"
    redis_url: str = "redis://redis:6379/0"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    api_key_prefix: str = "nx"
    default_rate_limit_rpm: int = 60
    default_rate_limit_tpd: int = 100_000
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()