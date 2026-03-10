"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM Configuration
    llm_provider: Literal["openai", "anthropic", "google"] = "openai"
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str = "local-model"
    llm_temperature: float = 0.0
    llm_api_key: str = ""

    # Database Configuration
    database_url: str = ""

    # Agent Configuration
    max_retry_attempts: int = 3
    query_timeout_seconds: int = 30

    # SQL Query Configuration
    default_result_limit: int = 1000  # Default TOP limit for SELECT queries
    max_result_limit: int = 1000  # Maximum allowed TOP limit

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Seq Logging Configuration
    seq_server_url: str = "http://localhost:5341"
    seq_api_key: str = ""

    # Conversational Memory Configuration
    conversation_memory_limit: int = 5  # Max prior exchanges in LLM context
    session_ttl_minutes: int = 60  # Redis session expiry (minutes)
    redis_url: str = "redis://:langfuseredis@localhost:6379/1"  # DB 1 to isolate from Langfuse

    # Langfuse Observability Configuration
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "http://localhost:3000"
    # Max characters stored in Langfuse for prompt/response payloads
    langfuse_prompt_truncate_limit: int = 500
    langfuse_response_truncate_limit: int = 1000

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
