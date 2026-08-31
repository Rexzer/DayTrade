"""BacktestService — runs backtests/validation for a strategy (Phase 4).

Sources historical candles from the active market-data provider (works with
the labelled simulated provider offline, or a real provider when connected),
runs the leakage-free backtester, and returns metrics, equity/drawdown curves,
the trade list, a Monte Carlo summary, and a PASS/WARNING/FAILED report.

Backtesting NEVER places an order and NEVER guarantees future performance.
"""

from __future__ import annotations

from backend.app.core.logging_config import get_logger
from backend.app.market_data import get_market_service
from backend.app.strategy import get_strategy_service
from backtesting import (
    BacktestConfig,
    Backtester,
    build_report,
    compute_windows,
    drawdown_curve,
    monte_carlo,
)
from market_data.provider import Timeframe

logger = get_logger("backtest")

_ALL_TIMEFRAMES = [tf.value for tf in Timeframe.ordered()]


class BacktestService:
    def __init__(self) -> None:
        self._history_limit = 1000

    # ------------------------------------------------------------- helpers
    def _strategy(self, key: str):
        svc = get_strategy_service()
        for strat in svc._all_strategies():  # includes builtins + custom
            if strat.key == key:
                return strat
        return None

    def available_strategies(self) -> dict:
        svc = get_strategy_service()
        return {
            "strategies": [
                {"key": s.key, "name": s.metadata.name, "is_builtin": s.metadata.is_builtin}
                for s in svc._all_strategies()
            ]
        }

    def _load_candles(self) -> dict[str, list]:
        """Fetch historical candles per timeframe from the active provider."""
        provider = get_market_service().provider
        broker_symbol = get_market_service().mapper.spec.broker_symbol
        if not provider.is_connected():
            try:
                provider.connect()
            except Exception:  # noqa: BLE001
                pass
        candles: dict[str, list] = {}
        for tf in _ALL_TIMEFRAMES:
            try:
                candles[tf] = provider.get_historical_candles(
                    broker_symbol, Timeframe(tf), limit=self._history_limit
                )
            except Exception:  # noqa: BLE001
                candles[tf] = []
        return candles

    def _build_config(self, overrides: dict | None) -> BacktestConfig:
        cfg = BacktestConfig()
        for field_name, value in (overrides or {}).items():
            if hasattr(cfg, field_name) and value is not None:
                setattr(cfg, field_name, value)
        return cfg

    # ------------------------------------------------------------- actions
    def run(self, strategy_key: str, config_overrides: dict | None = None) -> dict:
        strat = self._strategy(strategy_key)
        if strat is None:
            return {"error": f"Unknown strategy '{strategy_key}'."}
        cfg = self._build_config(config_overrides)
        errors = cfg.validate()
        if errors:
            return {"error": "Invalid config", "details": errors}

        candles = self._load_candles()
        primary = candles.get(cfg.primary_timeframe, [])
        if len(primary) <= cfg.warmup_bars + 5:
            return {
                "error": (
                    "Not enough historical candles for the selected timeframe. "
                    "Connect a data provider (or use MARKET_DATA_PROVIDER=simulated)."
                ),
                "bars_available": len(primary),
            }

        result = Backtester(strat, cfg).run(candles)
        payload = result.to_dict()
        payload["drawdown_curve"] = drawdown_curve(result.equity_curve)
        payload["monte_carlo"] = monte_carlo(result.trades, cfg.starting_capital, iterations=500)
        payload["disclaimer"] = (
            "Historical backtest only. No strategy is guaranteed profitable; "
            "past performance does not guarantee future results."
        )
        return payload

    def report(self, strategy_key: str, config_overrides: dict | None = None) -> dict:
        strat = self._strategy(strategy_key)
        if strat is None:
            return {"error": f"Unknown strategy '{strategy_key}'."}
        cfg = self._build_config(config_overrides)
        candles = self._load_candles()
        primary = candles.get(cfg.primary_timeframe, [])
        if len(primary) < 40:
            return {"error": "Not enough historical candles to build a validation report."}
        try:
            compute_windows(candles, cfg.primary_timeframe)
        except ValueError as exc:
            return {"error": str(exc)}
        return build_report(strat, candles, cfg)


_service: BacktestService | None = None


def get_backtest_service() -> BacktestService:
    global _service
    if _service is None:
        _service = BacktestService()
    return _service
