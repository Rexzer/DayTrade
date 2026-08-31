"""Provider-agnostic market-data interface (pure Python)."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

# Backwards-compatible StrEnum (Python 3.10 lacks enum.StrEnum).
if sys.version_info >= (3, 11):
    from enum import StrEnum  # type: ignore[attr-defined]
else:  # pragma: no cover - exercised only on 3.10

    class StrEnum(str, Enum):
        pass


class Timeframe(StrEnum):
    """Supported candle timeframes."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @classmethod
    def ordered(cls) -> list[Timeframe]:
        return [cls.M1, cls.M5, cls.M15, cls.M30, cls.H1, cls.H4, cls.D1]


@dataclass(frozen=True)
class PriceSnapshot:
    """A point-in-time quote for a symbol.

    All price fields are ``None`` when no live data is available. This type
    deliberately has no defaults that could be mistaken for real prices.
    """

    symbol: str
    connected: bool
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    timestamp_epoch: float | None = None
    source: str | None = None

    @property
    def spread(self) -> float | None:
        if self.bid is None or self.ask is None:
            return None
        return round(self.ask - self.bid, 5)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "connected": self.connected,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "spread": self.spread,
            "timestamp_epoch": self.timestamp_epoch,
            "source": self.source,
        }


@dataclass(frozen=True)
class Candle:
    """A single OHLC(V) candle."""

    timeframe: Timeframe
    open_time_epoch: float
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    def to_dict(self) -> dict:
        return {
            "timeframe": self.timeframe.value,
            "open_time_epoch": self.open_time_epoch,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class MarketDataProvider(ABC):
    """Abstract base class every concrete data provider implements.

    Concrete providers are added in later phases. Keeping the surface small
    and explicit means the strategy/backtesting layers depend only on this
    interface, not on any specific vendor.
    """

    #: Human-readable provider name shown in the Connections UI.
    name: str = "abstract"

    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the provider currently has a live connection."""

    @abstractmethod
    def get_snapshot(self, symbol: str) -> PriceSnapshot:
        """Return the latest quote. Must not fabricate values when offline."""

    @abstractmethod
    def get_candles(self, symbol: str, timeframe: Timeframe, limit: int = 500) -> list[Candle]:
        """Return recent candles (most-recent last). Empty when disconnected."""

    @abstractmethod
    def supported_timeframes(self) -> list[Timeframe]:
        """Return the timeframes this provider can serve."""
