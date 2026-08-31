"""The data-grounded trading assistant (pure Python)."""

from __future__ import annotations

from dataclasses import dataclass

from assistant.context import AssistantContext

SCORE_DISCLAIMER = "The score is a transparent rubric, not a probability of profit."
_LEVELS = {0: "NO SETUP", 1: "WATCH", 2: "POTENTIAL SETUP", 3: "CONFIRMED SETUP", 4: "EXECUTED"}


@dataclass
class AssistantAnswer:
    text: str
    intent: str
    sufficient: bool
    sources: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "intent": self.intent,
            "sufficient": self.sufficient,
            "sources": list(self.sources),
        }


def _insufficient(intent: str, missing: str) -> AssistantAnswer:
    return AssistantAnswer(
        text=f"INSUFFICIENT DATA. {missing}",
        intent=intent,
        sufficient=False,
    )


def _has(seq) -> bool:
    return bool(seq)


class TradingAssistant:
    """Answers questions about the current system, grounded strictly in data."""

    EXAMPLES = (
        "Why is XAUUSD bullish?",
        "What strategies currently have setups?",
        "Which setup has the strongest confluence?",
        "Why didn't you take a trade?",
        "Why was this trade stopped out?",
        "Show today's trades.",
        "Which strategy performed best?",
        "What changed in the market?",
        "Explain this setup to me.",
        "What is the risk status?",
        "Is there any news?",
        "What is the system health?",
    )

    def ask(self, question: str, ctx: AssistantContext) -> AssistantAnswer:
        q = (question or "").strip().lower()
        if not q:
            return self._help("help")
        intent = self._detect_intent(q)
        handler = getattr(self, f"_{intent}", None)
        if handler is None:
            return self._help("help")
        return handler(ctx)

    # ------------------------------------------------------------- intents
    def _detect_intent(self, q: str) -> str:
        def any_in(*words: str) -> bool:
            return any(w in q for w in words)

        if any_in("stopped out", "stop out", "stopped") and any_in("trade", "why", "position"):
            return "explain_stop"
        if any_in("reject", "didn't take", "didnt take", "not take", "why not", "no trade") or (
            "take" in q and any_in("didn", "did not", "not", "why")
        ):
            return "explain_rejection"
        if any_in("strongest", "best confluence", "highest confidence", "best setup"):
            return "strongest_setup"
        if any_in("explain") and any_in("setup", "signal", "trade", "this"):
            return "explain_setup"
        if any_in("today", "todays", "today's") and any_in("trade", "trades"):
            return "todays_trades"
        if any_in("best", "performed", "top") and any_in("strateg", "month", "perform"):
            return "best_strategy"
        if any_in("changed", "change", "what happened", "recent"):
            return "what_changed"
        if any_in("strateg") and any_in("setup", "active", "have", "which"):
            return "active_setups"
        if any_in("bullish", "bearish", "trend", "regime", "ranging", "volatil"):
            return "explain_regime"
        if any_in("risk", "limit", "drawdown", "daily loss", "halt"):
            return "risk_status"
        if any_in("news", "event", "economic", "fomc", "cpi", "nfp"):
            return "news_status"
        if any_in("health", "connected", "disconnect", "status", "system"):
            return "system_health"
        if any_in("price", "bid", "ask", "spread", "quote"):
            return "market_price"
        return "help"

    # ------------------------------------------------------------- builders
    def _explain_regime(self, ctx: AssistantContext) -> AssistantAnswer:
        if not ctx.regime:
            return _insufficient("explain_regime", "No market-regime analysis is available yet.")
        r = ctx.regime
        details = r.get("details") or {}
        parts = [
            f"Market regime is {str(r.get('regime', 'unknown')).replace('_', ' ').upper()} "
            f"(trend: {r.get('trend', 'unknown')}, volatility: {r.get('volatility', 'unknown')})."
        ]
        if r.get("strength") is not None:
            parts.append(f"Trend strength (ADX) is {r['strength']:.1f}.")
        e20, e50 = details.get("ema20"), details.get("ema50")
        if e20 is not None and e50 is not None:
            rel = "above" if e20 > e50 else "below"
            parts.append(f"EMA20 ({e20:.2f}) is {rel} EMA50 ({e50:.2f}).")
        if details.get("structure_trend"):
            parts.append(f"Market structure reads {details['structure_trend']}.")
        if ctx.mtf:
            trends = ", ".join(f"{row['timeframe']}={row.get('trend', '?')}" for row in ctx.mtf)
            parts.append(f"Across timeframes: {trends}.")
        return AssistantAnswer(" ".join(parts), "explain_regime", True, ("regime", "mtf"))

    def _active_setups(self, ctx: AssistantContext) -> AssistantAnswer:
        if ctx.signals is None:
            return _insufficient("active_setups", "The strategy engine has produced no data yet.")
        if not ctx.signals_allowed:
            reason = ctx.signals_reason or "signal generation is currently halted."
            return AssistantAnswer(
                f"No active setups: {reason}", "active_setups", True, ("signals",)
            )
        active = [s for s in ctx.signals if s.get("level", 0) >= 1]
        if not active:
            return AssistantAnswer(
                "No strategies currently have a setup — all are at NO SETUP.",
                "active_setups",
                True,
                ("signals",),
            )
        lines = [
            f"- {s.get('strategy_name', s.get('strategy_key'))}: "
            f"{_LEVELS.get(s.get('level', 0), '?')} "
            f"{(s.get('direction') or '').upper()}"
            + (
                f" (score {s['confidence_score']}/100)"
                if s.get("confidence_score") is not None
                else ""
            )
            for s in active
        ]
        return AssistantAnswer(
            "Strategies with a setup right now:\n" + "\n".join(lines) + f"\n{SCORE_DISCLAIMER}",
            "active_setups",
            True,
            ("signals",),
        )

    def _strongest_setup(self, ctx: AssistantContext) -> AssistantAnswer:
        if not ctx.signals:
            return _insufficient("strongest_setup", "No signals are available.")
        ranked = sorted(
            ctx.signals,
            key=lambda s: (s.get("level", 0), s.get("confidence_score") or 0),
            reverse=True,
        )
        top = ranked[0]
        if top.get("level", 0) < 1:
            return AssistantAnswer(
                "No setup currently stands out — every strategy is at NO SETUP.",
                "strongest_setup",
                True,
                ("signals",),
            )
        return AssistantAnswer(self._describe_signal(top), "strongest_setup", True, ("signals",))

    def _explain_setup(self, ctx: AssistantContext) -> AssistantAnswer:
        return self._strongest_setup(ctx)

    def _describe_signal(self, s: dict) -> str:
        name = s.get("strategy_name", s.get("strategy_key"))
        parts = [
            f"{name} — {_LEVELS.get(s.get('level', 0), '?')} "
            f"{(s.get('direction') or '').upper()} on {s.get('timeframe', '?')}."
        ]
        if s.get("entry_zone"):
            parts.append(f"Entry zone {s['entry_zone']}.")
        if s.get("stop_loss") is not None:
            parts.append(f"Stop {s['stop_loss']}.")
        if s.get("take_profits"):
            parts.append(f"Targets {s['take_profits']}.")
        if s.get("risk_reward") is not None:
            parts.append(f"Risk/reward 1:{s['risk_reward']}.")
        if s.get("confirmations"):
            parts.append("Satisfied: " + "; ".join(s["confirmations"]) + ".")
        if s.get("missing_confirmations"):
            parts.append("Waiting on: " + "; ".join(s["missing_confirmations"]) + ".")
        if s.get("invalidation"):
            parts.append(f"Invalidation: {s['invalidation']}.")
        if s.get("confidence_score") is not None:
            parts.append(f"Score {s['confidence_score']}/100. {SCORE_DISCLAIMER}")
        return " ".join(parts)

    def _explain_rejection(self, ctx: AssistantContext) -> AssistantAnswer:
        # Prefer concrete execution-log rejections.
        if ctx.execution_log:
            rejects = [e for e in ctx.execution_log if not e.get("ok")]
            if rejects:
                last = rejects[0]
                return AssistantAnswer(
                    f"The most recent rejection was at the '{last.get('stage')}' stage: "
                    f"{last.get('message')}.",
                    "explain_rejection",
                    True,
                    ("execution_log",),
                )
        # Otherwise explain what confirmations are still missing on the best signal.
        if ctx.signals:
            ranked = sorted(ctx.signals, key=lambda s: s.get("level", 0), reverse=True)
            top = ranked[0]
            if top.get("missing_confirmations"):
                return AssistantAnswer(
                    f"No trade was taken because {top.get('strategy_name', 'the strategy')} is "
                    f"still waiting on: " + "; ".join(top["missing_confirmations"]) + ". "
                    "A trade is only taken once all required conditions and the risk checks pass.",
                    "explain_rejection",
                    True,
                    ("signals",),
                )
        if ctx.risk_state and (
            ctx.risk_state.get("daily_loss_halt") or ctx.risk_state.get("drawdown_halt")
        ):
            return AssistantAnswer(
                "New trades are blocked by a risk halt (daily-loss or drawdown limit reached). "
                "A manual reset is required.",
                "explain_rejection",
                True,
                ("risk_state",),
            )
        return _insufficient(
            "explain_rejection",
            "No rejection record, pending signal, or active halt is available to explain.",
        )

    def _explain_stop(self, ctx: AssistantContext) -> AssistantAnswer:
        if not ctx.trades:
            return _insufficient("explain_stop", "There are no recorded trades to review.")
        stopped = [t for t in ctx.trades if t.get("exit_reason") == "stop_loss"]
        if not stopped:
            return AssistantAnswer(
                "No trade in the record was stopped out — the most recent exits "
                "were not stop-losses.",
                "explain_stop",
                True,
                ("trades",),
            )
        t = stopped[0]
        return AssistantAnswer(
            f"The {t.get('direction', '').upper()} {t.get('strategy_name', '')} trade was stopped "
            f"out: entry {t.get('entry_price')}, stop hit at {t.get('exit_price')}, "
            f"P&L {t.get('pnl')}. The stop is the pre-defined invalidation level; it executed "
            "because price reached it, capping the loss to the planned risk.",
            "explain_stop",
            True,
            ("trades",),
        )

    def _todays_trades(self, ctx: AssistantContext) -> AssistantAnswer:
        if ctx.trades is None:
            return _insufficient("todays_trades", "No trade record is available.")
        if not ctx.trades:
            return AssistantAnswer(
                "No trades have been recorded.", "todays_trades", True, ("trades",)
            )
        wins = sum(1 for t in ctx.trades if t.get("pnl", 0) > 0)
        net = round(sum(t.get("pnl", 0) for t in ctx.trades), 2)
        lines = [
            f"- {t.get('direction', '').upper()} {t.get('strategy_name', '')}: "
            f"{t.get('exit_reason')} P&L {t.get('pnl')}"
            for t in ctx.trades[:10]
        ]
        return AssistantAnswer(
            f"{len(ctx.trades)} recorded trades, {wins} winners, net {net}.\n" + "\n".join(lines),
            "todays_trades",
            True,
            ("trades",),
        )

    def _best_strategy(self, ctx: AssistantContext) -> AssistantAnswer:
        by = (ctx.performance or {}).get("by_strategy")
        if not by:
            return _insufficient("best_strategy", "No per-strategy performance is available yet.")
        best = max(by, key=lambda r: r.get("net_pnl", 0))
        return AssistantAnswer(
            f"By net P&L, {best.get('strategy_name')} leads: {best.get('num_trades')} trades, "
            f"win rate {round((best.get('win_rate') or 0) * 100)}%, "
            f"profit factor {best.get('profit_factor')}, net {best.get('net_pnl')}. "
            "This is historical/simulated performance and does not guarantee future results.",
            "best_strategy",
            True,
            ("performance",),
        )

    def _what_changed(self, ctx: AssistantContext) -> AssistantAnswer:
        if ctx.alerts:
            lines = [f"- {a.get('kind')}: {a.get('message')}" for a in ctx.alerts[:6]]
            return AssistantAnswer(
                "Recent changes (from the alert stream):\n" + "\n".join(lines),
                "what_changed",
                True,
                ("alerts",),
            )
        if ctx.regime:
            return self._explain_regime(ctx)
        return _insufficient("what_changed", "No alert history or regime data is available.")

    def _risk_status(self, ctx: AssistantContext) -> AssistantAnswer:
        if not ctx.risk_state:
            return _insufficient("risk_status", "No risk-engine state is available.")
        st = ctx.risk_state
        halts = [k for k in ("daily_loss_halt", "weekly_loss_halt", "drawdown_halt") if st.get(k)]
        halt_txt = (
            ("HALTS ACTIVE: " + ", ".join(halts) + " (manual reset required).")
            if halts
            else "No halts active."
        )
        return AssistantAnswer(
            f"Risk state: {st.get('trades_today', 0)} trades today, "
            f"{st.get('consecutive_losses', 0)} consecutive losses, "
            f"drawdown {round((st.get('current_drawdown_pct') or 0) * 100, 2)}%. {halt_txt}",
            "risk_status",
            True,
            ("risk_state",),
        )

    def _news_status(self, ctx: AssistantContext) -> AssistantAnswer:
        if not ctx.news:
            return _insufficient("news_status", "No news source is connected.")
        if not ctx.news.get("connected"):
            return AssistantAnswer(
                "No economic-calendar source is connected, so upcoming events are unavailable. "
                "The platform never fabricates news events.",
                "news_status",
                True,
                ("news",),
            )
        return AssistantAnswer(
            f"Next high-impact event: {ctx.news.get('next_high_impact_event') or 'none reported'}.",
            "news_status",
            True,
            ("news",),
        )

    def _system_health(self, ctx: AssistantContext) -> AssistantAnswer:
        if not ctx.health:
            return _insufficient("system_health", "No system-health snapshot is available.")
        comps = ctx.health.get("components") or []
        lines = [
            f"- {c.get('name')}: {c.get('status')}"
            + (f" ({c.get('detail')})" if c.get("detail") else "")
            for c in comps
        ]
        return AssistantAnswer(
            f"Overall: {ctx.health.get('overall', 'unknown')}.\n" + "\n".join(lines),
            "system_health",
            True,
            ("health",),
        )

    def _market_price(self, ctx: AssistantContext) -> AssistantAnswer:
        m = ctx.market
        if not m or not m.get("connected"):
            return AssistantAnswer(
                "No live market data is connected, so I cannot report a current price. "
                "The platform never shows fabricated prices.",
                "market_price",
                True,
                ("market",),
            )
        return AssistantAnswer(
            f"XAUUSD: bid {m.get('bid')}, ask {m.get('ask')}, spread {m.get('spread')} "
            f"(source: {m.get('source')}, status: {m.get('data_status')}).",
            "market_price",
            True,
            ("market",),
        )

    def _help(self, _ctx) -> AssistantAnswer:
        return AssistantAnswer(
            "I can only answer from the platform's own data (I never invent prices, trades or "
            "news). Try:\n" + "\n".join(f"- {q}" for q in self.EXAMPLES),
            "help",
            True,
            (),
        )
