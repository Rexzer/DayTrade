"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

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
        <strong>Trading:</strong> LIVE TRADING DISABLED. Paper and live trading
        are locked in Phase 1 and cannot be enabled from Settings.
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
                  <span className="badge gray">Locked</span>
                </div>
                <div className="row">
                  <span className="label">Live Trading</span>
                  <span className="badge red">Disabled</span>
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
                Channels available: browser, desktop, sound, email, telegram,
                discord. None configured yet.
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
    </div>
  );
}
