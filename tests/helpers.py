"""Deterministic candle factories for strategy/indicator tests (not collected)."""

from __future__ import annotations

from market_data.provider import Candle, Timeframe


def make_candles(
    closes: list[float],
    *,
    timeframe: Timeframe = Timeframe.M15,
    spread: float = 0.5,
    volume: float = 100.0,
    start_epoch: int = 0,
) -> list[Candle]:
    """Build candles from a close series.

    Each candle's open = previous close (contiguous). High/low straddle the
    open/close by ``spread``. Deterministic and dependency-free.
    """
    dur = {
        Timeframe.M1: 60,
        Timeframe.M5: 300,
        Timeframe.M15: 900,
        Timeframe.M30: 1800,
        Timeframe.H1: 3600,
        Timeframe.H4: 14400,
        Timeframe.D1: 86400,
    }[timeframe]
    out: list[Candle] = []
    prev = closes[0]
    for i, close in enumerate(closes):
        o = prev
        hi = max(o, close) + spread
        lo = min(o, close) - spread
        out.append(
            Candle(
                timeframe=timeframe,
                open_time_epoch=float(start_epoch + i * dur),
                open=o,
                high=hi,
                low=lo,
                close=close,
                volume=volume,
            )
        )
        prev = close
    return out


def uptrend(n: int = 120, start: float = 2000.0, step: float = 2.0, **kw) -> list[Candle]:
    return make_candles([start + i * step for i in range(n)], **kw)


def downtrend(n: int = 120, start: float = 2400.0, step: float = 2.0, **kw) -> list[Candle]:
    return make_candles([start - i * step for i in range(n)], **kw)


def flat(n: int = 120, level: float = 2000.0, wobble: float = 3.0, seed: int = 42, **kw):
    """A realistic mean-reverting range (deterministic).

    Uses a seeded random walk with a pull back toward ``level`` so the series
    stays banded and non-trending (unlike a pathological 2-bar oscillation,
    which would confuse ADX).
    """
    import random

    rng = random.Random(seed)
    closes = []
    price = level
    for _ in range(n):
        price += rng.uniform(-wobble, wobble) + (level - price) * 0.25
        closes.append(round(price, 3))
    return make_candles(closes, **kw)


# --- Phase 4 backtesting helpers -------------------------------------------

from strategy_engine.strategy import (  # noqa: E402
    MarketContext,
    Signal,
    SignalLevel,
    Strategy,
    StrategyMetadata,
)


def candle(t: float, o: float, h: float, low: float, c: float, tf=Timeframe.H1, vol=100.0):
    """Build one Candle with explicit OHLC (for precise backtest scenarios)."""
    return Candle(tf, float(t), o, h, low, c, vol)


class FixedSignalStrategy(Strategy):
    """Emits a fixed directional signal every bar once enough history exists.

    Deterministic and dependency-free — used to exercise backtester mechanics
    (entry/exit/sizing) without indicator noise.
    """

    def __init__(
        self,
        direction: str = "long",
        stop_offset: float = 10.0,
        tp_offset: float = 15.0,
        level: SignalLevel = SignalLevel.CONFIRMED_SETUP,
        timeframe: str = "1h",
        min_bars: int = 2,
    ) -> None:
        self._direction = direction
        self._stop_offset = stop_offset
        self._tp_offset = tp_offset
        self._level = level
        self._timeframe = timeframe
        self._min_bars = min_bars
        self.metadata = StrategyMetadata(key="fixed", name="Fixed", description="test")

    def evaluate(self, ctx: MarketContext) -> Signal:
        cs = ctx.candles.get(self._timeframe, [])
        if len(cs) < self._min_bars:
            return Signal("fixed", SignalLevel.NO_SETUP, timeframe=self._timeframe)
        last = cs[-1].close
        if self._direction == "long":
            stop = last - self._stop_offset
            tp = last + self._tp_offset
        else:
            stop = last + self._stop_offset
            tp = last - self._tp_offset
        return Signal(
            "fixed",
            self._level,
            timeframe=self._timeframe,
            direction=self._direction,
            entry_zone=(last, last),
            stop_loss=stop,
            take_profits=(tp,),
            invalidation="test",
        )


# --- Phase 6 MetaTrader 5 mock ---------------------------------------------

from types import SimpleNamespace as _NS  # noqa: E402


class FakeMT5:
    """Minimal MetaTrader5-API-compatible mock for connector tests."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388
    TIMEFRAME_D1 = 16408

    def __init__(
        self,
        *,
        init_ok: bool = True,
        symbol: str = "XAUUSDm",
        order_check_retcode: int = 0,
    ) -> None:
        self.init_ok = init_ok
        self.symbol = symbol
        self.order_check_retcode = order_check_retcode
        self._positions: tuple = (
            _NS(
                ticket=1,
                symbol=symbol,
                type=0,  # buy
                volume=0.10,
                price_open=2400.0,
                sl=2390.0,
                tp=2420.0,
                price_current=2405.0,
                profit=50.0,
                time=1_700_000_000,
            ),
        )

    def initialize(self, **kwargs):
        return self.init_ok

    def login(self, *args, **kwargs):
        return True

    def shutdown(self):
        return True

    def last_error(self):
        return (-10003, "IPC initialize failed")

    def account_info(self):
        return _NS(
            login=51234567,
            name="Demo User",
            server="ACME-Demo",
            company="ACME Markets",
            currency="USD",
            balance=10_000.0,
            equity=10_050.0,
            margin=200.0,
            margin_free=9_850.0,
            margin_level=5025.0,
            leverage=100,
            trade_mode=0,  # demo
        )

    def symbol_select(self, symbol, enable):
        return True

    def symbol_info(self, symbol):
        if symbol != self.symbol:
            return None
        return _NS(
            name=self.symbol,
            digits=2,
            point=0.01,
            trade_tick_size=0.01,
            trade_tick_value=1.0,
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_max=50.0,
            volume_step=0.01,
            visible=True,
            description="Gold vs US Dollar",
        )

    def symbol_info_tick(self, symbol):
        if symbol != self.symbol:
            return None
        return _NS(bid=2400.10, ask=2400.40, last=2400.25, volume=3, time=1_700_000_000)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return [
            _NS(
                time=1_700_000_000 + i * 3600,
                open=2400.0 + i,
                high=2402.0 + i,
                low=2399.0 + i,
                close=2401.0 + i,
                tick_volume=100 + i,
            )
            for i in range(count)
        ]

    def positions_get(self):
        return self._positions

    def set_positions(self, positions: tuple) -> None:
        self._positions = positions

    def orders_get(self):
        return (
            _NS(
                ticket=99,
                symbol=self.symbol,
                type=2,  # buy limit
                volume_current=0.20,
                volume_initial=0.20,
                price_open=2380.0,
                sl=2370.0,
                tp=2400.0,
                state="placed",
                time_setup=1_700_000_000,
            ),
        )

    def history_deals_get(self, from_epoch, to_epoch):
        return (
            _NS(
                ticket=5, symbol=self.symbol, volume=0.1, price=2401.0, profit=10.0, time=from_epoch
            ),
        )

    def order_check(self, request):
        return _NS(retcode=self.order_check_retcode, comment="checked")
