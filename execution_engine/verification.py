"""Account verification payload (pure-ish; calls provider reads).

Assembles the broker/account/symbol facts a user must confirm BEFORE any
future live execution (Phase 7). This is display + confirmation only; it never
enables trading.
"""

from __future__ import annotations

from execution_engine.provider import (
    BrokerConnectionError,
    ExecutionProvider,
    InvalidSymbolError,
)


def build_account_verification(provider: ExecutionProvider, symbol: str) -> dict:
    """Return the verification block (or an error note) for the UI."""
    if not provider.is_connected():
        return {"connected": False, "note": "Not connected to MetaTrader 5."}
    try:
        acc = provider.get_account_info()
    except BrokerConnectionError as exc:
        return {"connected": False, "note": str(exc)}

    result: dict = {
        "connected": True,
        "broker": acc.company,
        "server": acc.server,
        "login": acc.login,
        "account_type": acc.trade_mode,  # demo | contest | real
        "currency": acc.currency,
        "leverage": acc.leverage,
        "symbol": None,
        "contract_specifications": None,
        "live_execution_enabled": False,  # Phase 6: always false
        "note": (
            "Live execution is DISABLED (Phase 7 feature). This is a read-only "
            "verification of the connected account."
        ),
    }
    try:
        spec = provider.get_symbol_spec(symbol)
        result["symbol"] = spec.name
        result["contract_specifications"] = spec.to_dict()
    except (InvalidSymbolError, BrokerConnectionError) as exc:
        result["symbol_error"] = str(exc)
    return result
