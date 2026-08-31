"""Tests: the data-grounded AI assistant (never invents data)."""

from assistant import AssistantContext, TradingAssistant

A = TradingAssistant()


def test_insufficient_data_when_no_regime():
    ans = A.ask("why is xauusd bullish?", AssistantContext())
    assert ans.sufficient is False
    assert "INSUFFICIENT DATA" in ans.text


def test_regime_answer_is_grounded():
    ctx = AssistantContext(
        regime={
            "regime": "strong_bullish",
            "trend": "bullish",
            "strength": 30.0,
            "volatility": "normal",
            "details": {},
        }
    )
    ans = A.ask("why is xauusd bullish?", ctx)
    assert ans.sufficient and "STRONG BULLISH" in ans.text
    assert "regime" in ans.sources


def test_active_setups_reports_halt():
    ctx = AssistantContext(signals=[], signals_allowed=False, signals_reason="data is STALE.")
    ans = A.ask("what strategies have setups?", ctx)
    assert ans.sufficient and "STALE" in ans.text


def test_strongest_setup_describes_signal():
    ctx = AssistantContext(
        signals=[
            {
                "strategy_key": "tf",
                "strategy_name": "Trend",
                "level": 3,
                "direction": "long",
                "timeframe": "1h",
                "confirmations": ["a"],
                "missing_confirmations": [],
                "confidence_score": 80,
            }
        ],
        signals_allowed=True,
    )
    ans = A.ask("which setup has the strongest confluence?", ctx)
    assert "Trend" in ans.text and "not a probability" in ans.text


def test_market_price_never_fabricated():
    ans = A.ask("what is the price?", AssistantContext(market={"connected": False}))
    assert "fabricated" in ans.text.lower() or "no live market data" in ans.text.lower()


def test_news_not_connected_is_honest():
    ans = A.ask("is there any news?", AssistantContext(news={"connected": False}))
    assert "never fabricates" in ans.text.lower()


def test_help_fallback():
    ans = A.ask("asdfghjkl", AssistantContext())
    assert ans.intent == "help"
    assert "only answer from" in ans.text.lower()


def test_rejection_uses_execution_log():
    ctx = AssistantContext(
        execution_log=[{"ok": False, "stage": "risk", "message": "spread too high"}]
    )
    ans = A.ask("why didn't you take a trade?", ctx)
    assert "risk" in ans.text and "spread" in ans.text
