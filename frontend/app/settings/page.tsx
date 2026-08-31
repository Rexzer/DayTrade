"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { API_BASE_URL } from "@/lib/config";

interface SettingsResponse {
  sections: string[];
  general: Record<string, unknown>;
  trading: {
    mode: string;
    paper_trading_enabled: boolean;
    live_trading_enabled: boolean;
    message: string;
  };
  market_data: { provider: string; connected: boolean };
  notifications: { channels: string[]; configured: string[] };
  security: { secret_key_set: boolean; jwt_algorithm: string };
}

const SECTION_LABELS: Record<string, string> = {
  general: "General",
  market_data: "Market Data",
  strategies: "Strategies",
  risk_management: "Risk Management",
  notifications: "Notifications",
  trading: "Trading",
  security: "Security",
};

export default function SettingsPage() {
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    apiGet<SettingsResponse>("/settings").then((r) => {
      setData(r.data);
      setOnline(r.ok);
    });
  }, []);

  const sections = data?.sections ?? Object.keys(SECTION_LABELS);

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Settings</h2>

      {!online && (
        <div className="notice warn">Backend not reachable — showing defaults.</div>
      )}

      <div className="notice warn">
        <strong>Trading:</strong> Analysis and Paper trading are available. Live
        execution is user-initiated only, requires explicit authorization on the
        Live Trading page, and is disabled on restart.
      </div>

      <div className="grid grid-2">
        {sections.map((key) => (
          <div className="card" key={key}>
            <h3>{SECTION_LABELS[key] ?? key}</h3>
            {key === "trading" && (
              <>
                <div className="row">
                  <span className="label">Mode</span>
                  <span>{data?.trading.mode ?? "analysis_only"}</span>
                </div>
                <div className="row">
                  <span className="label">Paper Trading</span>
                  <span className="badge green">Available</span>
                </div>
                <div className="row">
                  <span className="label">Live Trading</span>
                  <span className="badge gold">Requires authorization</span>
                </div>
              </>
            )}
            {key === "market_data" && (
              <div className="row">
                <span className="label">Provider</span>
                <span className="badge gray">
                  {data?.market_data.provider ?? "none"}
                </span>
              </div>
            )}
            {key === "security" && (
              <>
                <div className="row">
                  <span className="label">Secret key configured</span>
                  <span>{data?.security.secret_key_set ? "Yes" : "No"}</span>
                </div>
                <div className="row">
                  <span className="label">JWT algorithm</span>
                  <span>{data?.security.jwt_algorithm ?? "HS256"}</span>
                </div>
              </>
            )}
            {key === "notifications" && (
              <div className="muted" style={{ fontSize: 13 }}>
                Manage channels and event types in the Notifications panel below.
              </div>
            )}
            {["general", "strategies", "risk_management"].includes(key) && (
              <div className="muted" style={{ fontSize: 13 }}>
                Configuration UI for this section is expanded in later phases.
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="section-title">Notifications</div>
      <NotificationsPrefs />
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function NotificationsPrefs() {
  const [cfg, setCfg] = useState<any>(null);

  async function load() {
    const r = await apiGet<any>("/notifications");
    setCfg(r.data);
  }
  useEffect(() => {
    load();
  }, []);

  async function toggle(kind: "channels" | "events", key: string, value: boolean) {
    const body = { [kind]: { [key]: value } };
    await fetch(`${API_BASE_URL}/api/notifications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    load();
  }

  if (!cfg) return <div className="card"><div className="muted">Loading…</div></div>;

  return (
    <div className="grid grid-2">
      <div className="card">
        <h3>Channels</h3>
        {cfg.available_channels.map((c: string) => (
          <label key={c} className="row" style={{ cursor: "pointer" }}>
            <span>{c}</span>
            <input
              type="checkbox"
              checked={!!cfg.channels[c]}
              onChange={(e) => toggle("channels", c, e.target.checked)}
            />
          </label>
        ))}
      </div>
      <div className="card">
        <h3>Events</h3>
        {cfg.available_events.map((e: string) => (
          <label key={e} className="row" style={{ cursor: "pointer" }}>
            <span>{e.replace(/_/g, " ")}</span>
            <input
              type="checkbox"
              checked={!!cfg.events[e]}
              onChange={(ev) => toggle("events", e, ev.target.checked)}
            />
          </label>
        ))}
      </div>
    </div>
  );
}
