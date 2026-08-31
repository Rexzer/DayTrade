# Go-Live Checklist (DEMO first)

Follow this in order. **Do not skip the demo stage.** Trading real money can
lose money; no strategy here is guaranteed and a score is not a probability.

## 0. Prerequisites (on the MT5 host — Windows, or Linux/Wine)
- [ ] MetaTrader 5 terminal installed and logged into your broker's **demo**.
- [ ] `pip install -r backend/requirements.txt` and `pip install MetaTrader5`.
- [ ] PostgreSQL and Redis running (or use `docker compose`).
- [ ] `.env` created from `.env.example` with a strong `SECRET_KEY`.

## 1. Verify the broker connection
- [ ] Set `MT5_LOGIN`, `MT5_SERVER`, `MT5_PASSWORD`, `MT5_SYMBOL` in the env.
- [ ] Run `python scripts/check_mt5.py` → expect **SUCCESS** and `account type: DEMO`.
- [ ] Confirm the XAUUSD contract spec (digits, tick value, min/step lot) looks right.

## 2. Start the platform
- [ ] `MARKET_DATA_PROVIDER=mt5` in `.env`; `LIVE_EXECUTION_ENABLED=false` for now.
- [ ] Start backend + frontend (or `docker compose up --build`), open http://localhost:3000.
- [ ] **Data Connections** page: MT5 🟢, System Health mostly 🟢, Account Verification shows DEMO.

## 3. Validate strategies (no money at risk)
- [ ] **Backtesting**: run each strategy; then **Validate** (in-sample vs out-of-sample).
- [ ] Review PASS / WARNING / FAILED. Treat FAILED/insufficient-evidence as "not ready".
- [ ] Check parameter sensitivity isn't FRAGILE and Monte Carlo drawdown is tolerable.

## 4. Paper trade on live data
- [ ] **Paper Trading**: Start; let it run through real sessions.
- [ ] Review **Trade Journal**, **Performance Analytics** and journal observations.
- [ ] Only proceed if *your* results justify it.

## 5. Configure risk (hard limits)
- [ ] Set per-trade risk (start 0.25–0.5%), daily/weekly loss, max drawdown,
      max positions, max spread, news blackout.
- [ ] Set an operator secret: `LIVE_API_TOKEN=<random>` in the backend env.

## 6. Enable live — on DEMO
- [ ] Set `LIVE_EXECUTION_ENABLED=true` and restart the backend.
- [ ] **Live Trading** page: enter the **Operator token**.
- [ ] Tick all six confirmations → **ENABLE LIVE TRADING** (arm).
- [ ] Use **Execute best signal (manual)** and watch the **Execution Log** show:
      signal → risk → order_check → order_request → order_response → position.
- [ ] Verify the order/position appears in your MT5 terminal.
- [ ] Test the **EMERGENCY STOP** — confirm new trades are blocked immediately.

## 7. Safety reminders (always true)
- Live execution is **user-initiated only** — the platform never auto-trades.
- A backend **restart disables live trading** (you must re-arm).
- The **independent risk engine can reject any trade**; it cannot be bypassed.
- Daily-loss / drawdown halts **latch** and require a manual reset.
- Keep `ENABLE_LIVE_TRADING=false` (there is intentionally no autonomous loop).

## 8. Only after sustained demo success
- [ ] Consider a small **real** account with conservative limits, having read
      `docs/SECURITY.md` and put the API behind auth + TLS.
- [ ] Persisted signals/orders/trades are in PostgreSQL (`/api/live/history`).

> Past performance does not guarantee future results.
