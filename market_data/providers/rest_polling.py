"""Generic REST-polling market-data provider.

Fetches XAUUSD quotes from any HTTP JSON endpoint by describing where the
bid/ask fields live in the response. This makes it usable with many data
vendors without writing vendor-specific code.

Network access and credentials are required at runtime and are supplied via
configuration/environment — nothing is hard-coded. ``httpx`` is imported
lazily so the rest of the platform (and the offline test suite) does not
depend on it.

NOTE: This is real, working code, but it cannot be exercised in an offline /
no-network environment. Point ``RestProviderConfig.url`` at a real quote API
(with any required API key) to receive live prices.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from market_data.provider import (
    Candle,
    MarketDataProvider,
    PriceSnapshot,
    SymbolSpec,
    Timeframe,
)
from market_data.tick import Tick


@dataclass
class RestProviderConfig:
    """Describes how to fetch and parse a quote from an HTTP JSON endpoint."""

    url: str
    #: Query params merged into the request (e.g. {"symbol": "XAU/USD"}).
    params: dict[str, str] = field(default_factory=dict)
    #: Headers, e.g. {"Authorization": "Bearer <token>"} (from env, not code).
    headers: dict[str, str] = field(default_factory=dict)
    #: Dotted paths into the JSON body for each field, e.g. "data.bid".
    bid_path: str | None = None
    ask_path: str | None = None
    last_path: str | None = None
    volume_path: str | None = None
    broker_symbol: str = "XAUUSD"
    timeout_seconds: float = 5.0


def _dig(obj: object, dotted: str | None):
    """Safely walk a dotted path into nested dict/list JSON. Returns None on miss."""
    if not dotted:
        return None
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


class GenericRestProvider(MarketDataProvider):
    """Polls a configurable HTTP endpoint for the latest XAUUSD quote."""

    name = "rest"

    def __init__(self, config: RestProviderConfig) -> None:
        self._config = config
        self._connected = False
        self._last_tick: Tick | None = None
        self._client = None  # created lazily in connect()

    # ------------------------------------------------------------- lifecycle
    def connect(self) -> bool:
        try:
            import httpx  # local import: optional dependency
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "GenericRestProvider requires 'httpx'. Install backend/requirements.txt."
            ) from exc
        self._client = httpx.Client(timeout=self._config.timeout_seconds)
        self._connected = True
        return True

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def supported_timeframes(self) -> list[Timeframe]:
        return Timeframe.ordered()

    def symbol_spec(self, symbol: str) -> SymbolSpec:
        return SymbolSpec(canonical="XAUUSD", broker_symbol=self._config.broker_symbol)

    # --------------------------------------------------------------- fetching
    def _fetch_json(self) -> dict:
        if self._client is None:
            raise RuntimeError("Provider not connected; call connect() first.")
        resp = self._client.get(
            self._config.url,
            params=self._config.params,
            headers=self._config.headers,
        )
        resp.raise_for_status()
        return resp.json()

    def poll(self) -> Tick | None:
        """Fetch one quote and return it as a :class:`Tick` (or None on parse miss)."""
        body = self._fetch_json()
        cfg = self._config

        def _num(path: str | None) -> float | None:
            val = _dig(body, path)
            try:
                return float(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        bid = _num(cfg.bid_path)
        ask = _num(cfg.ask_path)
        last = _num(cfg.last_path)
        volume = _num(cfg.volume_path)
        if bid is None and ask is None and last is None:
            # Nothing usable parsed — do not fabricate a price.
            return None
        tick = Tick(
            symbol="XAUUSD",
            timestamp_epoch=time.time(),
            bid=bid,
            ask=ask,
            last=last,
            volume=volume,
            source=self.name,
        )
        self._last_tick = tick
        return tick

    def get_tick(self, symbol: str) -> Tick | None:
        return self._last_tick

    def get_snapshot(self, symbol: str) -> PriceSnapshot:
        t = self._last_tick
        if not self._connected or t is None:
            return PriceSnapshot(symbol=symbol, connected=self._connected, source=self.name)
        return PriceSnapshot(
            symbol=symbol,
            connected=True,
            bid=t.bid,
            ask=t.ask,
            last=t.last,
            timestamp_epoch=t.timestamp_epoch,
            source=self.name,
        )

    def get_candles(self, symbol: str, timeframe: Timeframe, limit: int = 500) -> list[Candle]:
        # A pure quote endpoint has no history; candles are built locally by
        # the aggregator from polled ticks, or fetched from storage. A vendor
        # provider with an OHLC endpoint would override this.
        return []
