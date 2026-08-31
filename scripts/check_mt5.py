#!/usr/bin/env python3
"""Standalone MetaTrader 5 connection checker.

Run this ON YOUR MT5 HOST (Windows, or Linux via Wine) after installing the
MetaTrader 5 terminal and `pip install MetaTrader5`. It verifies that the
platform will be able to read your account and the XAUUSD contract spec.

It is SELF-CONTAINED (no backend imports) and READ-ONLY — it never places an
order. It never prints your password.

Usage (PowerShell):
    $env:MT5_LOGIN="51234567"; $env:MT5_SERVER="YourBroker-Demo"
    $env:MT5_PASSWORD="..."; $env:MT5_SYMBOL="XAUUSD"
    python scripts/check_mt5.py

Paste the (non-secret) output back if anything fails.
"""

from __future__ import annotations

import os
import sys


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v else default


def main() -> int:
    login = _env("MT5_LOGIN")
    server = _env("MT5_SERVER")
    password = _env("MT5_PASSWORD")  # used, never printed
    symbol = _env("MT5_SYMBOL", "XAUUSD")
    path = _env("MT5_PATH")

    print("=== MetaTrader 5 connection check ===")
    print(f"login   : {login or '(not set)'}")
    print(f"server  : {server or '(not set)'}")
    print(f"password: {'set' if password else '(not set)'}")
    print(f"symbol  : {symbol}")
    print(f"path    : {path or '(default)'}")
    print("-" * 40)

    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print("FAIL: could not import MetaTrader5.")
        print("      Install it on this host:  pip install MetaTrader5")
        print(f"      ({exc})")
        return 2

    kwargs = {}
    if path:
        kwargs["path"] = path
    if login:
        try:
            kwargs["login"] = int(login)
        except ValueError:
            print("FAIL: MT5_LOGIN must be an integer.")
            return 2
        kwargs["password"] = password
        kwargs["server"] = server

    if not (mt5.initialize(**kwargs) if kwargs else mt5.initialize()):
        print(f"FAIL: initialize() failed. last_error={mt5.last_error()}")
        print("      Check the terminal is running and credentials/server are correct.")
        return 3

    try:
        acc = mt5.account_info()
        if acc is None:
            print(f"FAIL: account_info() returned None. last_error={mt5.last_error()}")
            return 3
        trade_mode = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(getattr(acc, "trade_mode", None), "?")
        print("OK: connected.")
        print(f"  broker/company : {getattr(acc, 'company', '?')}")
        print(f"  server         : {getattr(acc, 'server', '?')}")
        print(f"  login          : {getattr(acc, 'login', '?')}")
        print(f"  account type   : {trade_mode}")
        print(f"  currency       : {getattr(acc, 'currency', '?')}")
        print(f"  balance/equity : {getattr(acc, 'balance', '?')} / {getattr(acc, 'equity', '?')}")
        print(f"  leverage       : 1:{getattr(acc, 'leverage', '?')}")
        if trade_mode == "REAL":
            print("  *** WARNING: this is a REAL-money account. Test on a DEMO first. ***")

        if hasattr(mt5, "symbol_select"):
            mt5.symbol_select(symbol, True)
        si = mt5.symbol_info(symbol)
        if si is None:
            print(f"FAIL: symbol_info('{symbol}') is None — wrong symbol name?")
            print("      Try your broker's exact gold symbol (e.g. XAUUSDm, GOLD).")
            return 4
        print(f"  symbol         : {si.name}")
        print(f"    digits       : {si.digits}")
        print(f"    point        : {si.point}")
        print(f"    tick size    : {getattr(si, 'trade_tick_size', '?')}")
        print(f"    tick value   : {getattr(si, 'trade_tick_value', '?')}")
        print(f"    contract size: {getattr(si, 'trade_contract_size', '?')}")
        print(f"    volume min/max/step: {si.volume_min} / {si.volume_max} / {si.volume_step}")

        tick = mt5.symbol_info_tick(symbol)
        if tick is not None:
            spread = (tick.ask - tick.bid) if (tick.ask and tick.bid) else None
            print(f"  tick           : bid {tick.bid} / ask {tick.ask} / spread {spread}")
        print("-" * 40)
        print("SUCCESS: the platform should be able to read this account.")
        print("Next: start the backend with MARKET_DATA_PROVIDER=mt5 and open the app.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
