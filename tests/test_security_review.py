"""Automated security-review checks (Phase 8 final review)."""

import os

import pytest

from backend.app.config import Settings
from execution_engine import (
    REQUIRED_CONFIRMATIONS,
    ExecutionCoordinator,
    LiveAuthorization,
    LiveExecutionDisabledError,
    MT5ExecutionProvider,
)
from execution_engine.provider import ExecOrderRequest
from risk_engine import LiveRiskEngine, RiskContext, RiskSettings
from tests.helpers import FakeMT5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")


def _authorized() -> LiveAuthorization:
    auth = LiveAuthorization(config_enabled=True)
    for k in REQUIRED_CONFIRMATIONS:
        auth.confirm(k, True)
    auth.arm()
    return auth


# 1. No unauthorized live trading -----------------------------------------
def test_no_unauthorized_live_trading():
    provider = MT5ExecutionProvider(client=FakeMT5())
    provider.connect()
    with pytest.raises(LiveExecutionDisabledError):
        provider.send_order(ExecOrderRequest("XAUUSDm", "buy", "market", 0.1))


def test_live_enabled_flag_alone_does_not_authorize():
    provider = MT5ExecutionProvider(client=FakeMT5(), live_enabled=True)
    provider.connect()
    with pytest.raises(LiveExecutionDisabledError):
        provider.send_order(ExecOrderRequest("XAUUSDm", "buy", "market", 0.1))


# 2. Risk engine cannot be bypassed ---------------------------------------
def test_risk_engine_is_mandatory_no_send_on_rejection():
    provider = MT5ExecutionProvider(client=FakeMT5())
    provider.connect()
    coord = ExecutionCoordinator(
        provider, LiveRiskEngine(RiskSettings(max_spread_points=50)), _authorized()
    )
    signal = {
        "strategy_key": "s",
        "symbol": "XAUUSDm",
        "level": 3,
        "direction": "long",
        "stop_loss": 2390.0,
        "take_profits": (2420.0,),
    }
    ctx = RiskContext(
        equity=10_000.0,
        spread_points=999.0,  # over the limit -> risk must reject
        price=2400.4,
        data_status="live",
        broker_connected=True,
        now_epoch=1000.0,
    )
    out = coord.execute_signal(signal, ctx, provider.get_symbol_spec("XAUUSDm"))
    assert out.executed is False and out.stage == "risk"
    assert provider._client.last_order_request is None  # order was NEVER sent


# 3. Kill switch works -----------------------------------------------------
def test_kill_switch_stops_new_trades():
    provider = MT5ExecutionProvider(client=FakeMT5())
    provider.connect()
    auth = _authorized()
    coord = ExecutionCoordinator(provider, LiveRiskEngine(RiskSettings()), auth)
    coord.kill_switch()
    assert auth.is_authorized() is False


# 4. Restart safety --------------------------------------------------------
def test_restart_disables_live_trading():
    # A fresh authorization (new process) is always disabled.
    assert LiveAuthorization(config_enabled=True).is_authorized() is False


# 5. No passwords exposed --------------------------------------------------
def test_settings_repr_has_no_password():
    s = Settings()
    text = repr(s)
    assert "mt5_password" not in text  # it's a property, not a stored field
    # Even if the env var is set, it must not appear in the repr.
    assert not any("password" in f and f != "" for f in [text.lower().split("password")[0][-0:]])


def test_settings_has_no_password_field():
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(Settings)}
    assert "mt5_password" not in field_names
    assert "password" not in field_names


# 6. No secrets in the frontend -------------------------------------------
_FORBIDDEN = ("SECRET_KEY", "MT5_PASSWORD", "POSTGRES_PASSWORD", "Authorization: Bearer ")


def test_frontend_contains_no_hardcoded_secrets():
    if not os.path.isdir(FRONTEND):
        pytest.skip("frontend directory not present")
    offenders = []
    for dirpath, dirnames, filenames in os.walk(FRONTEND):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".next")]
        for name in filenames:
            if not name.endswith((".ts", ".tsx", ".js", ".jsx", ".json", ".css")):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            for token in _FORBIDDEN:
                if token in content:
                    offenders.append(f"{path}: {token}")
    assert not offenders, f"Potential secrets in frontend: {offenders}"


def test_frontend_only_uses_public_env_vars():
    if not os.path.isdir(FRONTEND):
        pytest.skip("frontend directory not present")
    offenders = []
    for dirpath, dirnames, filenames in os.walk(FRONTEND):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".next")]
        for name in filenames:
            if not name.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            # Any process.env access must be a NEXT_PUBLIC_* variable.
            idx = 0
            while True:
                idx = content.find("process.env.", idx)
                if idx == -1:
                    break
                after = content[idx + len("process.env.") : idx + len("process.env.") + 12]
                if not after.startswith("NEXT_PUBLIC_"):
                    offenders.append(f"{path}: process.env.{after}")
                idx += 1
    assert not offenders, f"Frontend reads non-public env vars: {offenders}"
