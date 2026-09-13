#file: trading_bot/infrastructure/config/settings.py
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _empty_to_none(value: str | None) -> str | None:
    return None if value is None or value == "" else value


class Settings(BaseSettings):
    app_name: str = "trading-bot"
    environment: Literal["local", "staging", "production"] = "local"
    debug: bool = True

    database_backend: Literal["postgresql"] = "postgresql"

    postgres_enabled: bool = True
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("postgres")
    postgres_db: str = "trading"
    postgres_schema: str = "public"
    postgres_sslmode: str = "prefer"
    postgres_dsn: str | None = None
    database_reset_on_start: bool = False
    preserve_broker_data_only: bool = True

    mt5_enabled: bool = False
    mt5_terminal_path: str | None = None
    mt5_login: int | None = None
    mt5_password: SecretStr | None = None
    mt5_server: str | None = None

    binance_api_key: SecretStr | None = None
    binance_api_secret: SecretStr | None = None

    stockbit_api_key: SecretStr | None = None
    stockbit_api_secret: SecretStr | None = None

    redis_url: str = "redis://localhost:6379/0"

    max_open_positions: int = 5
    max_daily_loss_pct: float = 2.0
    max_drawdown_pct: float = 10.0
    min_margin_buffer_pct: float = 25.0
    max_lot: float = 0.10
    default_risk_pct: float = 0.5
    kill_switch_enabled: bool = False

    @field_validator("mt5_terminal_path", "mt5_server", "binance_api_key", "binance_api_secret", "stockbit_api_key", "stockbit_api_secret", mode="before")
    @classmethod
    def _normalize_optional_string(cls, value: str | None) -> str | None:
        return _empty_to_none(value)

    @field_validator("mt5_login", mode="before")
    @classmethod
    def _normalize_mt5_login(cls, value: str | int | None) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @field_validator("mt5_password", mode="before")
    @classmethod
    def _normalize_mt5_password(cls, value: str | SecretStr | None) -> SecretStr | None:
        if value is None or value == "":
            return None
        return SecretStr(value)

    @property
    def postgres_url(self) -> str:
        password = self.postgres_password.get_secret_value() if self.postgres_password else ""
        if self.postgres_dsn:
            return self.postgres_dsn
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            f"?sslmode={self.postgres_sslmode}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
