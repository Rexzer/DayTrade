"""Application configuration.

Reads settings from environment variables (12-factor style). Uses only the
standard library so it can be imported and tested without third-party
settings libraries. There are NO secret defaults — SECRET_KEY has no usable
default in production, and the trading locks default to OFF.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _get_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    """Typed view over the environment."""

    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "RexDayTrades"))
    app_debug: bool = field(default_factory=lambda: _get_bool("APP_DEBUG", True))

    backend_host: str = field(default_factory=lambda: os.getenv("BACKEND_HOST", "0.0.0.0"))
    backend_port: int = field(default_factory=lambda: _get_int("BACKEND_PORT", 8000))
    cors_origins: list[str] = field(
        default_factory=lambda: _get_list("CORS_ORIGINS", ["http://localhost:3000"])
    )

    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    access_token_expire_minutes: int = field(
        default_factory=lambda: _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    )
    jwt_algorithm: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))

    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # --- Market data (Phase 2) ----------------------------------------------
    # Provider: "none" (null), "simulated" (labelled synthetic feed for offline
    # dev), or "rest" (generic HTTP quote poller — needs network + config).
    market_data_provider: str = field(
        default_factory=lambda: os.getenv("MARKET_DATA_PROVIDER", "none")
    )
    market_data_symbol: str = field(
        default_factory=lambda: os.getenv("MARKET_DATA_SYMBOL", "XAUUSD")
    )
    market_tick_interval_seconds: float = field(
        default_factory=lambda: float(os.getenv("MARKET_TICK_INTERVAL_SECONDS", "1.0"))
    )
    data_delayed_after_seconds: float = field(
        default_factory=lambda: float(os.getenv("DATA_DELAYED_AFTER_SECONDS", "3.0"))
    )
    data_stale_after_seconds: float = field(
        default_factory=lambda: float(os.getenv("DATA_STALE_AFTER_SECONDS", "10.0"))
    )
    market_history_candles: int = field(
        default_factory=lambda: _get_int("MARKET_HISTORY_CANDLES", 300)
    )

    # Hard safety locks. Phase 1 refuses to honour these even if set true;
    # they are surfaced so operators can see the intended future switches.
    enable_paper_trading: bool = field(
        default_factory=lambda: _get_bool("ENABLE_PAPER_TRADING", False)
    )
    enable_live_trading: bool = field(
        default_factory=lambda: _get_bool("ENABLE_LIVE_TRADING", False)
    )
    # Live ORDER execution via a broker. Implemented only in Phase 7; the
    # execution provider refuses writes regardless of this flag in Phase 6.
    live_execution_enabled: bool = field(
        default_factory=lambda: _get_bool("LIVE_EXECUTION_ENABLED", False)
    )

    # --- MetaTrader 5 (Phase 6, read-only) ----------------------------------
    # The password is read from the environment only and is NEVER logged or
    # returned by the API. Prefer a secret store in production.
    mt5_login: int | None = field(
        default_factory=lambda: (int(os.getenv("MT5_LOGIN")) if os.getenv("MT5_LOGIN") else None)
    )
    mt5_server: str | None = field(default_factory=lambda: os.getenv("MT5_SERVER") or None)
    mt5_path: str | None = field(default_factory=lambda: os.getenv("MT5_PATH") or None)
    mt5_symbol: str = field(default_factory=lambda: os.getenv("MT5_SYMBOL", "XAUUSD"))

    @property
    def mt5_password(self) -> str | None:
        # Not stored on the instance to reduce accidental exposure in reprs/logs.
        return os.getenv("MT5_PASSWORD") or None

    @property
    def live_api_token(self) -> str | None:
        # Shared operator secret guarding the dangerous live-trading endpoints.
        # Read from env only; never stored on the instance, logged or returned.
        return os.getenv("LIVE_API_TOKEN") or None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_url(self) -> str:
        explicit = os.getenv("DATABASE_URL")
        if explicit:
            return explicit
        user = os.getenv("POSTGRES_USER", "xauusd")
        password = os.getenv("POSTGRES_PASSWORD", "change-me")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        name = os.getenv("POSTGRES_DB", "xauusd")
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"

    def validate(self) -> list[str]:
        """Return configuration problems (empty list = OK)."""
        problems: list[str] = []
        _placeholder_secret = "change-me-to-a-long-random-string"
        if self.is_production and (not self.secret_key or self.secret_key == _placeholder_secret):
            problems.append("SECRET_KEY must be set to a strong value in production.")
        # Safety invariant: fully-autonomous live auto-trading is intentionally
        # NOT enabled. ENABLE_LIVE_TRADING must remain false (the platform never
        # auto-executes signals without a human). LIVE_EXECUTION_ENABLED is a
        # legitimate advanced precondition for the manual, explicitly-authorized
        # live-execution flow, so it is allowed to be true.
        if self.enable_live_trading:
            problems.append(
                "ENABLE_LIVE_TRADING must be false; the platform does not "
                "auto-execute trades. Use the explicit live-execution "
                "authorization flow instead (LIVE_EXECUTION_ENABLED)."
            )
        return problems


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
