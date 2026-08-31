"""Persistence for market candles (Phase 2).

Stores/queries candles keyed by (symbol, timeframe, open_time_epoch). Writes
are idempotent: re-saving a candle for an existing bucket updates it rather
than creating a duplicate (the unique constraint also guarantees this at the
database level).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import MarketCandle
from market_data.provider import Candle, Timeframe


def _to_model(symbol: str, candle: Candle, source: str | None) -> MarketCandle:
    return MarketCandle(
        symbol=symbol,
        timeframe=candle.timeframe.value,
        open_time_epoch=int(candle.open_time_epoch),
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        source=source,
    )


def _to_domain(row: MarketCandle) -> Candle:
    return Candle(
        timeframe=Timeframe(row.timeframe),
        open_time_epoch=float(row.open_time_epoch),
        open=float(row.open),
        high=float(row.high),
        low=float(row.low),
        close=float(row.close),
        volume=float(row.volume) if row.volume is not None else None,
    )


class CandleRepository:
    """CRUD for candles with duplicate prevention."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, symbol: str, candle: Candle, source: str | None = None) -> None:
        """Insert or update a single candle (no duplicates)."""
        existing = self.db.execute(
            select(MarketCandle).where(
                MarketCandle.symbol == symbol,
                MarketCandle.timeframe == candle.timeframe.value,
                MarketCandle.open_time_epoch == int(candle.open_time_epoch),
            )
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(_to_model(symbol, candle, source))
        else:
            existing.open = candle.open
            existing.high = candle.high
            existing.low = candle.low
            existing.close = candle.close
            existing.volume = candle.volume
            if source:
                existing.source = source
        self.db.commit()

    def bulk_upsert(self, symbol: str, candles: list[Candle], source: str | None = None) -> int:
        count = 0
        for c in candles:
            self.upsert(symbol, c, source)
            count += 1
        return count

    def get_recent(self, symbol: str, timeframe: Timeframe, limit: int = 500) -> list[Candle]:
        """Return the most recent ``limit`` candles, oldest first."""
        rows = (
            self.db.execute(
                select(MarketCandle)
                .where(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe.value,
                )
                .order_by(MarketCandle.open_time_epoch.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [_to_domain(r) for r in reversed(rows)]

    def get_range(
        self, symbol: str, timeframe: Timeframe, start_epoch: int, end_epoch: int
    ) -> list[Candle]:
        rows = (
            self.db.execute(
                select(MarketCandle)
                .where(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe.value,
                    MarketCandle.open_time_epoch >= start_epoch,
                    MarketCandle.open_time_epoch <= end_epoch,
                )
                .order_by(MarketCandle.open_time_epoch.asc())
            )
            .scalars()
            .all()
        )
        return [_to_domain(r) for r in rows]
