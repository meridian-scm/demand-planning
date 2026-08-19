"""Application configuration, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the demand planning service.

    Every value can be overridden with an environment variable of the same
    name (case-insensitive), or via a local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Service ----
    app_name: str = "Meridian Demand Planning API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # ---- Database ----
    database_url: str = (
        "postgresql+psycopg://meridian:meridian@localhost:5432/meridian_demand"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # ---- CORS ----
    # NoDecode: pydantic-settings would otherwise try to JSON-parse the env
    # var before our validator runs, which fails on a plain comma-separated
    # string like "http://a,http://b". NoDecode hands the raw string straight
    # to the validator below instead.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
        ]
    )

    # ---- Forecasting defaults ----
    forecast_default_horizon: int = 6
    forecast_min_history_periods: int = 4
    forecast_backtest_holdout: int = 3
    forecast_seasonal_periods: int = 12

    # ---- Exception detection thresholds ----
    spike_threshold_pct: float = 25.0
    drop_threshold_pct: float = 25.0
    zscore_threshold: float = 2.0
    stockout_cover_periods: float = 1.0
    excess_cover_periods: float = 4.0

    # ---- AI ----
    ai_enabled: bool = True
    # Which LLM provider InsightService uses as its primary. "ollama" needs a
    # locally-running daemon; "groq" needs GROQ_API_KEY and talks to Groq's
    # hosted API instead — no local model required.
    ai_provider: Literal["ollama", "groq"] = "ollama"
    # When the configured provider is unreachable/misconfigured, the service
    # falls back to deterministic, template-driven narratives instead of
    # failing the request.
    ai_fallback_enabled: bool = True

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_timeout_seconds: float = 60.0

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    groq_timeout_seconds: float = 30.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow CORS origins to be supplied as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_testing(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()


settings = get_settings()
