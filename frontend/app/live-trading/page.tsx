"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/config";
import { apiGet } from "@/lib/api";

interface Authorization {
  config_enabled: boolean;
  confirmations: Record<string, boolean>;
  confirmation_labels: Record<string, string>;
  all_confirmed: boolean;
  missing_confirmations: string[];
  armed: boolean;
  killed: boolean;
  authorized: boolean;
}

interface AutoTradeStatus {
  enabled: boolean;
  running: boolean;
  interval_seconds: number;
  interval_label: string | null;
  strategy_key: string | null;
  last_scan_epoch: number | null;
  last_result: { executed?: boolean; reason?: string } | null;
}

interface LiveStatus {
  authorization: Authorization;
  risk_settings: Record<string, number>;
  risk_state: Record<string, unknown>;
  broker_connected: boolean;
  symbol: string;
  dry_run: boolean;
  auto_execute: boolean;
  auto_trade: AutoTradeStatus;
  disabled_strategies: string[];
  note: string;
}

interface StrategyHealthEntry {
  strategy_key: string;
  status: string; // healthy | watch | degraded | insufficient_data
  sample_size: number;
  consecutive_losses: number;
  should_disable: boolean;
  reasons: string[];
  metrics: { win_rate?: number; expectancy?: number; profit_factor?: number | null };
}

interface LogEntry {
  epoch: number;
  stage: string;
  ok: boolean;
  message: string;
}

interface IntervalOption {
  label: string;
  seconds: number;
}

interface StrategyRecommendation {
  strategy_key: string;
  name: string;
  suitable_timeframes: string[];
  recommended: string;
  recommended_seconds: number | null;
  faster: string | null;
  rationale: string;
}

