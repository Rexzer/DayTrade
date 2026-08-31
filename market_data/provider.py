"""Provider-agnostic market-data interface (pure Python)."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from market_data.tick import Tick

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


@dataclass(frozen=True)
class SymbolSpec:
    """Broker-specific instrument specification.

    Different brokers name the same instrument differently (XAUUSD, XAUUSDm,
    GOLD, XAUUSD.a, ...). ``canonical`` is the platform's internal name;
    ``broker_symbol`` is what the provider actually expects. Contract details
    (digits, tick size, point value) are used later for spread/sizing and are
    never assumed to be identical across brokers.
    """

    canonical: str = "XAUUSD"
    broker_symbol: str = "XAUUSD"
    digits: int = 2
    point: float = 0.01
    description: str = "Gold vs US Dollar"

    def to_dict(self) -> dict:
        return {
            "canonical": self.canonical,
            "broker_symbol": self.broker_symbol,
            "digits": self.digits,
            "point": self.point,
            "description": self.description,
        }


# Callback signatures for streaming subscriptions.
TickCallback = Callable[["Tick"], None]
CandleCallback = Callable[[Candle], None]


class MarketDataProvider(ABC):
    """Abstract base class every concrete data provider implements.

    The interface is intentionally provider-independent so brokers/vendors can
    be swapped without touching the strategy, storage or UI layers. The four
    ``@abstractmethod`` members below form the minimal contract; the streaming
    lifecycle methods (``connect``/``subscribe_ticks``/...) have safe defaults
    so simple providers (like the null provider) remain valid without
    implementing them.
    """

    #: Human-readable provider name shown in the Connections UI.
    name: str = "abstract"

    # --- Minimal required contract -------------------------------------------
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

    # --- Streaming lifecycle (optional; safe defaults) -----------------------
    def connect(self) -> bool:
        """Establish a connection. Default: no-op returning current state."""
        return self.is_connected()

    def disconnect(self) -> None:  # noqa: B027 - intentional optional no-op hook
        """Tear down the connection. Default: no-op."""

    def get_current_price(self, symbol: str) -> PriceSnapshot:
        """Alias for :meth:`get_snapshot` (kept for interface symmetry)."""
        return self.get_snapshot(symbol)

    def get_tick(self, symbol: str) -> Tick | None:
        """Return the most recent tick, or ``None`` if none/disconnected."""
        return None

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        end_epoch: float | None = None,
    ) -> list[Candle]:
        """Return historical candles up to ``end_epoch`` (for backfill/load)."""
        return self.get_candles(symbol, timeframe, limit=limit)

    def subscribe_ticks(self, symbol: str) -> Iterator[Tick]:
        """Yield ticks as they arrive. Default: empty stream (no data)."""
        return iter(())

    def subscribe_candles(self, symbol: str, timeframe: Timeframe) -> Iterator[Candle]:
        """Yield closed candles as they form. Default: empty stream."""
        return iter(())

    def symbol_spec(self, symbol: str) -> SymbolSpec:
        """Return the contract spec for ``symbol`` (default XAUUSD 2-digit)."""
        return SymbolSpec(canonical=symbol, broker_symbol=symbol)
