# Security Review

Final review for the XAUUSD platform. Items marked ✅ are enforced in code and
covered by automated tests (`tests/test_security_review.py` and others).

## Findings

| Check | Status | Evidence |
|-------|--------|----------|
| No secrets in the frontend | ✅ | `test_frontend_contains_no_hardcoded_secrets`; frontend only reads `NEXT_PUBLIC_*` env vars (`test_frontend_only_uses_public_env_vars`). |
| No passwords in logs / API | ✅ | `MT5_PASSWORD` is read via a property, never stored on `Settings` or returned; `test_settings_has_no_password_field`, `test_settings_repr_has_no_password`. Structured logs never include credentials. |
| No API keys exposed | ✅ | Secrets come from environment variables only; `.env` is git-ignored; `.env.example` contains placeholders. |
| No unauthorized live trading | ✅ | Provider write ops raise `LiveExecutionDisabledError` unless a `LiveAuthorization.is_authorized()`; `test_no_unauthorized_live_trading`, `test_live_enabled_flag_alone_does_not_authorize`. |
| Risk engine cannot be bypassed | ✅ | The execution coordinator requires an approving `RiskDecision`; on rejection no order is sent (`test_risk_engine_is_mandatory_no_send_on_rejection`). |
| Kill switch works | ✅ | `kill_switch()` disarms authorization and blocks new trades; `test_kill_switch_stops_new_trades`, `test_kill_switch_blocks_subsequent_execution`. |
| Restart safety | ✅ | Authorization is in-memory and defaults disabled; `test_restart_disables_live_trading`. |
| No autonomous live trading | ✅ | `ENABLE_LIVE_TRADING` must be false (the app refuses to start otherwise); live orders are user-initiated via `/api/live/execute`. |
| Never assume order success | ✅ | Only an explicit broker DONE retcode counts; `test_broker_order_rejection_is_not_success`. |
| Duplicate-order prevention | ✅ | Coordinator dedup window; `test_duplicate_within_window_is_blocked`. |
| No fabricated market data | ✅ | Null provider returns `None` prices; simulated data is labelled `source="simulated"`. |
| AI assistant grounding | ✅ | Answers only from provided context; returns "INSUFFICIENT DATA" otherwise; never invents (`tests/test_assistant.py`). |

## Operational recommendations
- Set a strong `SECRET_KEY` and a real `POSTGRES_PASSWORD` in production; the
  app validates that `SECRET_KEY` is set in production.
- Store the MT5 password in a secret manager; keep `LIVE_EXECUTION_ENABLED`
  false unless you intend to trade live, and always validate on a demo account.
- Put the API behind authentication/roles and TLS before any deployment.
- Restrict `CORS_ORIGINS` to your real frontend origin.

## Residual risks
- Live execution ultimately depends on the broker/MT5 terminal; verify account,
  symbol and contract specs (`/api/mt5/verify`) before arming.
- The bundled auth is a baseline (PBKDF2 + HS256 JWT); consider argon2/bcrypt
  and a vetted JWT library plus rate-limiting for production.
