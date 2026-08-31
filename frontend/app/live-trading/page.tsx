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

interface LiveStatus {
  authorization: Authorization;
  risk_settings: Record<string, number>;
  risk_state: Record<string, unknown>;
  broker_connected: boolean;
  symbol: string;
  auto_execute: boolean;
  note: string;
}

interface LogEntry {
  epoch: number;
  stage: string;
  ok: boolean;
  message: string;
}

export default function LiveTradingPage() {
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const [s, l] = await Promise.all([
      apiGet<LiveStatus>("/live/status"),
      apiGet<{ log: LogEntry[] }>("/live/log?limit=40"),
    ]);
    if (s.data) setStatus(s.data);
    if (l.data) setLog(l.data.log);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

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
        Phase 7 — live execution flows Strategy → Signal → Risk Engine →
        Execution → MetaTrader 5. The independent risk engine can reject any
        trade and the strategy engine cannot bypass it. Live trading requires
        explicit authorization, is never automatic, and is disabled on restart.
        Past performance does not guarantee future results.
      </div>
    </div>
  );
}