export default function LiveTradingPage() {
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Auto Trade config UI state.
  const [intervals, setIntervals] = useState<IntervalOption[]>([]);
  const [recommendations, setRecommendations] = useState<StrategyRecommendation[]>([]);
  const [selStrategy, setSelStrategy] = useState<string>(""); // "" = best across all
  const [selInterval, setSelInterval] = useState<number>(900); // default 15m

  const [health, setHealth] = useState<Record<string, StrategyHealthEntry>>({});

  async function refresh() {
    const [s, l, h] = await Promise.all([
      apiGet<LiveStatus>("/live/status"),
      apiGet<{ log: LogEntry[] }>("/live/log?limit=40"),
      apiGet<{ strategies: Record<string, StrategyHealthEntry> }>("/live/health"),
    ]);
    if (s.data) setStatus(s.data);
    if (l.data) setLog(l.data.log);
    if (h.data?.strategies) setHealth(h.data.strategies);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  // Load selectable intervals + per-strategy recommendations once.
  useEffect(() => {
    apiGet<{ intervals: IntervalOption[]; recommendations: StrategyRecommendation[] }>(
      "/live/auto/intervals"
    ).then((r) => {
      if (r.data) {
        setIntervals(r.data.intervals);
        setRecommendations(r.data.recommendations);
      }
    });
  }, []);

  const selectedRec = recommendations.find((r) => r.strategy_key === selStrategy) ?? null;

  // When the operator picks a strategy, snap the interval to its recommendation.
  function onStrategyChange(key: string) {
    setSelStrategy(key);
    const rec = recommendations.find((r) => r.strategy_key === key);
    if (rec?.recommended_seconds) setSelInterval(rec.recommended_seconds);
  }

  const [opToken, setOpToken] = useState("");

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("operatorToken") : null;
    if (saved) setOpToken(saved);
  }, []);

  function saveToken(v: string) {
    setOpToken(v);
    if (typeof window !== "undefined") localStorage.setItem("operatorToken", v);
  }

  async function post(path: string, body?: unknown) {
    setBusy(true);
    setMsg(null);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (opToken) headers["X-Operator-Token"] = opToken;
      const res = await fetch(`${API_BASE_URL}/api/live${path}`, {
        method: "POST",
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) setMsg(data?.detail?.error ?? `HTTP ${res.status}`);
      else if (data?.error) setMsg(data.error);
      await refresh();
      return data;
    } finally {
      setBusy(false);
    }
  }

  const auth = status?.authorization;

  function toggleConfirm(key: string, value: boolean) {
    if (!auth) return;
    const next = { ...auth.confirmations, [key]: value };
    post("/confirm", { confirmations: next });
  }

  return (
    <div>
      <h2 style={{ marginBottom: 12 }}>Live Trading</h2>

      <div
        className="notice warn"
        style={{ fontWeight: 700, fontSize: 15, borderWidth: 2 }}
      >
        ⚠ WARNING — REAL MONEY TRADING. Orders placed here use real funds.
        Trading can result in losses. The platform never auto-executes; every
        live order is user-initiated and must pass the independent risk engine.
      </div>

      {/* Operator authorization token (required for arm/execute/confirm/risk). */}
      <div className="card" style={{ marginBottom: 12 }}>
        <h3>Operator token</h3>
        <input
          type="password"
          value={opToken}
          onChange={(e) => saveToken(e.target.value)}
          placeholder="X-Operator-Token (matches backend LIVE_API_TOKEN)"
          style={{
            width: "100%",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            borderRadius: 6,
            padding: "8px 10px",
          }}
        />
        <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          Required to arm/execute/configure. Stored only in this browser. Never
          sent anywhere except this backend as a request header.
        </div>
      </div>

      {/* Dry-run toggle — ON by default; validates the chain but never sends. */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h3 style={{ marginBottom: 4 }}>Dry-run mode</h3>
            <div className="muted" style={{ fontSize: 12 }}>
              ON = run the full pipeline incl. the broker&apos;s order-check, but
              place ZERO orders. Use this for your first real-account test.
            </div>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className={`badge ${status?.dry_run ? "gold" : "red"}`}>
              {status?.dry_run ? "DRY-RUN ON" : "LIVE SEND"}
            </span>
            <input
              type="checkbox"
              checked={!!status?.dry_run}
              onChange={(e) => post("/dry-run", { enabled: e.target.checked })}
            />
          </label>
        </div>
      </div>

      {/* Auto Trade — fully automatic execution on a chosen scan interval. */}
      <div className="card" style={{ marginBottom: 12, borderColor: status?.auto_trade?.running ? "var(--red)" : undefined }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h3 style={{ marginBottom: 4 }}>Auto Trade</h3>
            <div className="muted" style={{ fontSize: 12 }}>
              When ON, the bot scans on your chosen interval and executes
              qualifying setups automatically — sizing, stop-loss and
              take-profit handled for you, no clicks. Every trade still passes
              the risk engine; the kill switch stops it and a restart disables
              it. Requires live trading to be armed first.
            </div>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className={`badge ${status?.auto_trade?.running ? "red" : "gold"}`}>
              {status?.auto_trade?.running ? "AUTO ON" : "AUTO OFF"}
            </span>
            <input
              type="checkbox"
              disabled={busy || !auth?.authorized}
              checked={!!status?.auto_trade?.running}
              onChange={(e) =>
                post("/auto", {
                  enabled: e.target.checked,
                  interval_seconds: selInterval,
                  strategy_key: selStrategy || null,
                })
              }
            />
          </label>
        </div>

        <div className="grid grid-2" style={{ marginTop: 12 }}>
          <div>
            <label className="label" style={{ fontSize: 12 }}>Strategy</label>
            <select
              value={selStrategy}
              onChange={(e) => onStrategyChange(e.target.value)}
              disabled={status?.auto_trade?.running}
              style={{
                width: "100%",
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                color: "var(--text)",
                borderRadius: 6,
                padding: "8px 10px",
                marginTop: 4,
              }}
            >
              <option value="">Best confirmed setup (all strategies)</option>
              {recommendations.map((r) => {
                const disabled = status?.disabled_strategies?.includes(r.strategy_key);
                return (
                  <option key={r.strategy_key} value={r.strategy_key}>
                    {r.name}
                    {disabled ? "  ⚠ auto-disabled (decay)" : ""}
                  </option>
                );
              })}
            </select>
          </div>
          <div>
            <label className="label" style={{ fontSize: 12 }}>Scan interval</label>
            <select
              value={selInterval}
              onChange={(e) => setSelInterval(Number(e.target.value))}
              disabled={status?.auto_trade?.running}
              style={{
                width: "100%",
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                color: "var(--text)",
                borderRadius: 6,
                padding: "8px 10px",
                marginTop: 4,
              }}
            >
              {intervals.map((iv) => (
                <option key={iv.seconds} value={iv.seconds}>
                  Every {iv.label}
                  {selectedRec?.recommended_seconds === iv.seconds ? "  ★ recommended" : ""}
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedRec ? (
          <div className="notice" style={{ marginTop: 10, fontSize: 12 }}>
            <b>Recommended for {selectedRec.name}: every {selectedRec.recommended}</b>
            {selectedRec.faster ? ` (or ${selectedRec.faster} for earlier entries)` : ""}. {selectedRec.rationale}
          </div>
        ) : (
          <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>
            &quot;Best confirmed setup&quot; trades whichever strategy currently
            shows a confirmed signal. Pick a specific strategy to see its
            recommended scan interval.
          </div>
        )}

        {status?.auto_trade?.running && (
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            Running every {status.auto_trade.interval_label}
            {status.auto_trade.strategy_key ? ` · strategy: ${status.auto_trade.strategy_key}` : " · best-of-all"}
            {status.dry_run ? " · DRY-RUN (no real orders)" : " · LIVE (placing real orders)"}
            {status.auto_trade.last_result?.reason ? ` · last: ${status.auto_trade.last_result.reason}` : ""}
          </div>
        )}
        {!auth?.authorized && (
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            Arm live trading below (complete the confirmations and ENABLE) before turning Auto Trade on.
          </div>
        )}
      </div>

      {/* Emergency stop — always visible and prominent. */}
      <button
        onClick={() => post("/kill", { cancel_pending: true, close_positions: true })}
        disabled={busy}
        style={{
          width: "100%",
          padding: "18px",
          background: "var(--red)",
          color: "white",
          border: "none",
          borderRadius: 10,
          fontSize: 20,
          fontWeight: 800,
          cursor: "pointer",
          margin: "12px 0",
        }}
      >
        ■ EMERGENCY STOP (kill switch)
      </button>
      {auth?.killed && (
        <div className="notice warn">
          Kill switch is ENGAGED — new trades are blocked.{" "}
          <button className="tf-tab" onClick={() => post("/kill/clear")}>Clear kill switch</button>
        </div>
      )}

      {msg && <div className="notice warn">{msg}</div>}

      {/* Status */}
      <div className="grid grid-4">
        <div className="card"><h3>Config enabled</h3><div className="metric">{auth?.config_enabled ? "Yes" : "No"}</div></div>
        <div className="card"><h3>Broker</h3><div className="metric">{status?.broker_connected ? "Connected" : "Disconnected"}</div></div>
        <div className="card"><h3>Armed</h3><div className="metric" style={{ color: auth?.armed ? "var(--red)" : "var(--text-dim)" }}>{auth?.armed ? "LIVE" : "No"}</div></div>
        <div className="card"><h3>Authorized</h3><div className="metric" style={{ color: auth?.authorized ? "var(--red)" : "var(--text-dim)" }}>{auth?.authorized ? "YES" : "No"}</div></div>
      </div>

      {!auth?.config_enabled && (
        <div className="notice" style={{ marginTop: 12 }}>
          Live execution is disabled at the backend. An operator must set
          LIVE_EXECUTION_ENABLED=true before it can be armed. (A restart always
          disables live trading.)
        </div>
      )}

      {/* Confirmation checklist */}
      <div className="section-title">Required confirmations</div>
      <div className="card">
        {auth &&
          Object.entries(auth.confirmation_labels).map(([key, label]) => (
            <label key={key} className="row" style={{ cursor: "pointer" }}>
              <span>
                <input
                  type="checkbox"
                  checked={auth.confirmations[key] ?? false}
                  onChange={(e) => toggleConfirm(key, e.target.checked)}
                  style={{ marginRight: 8 }}
                />
                {label}
              </span>
            </label>
          ))}
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          {auth?.armed ? (
            <button className="mode-btn" disabled={busy} onClick={() => post("/disable")}>
              Disarm
            </button>
          ) : (
            <button
              className="mode-btn active"
              disabled={busy || !auth?.config_enabled || !auth?.all_confirmed || auth?.killed}
              onClick={() => post("/enable")}
            >
              ENABLE LIVE TRADING
            </button>
          )}
          <button className="mode-btn" disabled={busy || !auth?.authorized} onClick={() => post("/execute")}>
            Execute best signal (manual)
          </button>
        </div>
      </div>

      {/* Risk state */}
      <div className="section-title">Risk Engine</div>
      <div className="card">
        <div className="grid grid-2">
          <div>
            {status &&
              Object.entries(status.risk_settings).map(([k, v]) => (
                <div key={k} className="row" style={{ fontSize: 12 }}>
                  <span className="label">{k}</span>
                  <span>{String(v)}</span>
                </div>
              ))}
          </div>
          <div>
            {status &&
              Object.entries(status.risk_state).map(([k, v]) => (
                <div key={k} className="row" style={{ fontSize: 12 }}>
                  <span className="label">{k}</span>
                  <span style={{ color: v === true ? "var(--red)" : undefined }}>{String(v)}</span>
                </div>
              ))}
            <button className="tf-tab" style={{ marginTop: 8 }} onClick={() => post("/risk/reset")}>
              Reset risk halts (manual)
            </button>
          </div>
        </div>
      </div>

      {/* Strategy health / decay monitor */}
      <div className="section-title">Strategy Health (decay monitor)</div>
      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
          Rolling performance per strategy. A strategy is auto-skipped by live
          trading only when its edge genuinely decays (poor expectancy/profit
          factor or an abnormal losing streak) on a meaningful sample — a low
          win rate alone is just a &quot;watch&quot;. Judged on realized trades
          the platform has recorded.
        </div>
        {Object.keys(health).length === 0 && (
          <div className="muted">No recorded trades yet to evaluate.</div>
        )}
        {Object.entries(health).map(([key, h]) => {
          const color =
            h.status === "degraded"
              ? "red"
              : h.status === "watch"
                ? "gold"
                : h.status === "healthy"
                  ? "green"
                  : "";
          return (
            <div key={key} className="row" style={{ fontSize: 12, alignItems: "flex-start" }}>
              <span className={`badge ${color}`} style={{ minWidth: 96 }}>
                {h.status}
              </span>
              <span style={{ flex: 1, textAlign: "left", paddingLeft: 10 }}>
                <b>{key}</b> · {h.sample_size} trades · win{" "}
                {h.metrics?.win_rate != null ? `${Math.round(h.metrics.win_rate * 100)}%` : "—"} ·
                expectancy {h.metrics?.expectancy ?? "—"} · PF{" "}
                {h.metrics?.profit_factor ?? "—"} · streak {h.consecutive_losses}
                {h.reasons?.length > 0 && (
                  <div className="muted" style={{ marginTop: 2 }}>
                    {h.reasons.join(" ")}
                  </div>
                )}
              </span>
            </div>
          );
        })}
      </div>

      {/* Execution log */}
      <div className="section-title">Execution Log</div>
      <div className="card" style={{ maxHeight: 320, overflowY: "auto" }}>
        {log.length === 0 && <div className="muted">No execution activity yet.</div>}
        {log.map((e, i) => (
          <div key={i} className="row" style={{ fontSize: 12 }}>
            <span className={`badge ${e.ok ? "green" : "red"}`}>{e.stage}</span>
            <span style={{ flex: 1, textAlign: "left", paddingLeft: 10 }}>{e.message}</span>
          </div>
        ))}
      </div>

      <div className="disclaimer">
        Live execution flows Strategy → Signal → Risk Engine → Execution →
        MetaTrader 5. The independent risk engine can reject any trade and the
        strategy engine cannot bypass it. Trades can be placed manually
        (one click each) or automatically via Auto Trade — both run this exact
        risk-gated pipeline. Live trading requires explicit authorization, the
        kill switch stops everything instantly, and a restart disables both
        live trading and Auto Trade. Trading real money carries risk of loss;
        past performance does not guarantee future results.
      </div>
    </div>
  );
}
