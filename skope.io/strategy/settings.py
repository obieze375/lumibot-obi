"""Shared settings for skope.io."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_api_secret: str = Field(default="", alias="ALPACA_API_SECRET")
    alpaca_is_paper: bool = Field(default=True, alias="ALPACA_IS_PAPER")

    finnhub_api_key: str = Field(default="", alias="FINNHUB_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    skope_gemini_model: str = Field(default="gemini-2.0-flash", alias="SKOPE_GEMINI_MODEL")

    database_url: str = Field(default="", alias="DATABASE_URL")
    skope_api_token: str = Field(default="dev-token-change-me", alias="SKOPE_API_TOKEN")

    min_avg_volume: int = Field(default=500_000, alias="SKOPE_MIN_AVG_VOLUME")
    min_day_volume: int = Field(default=1_000_000, alias="SKOPE_MIN_DAY_VOLUME")
    min_rvol: float = Field(default=3.0, alias="SKOPE_MIN_RVOL")
    min_pct_change: float = Field(default=20.0, alias="SKOPE_MIN_PCT_CHANGE")
    position_pct: float = Field(default=0.10, alias="SKOPE_POSITION_PCT")
    take_profit_pct: float = Field(default=0.10, alias="SKOPE_TAKE_PROFIT_PCT")
    stop_loss_pct: float = Field(default=0.10, alias="SKOPE_STOP_LOSS_PCT")
    daily_loss_kill_pct: float = Field(default=0.10, alias="SKOPE_DAILY_LOSS_KILL_PCT")
    timezone: str = Field(default="Europe/London", alias="SKOPE_TIMEZONE")

    @property
    def effective_gemini_key(self) -> Optional[str]:
        return self.gemini_api_key or self.google_api_key or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
