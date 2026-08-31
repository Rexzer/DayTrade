"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/config";
import { apiGet } from "@/lib/api";
import { LineChart } from "@/components/LineChart";

interface StrategyOpt {
  key: string;
  name: string;
  is_builtin: boolean;
}

const inp: React.CSSProperties = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  color: "var(--text)",
  borderRadius: 6,
  padding: "6px 8px",
  width: "100%",
};

const METRIC_LABELS: Record<string, string> = {
  num_trades: "Trades",
  win_rate: "Win rate",
  net_profit: "Net profit",
  profit_factor: "Profit factor",
  expectancy: "Expectancy",
  average_win: "Avg win",
  average_loss: "Avg loss",
  largest_win: "Largest win",
  largest_loss: "Largest loss",
  max_drawdown_pct: "Max drawdown %",
  max_consecutive_losses: "Max losing streak",
  sharpe_ratio: "Sharpe (per-trade)",
  sortino_ratio: "Sortino (per-trade)",
  return_pct: "Return %",
};

const STATUS_BADGE: Record<string, string> = {
  PASS: "green",
  WARNING: "warn",
  FAILED: "red",
};

export default function BacktestingPage() {
  const [strategies, setStrategies] = useState<StrategyOpt[]>([]);
  const [form, setForm] = useState({
    strategy_key: "",
    starting_capital: 10000,
    risk_per_trade_pct: 1,
    primary_timeframe: "1h",
    spread: 0.3,
    slippage: 0.1,
    commission_per_lot: 7,
    value_per_unit: 1,
    min_signal_level: 3,
    allow_long: true,
    allow_short: true,
  });
  const [running, setRunning] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [result, setResult] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ strategies: StrategyOpt[] }>("/backtest/strategies").then((r) => {
      if (r.data?.strategies?.length) {
        setStrategies(r.data.strategies);
        setForm((f) => ({ ...f, strategy_key: r.data!.strategies[0].key }));
      }
    });
  }, []);

  function set<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function post(path: string) {
    const res = await fetch(`${API_BASE_URL}/api${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    return res.json();
  }

  async function run() {
    setRunning(true);
    setError(null);
    setReport(null);
    try {
      const data = await post("/backtest/run");
      if (data.error) {
        setError(data.error + (data.details ? `: ${data.details.join?.(", ")}` : ""));
        setResult(null);
      } else {
        setResult(data);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "network error");
    } finally {
      setRunning(false);
    }
  }

  async function validate() {
    setError(null);
    try {
      const data = await post("/backtest/report");
      if (data.error) setError(data.error);
      else setReport(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "network error");
    }
  }

  const equity = (result?.equity_curve ?? []).map((p: { equity: number }) => p.equity);
  const drawdown = (result?.drawdown_curve ?? []).map(
    (p: { drawdown_pct: number }) => -p.drawdown_pct * 100
  );
  const metrics = result?.metrics ?? {};

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Backtesting &amp; Validation</h2>
      <div className="notice">
        Backtesting measures HISTORICAL robustness only — it can never place an
        order and never guarantees future results. No strategy is guaranteed to
        be profitable.
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="grid grid-4">
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Strategy</div>
            <select value={form.strategy_key} onChange={(e) => set("strategy_key", e.target.value)} style={inp}>
              {strategies.map((s) => (
                <option key={s.key} value={s.key}>{s.name}</option>
              ))}
            </select>
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Timeframe</div>
            <select value={form.primary_timeframe} onChange={(e) => set("primary_timeframe", e.target.value)} style={inp}>
              {["5m", "15m", "30m", "1h", "4h", "1d"].map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Starting capital</div>
            <input type="number" value={form.starting_capital} onChange={(e) => set("starting_capital", +e.target.value)} style={inp} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Risk per trade %</div>
            <input type="number" value={form.risk_per_trade_pct} onChange={(e) => set("risk_per_trade_pct", +e.target.value)} style={inp} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Spread</div>
            <input type="number" value={form.spread} onChange={(e) => set("spread", +e.target.value)} style={inp} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Slippage</div>
            <input type="number" value={form.slippage} onChange={(e) => set("slippage", +e.target.value)} style={inp} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Commission / lot</div>
            <input type="number" value={form.commission_per_lot} onChange={(e) => set("commission_per_lot", +e.target.value)} style={inp} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Value per unit move</div>
            <input type="number" value={form.value_per_unit} onChange={(e) => set("value_per_unit", +e.target.value)} style={inp} />
          </label>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button className="mode-btn active" onClick={run} disabled={running || !form.strategy_key}>
            {running ? "Running…" : "Run backtest"}
          </button>
          <button className="mode-btn" onClick={validate} disabled={!form.strategy_key}>
            Validate (in-sample vs out-of-sample)
          </button>
        </div>
      </div>

      {error && <div className="notice warn">{error}</div>}

      {report && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Validation Report</h3>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8 }}>
            <span className={`badge ${STATUS_BADGE[report.status] ?? "gray"}`}>{report.status}</span>
            <span className="muted">Robustness: {report.robustness}</span>
          </div>
          <div className="grid grid-2">
            <div>
              <div className="section-title" style={{ margin: "4px 0" }}>In-sample</div>
              <div className="row"><span className="label">Profit factor</span><span>{report.in_sample.profit_factor ?? "—"}</span></div>
              <div className="row"><span className="label">Win rate</span><span>{report.in_sample.win_rate}</span></div>
              <div className="row"><span className="label">Max DD %</span><span>{report.in_sample.max_drawdown_pct}</span></div>
              <div className="row"><span className="label">Trades</span><span>{report.in_sample.num_trades}</span></div>
            </div>
            <div>
              <div className="section-title" style={{ margin: "4px 0" }}>Out-of-sample</div>
              <div className="row"><span className="label">Profit factor</span><span>{report.out_of_sample.profit_factor ?? "—"}</span></div>
              <div className="row"><span className="label">Win rate</span><span>{report.out_of_sample.win_rate}</span></div>
              <div className="row"><span className="label">Max DD %</span><span>{report.out_of_sample.max_drawdown_pct}</span></div>
              <div className="row"><span className="label">Trades</span><span>{report.out_of_sample.num_trades}</span></div>
            </div>
          </div>
          {report.warnings?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {report.warnings.map((w: string, i: number) => (
                <div key={i} style={{ color: "var(--warn)", fontSize: 13 }}>⚠ {w}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {result && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Equity curve</h3>
            <LineChart points={equity} label="Equity" />
            <div style={{ marginTop: 12 }}>
              <h3>Drawdown (%)</h3>
              <LineChart points={drawdown} color="#ef5350" fill="rgba(239,83,80,0.12)" label="Drawdown %" />
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Metrics</h3>
            <div className="grid grid-4">
              {Object.entries(METRIC_LABELS).map(([k, label]) => (
                <div key={k} className="row" style={{ borderBottom: "none" }}>
                  <span className="label">{label}</span>
                  <span>{metrics[k] ?? "—"}</span>
                </div>
              ))}
            </div>
            {result.monte_carlo?.iterations > 0 && (
              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                Monte Carlo ({result.monte_carlo.iterations} runs): ending equity
                p5 {result.monte_carlo.ending_equity.p5} / p50{" "}
                {result.monte_carlo.ending_equity.p50} / p95{" "}
                {result.monte_carlo.ending_equity.p95}; max DD p95{" "}
                {(result.monte_carlo.max_drawdown_pct.p95 * 100).toFixed(1)}%.
              </div>
            )}
          </div>

          <div className="card">
            <h3>Trades ({result.trades?.length ?? 0})</h3>
            <div style={{ maxHeight: 320, overflowY: "auto" }}>
              {(result.trades ?? []).slice(0, 200).map((t: Record<string, unknown>, i: number) => (
                <div key={i} className="row" style={{ fontSize: 12 }}>
                  <span>
                    {String(t.direction).toUpperCase()} @ {String(t.entry_price)} → {String(t.exit_price)}
                  </span>
                  <span style={{ color: (t.pnl as number) >= 0 ? "var(--green)" : "var(--red)" }}>
                    {String(t.pnl)} ({String(t.exit_reason)})
                  </span>
                </div>
              ))}
              {(!result.trades || result.trades.length === 0) && (
                <div className="muted">No trades generated in this period.</div>
              )}
            </div>
          </div>
        </>
      )}

      <div className="disclaimer">
        Phase 4 — backtesting &amp; validation. Results are historical
        measurements with modelled costs and no look-ahead. They are not
        predictions and do not guarantee future performance.
      </div>
    </div>
  );
}
