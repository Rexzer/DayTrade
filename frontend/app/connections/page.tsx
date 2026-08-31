"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/config";
import { MarketStatus, apiGet } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
function SystemHealthCard() {
  const [health, setHealth] = useState<any>(null);
  useEffect(() => {
    const load = () => apiGet<any>("/system/health").then((r) => setHealth(r.data));
    load();
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>System Health</h3>
        <span>{health?.overall_emoji} {(health?.overall ?? "unknown").toUpperCase()}</span>
      </div>
      {(health?.components ?? []).map((c: any) => (
        <div key={c.name} className="row" style={{ fontSize: 13 }}>
          <span>{c.emoji} {c.name}</span>
          <span className="muted">{c.detail}</span>
        </div>
      ))}
    </div>
  );
}

interface Mt5Status {
  provider: string;
  connected: boolean;
  connect_attempts: number;
  last_error: string | null;
  symbol: string;
  live_execution_enabled: boolean;
  note: string;
}

interface Mt5Verify {
  connected: boolean;
  broker?: string;
  server?: string;
  login?: number;
  account_type?: string;
  currency?: string;
  leverage?: number;
  symbol?: string | null;
  contract_specifications?: Record<string, unknown> | null;
  live_execution_enabled?: boolean;
  note?: string;
  symbol_error?: string;
}

function Dot({ ok }: { ok: boolean }) {
  return <span className={`badge ${ok ? "green" : "gray"}`}><span className="status-dot" />{ok ? "Connected" : "Disconnected"}</span>;
}

export default function ConnectionsPage() {
  const [mt5, setMt5] = useState<Mt5Status | null>(null);
  const [verify, setVerify] = useState<Mt5Verify | null>(null);
  const [market, setMarket] = useState<MarketStatus | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [s, v, m] = await Promise.all([
      apiGet<Mt5Status>("/mt5/status"),
      apiGet<Mt5Verify>("/mt5/verify"),
      apiGet<MarketStatus>("/market/status"),
    ]);
    setMt5(s.data);
    setVerify(v.data);
    setMarket(m.data);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 6000);
    return () => clearInterval(id);
  }, []);

  async function post(path: string) {
    setBusy(true);
    try {
      await fetch(`${API_BASE_URL}/api/mt5${path}`, { method: "POST" });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  const specs = verify?.contract_specifications ?? null;

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Data Connections</h2>

      <SystemHealthCard />

      <div className="notice warn">
        MetaTrader 5 integration is READ-ONLY. Order execution is disabled —
        no orders can be placed from this platform (a later phase adds live
        execution behind explicit confirmations).
      </div>

      {/* Market data */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <h3>Market Data</h3>
          <Dot ok={market?.connected ?? false} />
        </div>
        <div className="row"><span className="label">Source</span><span>{market?.source ?? "none"}</span></div>
        <div className="row"><span className="label">Broker symbol</span><span>{market?.broker_symbol ?? "—"}</span></div>
        <div className="row"><span className="label">Status</span><span>{(market?.health?.status ?? "disconnected").toUpperCase()}</span></div>
        <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          Set MARKET_DATA_PROVIDER=mt5 to use MetaTrader 5 as the data source.
        </div>
      </div>

      {/* MetaTrader 5 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>MetaTrader 5</h3>
          <Dot ok={mt5?.connected ?? false} />
        </div>
        <div style={{ display: "flex", gap: 8, margin: "8px 0" }}>
          <button className="mode-btn active" disabled={busy} onClick={() => post("/connect")}>Connect</button>
          <button className="mode-btn" disabled={busy} onClick={() => post("/disconnect")}>Disconnect</button>
        </div>
        {mt5?.last_error && !mt5.connected && (
          <div className="muted" style={{ fontSize: 12 }}>
            Last error: {mt5.last_error}. (Requires the MT5 terminal + MetaTrader5
            package on the backend host, plus MT5_LOGIN/SERVER/PASSWORD.)
          </div>
        )}
        <div className="row">
          <span className="label">Live execution</span>
          <span className="badge red">DISABLED</span>
        </div>
      </div>

      {/* Account verification */}
      {verify?.connected && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Account Verification</h3>
          <div className="grid grid-2">
            <div>
              <div className="row"><span className="label">Broker</span><span>{verify.broker ?? "—"}</span></div>
              <div className="row"><span className="label">Server</span><span>{verify.server ?? "—"}</span></div>
              <div className="row"><span className="label">Login</span><span>{verify.login ?? "—"}</span></div>
              <div className="row"><span className="label">Account type</span>
                <span className={`badge ${verify.account_type === "real" ? "red" : "gold"}`}>
                  {(verify.account_type ?? "—").toUpperCase()}
                </span>
              </div>
              <div className="row"><span className="label">Currency</span><span>{verify.currency ?? "—"}</span></div>
              <div className="row"><span className="label">Leverage</span><span>{verify.leverage ?? "—"}</span></div>
            </div>
            <div>
              <div className="section-title" style={{ margin: "4px 0" }}>XAUUSD contract</div>
              {specs ? (
                Object.entries(specs).map(([k, v]) => (
                  <div key={k} className="row" style={{ fontSize: 12 }}>
                    <span className="label">{k}</span>
                    <span>{String(v)}</span>
                  </div>
                ))
              ) : (
                <div className="muted">{verify.symbol_error ?? "No symbol spec."}</div>
              )}
            </div>
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>{verify.note}</div>
        </div>
      )}

      <div className="disclaimer">
        Phase 6 — MetaTrader 5 integration is read-only: account, symbol
        specifications, ticks, historical data, positions, orders and trade
        history. No order can be placed. Broker contract specs are read from the
        actual account and never assumed.
      </div>
    </div>
  );
}
