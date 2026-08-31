"""Tick data model (pure Python).

A tick is a single market update. XAUUSD feeds typically provide bid/ask;
``last`` and ``volume`` are optional. Timestamps are Unix epoch seconds in
UTC. Nothing here fabricates a value — missing fields stay ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tick:
    """A single market data tick.

    Attributes:
        symbol: The (canonical) instrument symbol, e.g. "XAUUSD".
        timestamp_epoch: Unix time in seconds (UTC).
        bid: Best bid price, if provided.
        ask: Best ask price, if provided.
        last: Last traded price, if provided.
        volume: Tick/trade volume for this update, if provided.
        source: Name of the provider that produced the tick.
    """

    symbol: str
    timestamp_epoch: float
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: float | None = None
    source: str | None = None

    @property
    def spread(self) -> float | None:
        if self.bid is None or self.ask is None:
            return None
        return round(self.ask - self.bid, 5)

    @property
    def price(self) -> float | None:
        """Best single price to use for candle construction.

        Prefers the last traded price; otherwise the bid/ask midpoint;
        otherwise whichever single side is available. Returns ``None`` if the
        tick carries no usable price (such ticks are ignored by aggregators).
        """
        if self.last is not None:
            return self.last
        if self.bid is not None and self.ask is not None:
            return round((self.bid + self.ask) / 2.0, 5)
        if self.bid is not None:
            return self.bid
        if self.ask is not None:
            return self.ask
        return None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp_epoch": self.timestamp_epoch,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "spread": self.spread,
            "price": self.price,
            "source": self.source,
        }
