"use client";

import { useState } from "react";
import { API_BASE_URL } from "@/lib/config";

// A basic visual/rule-based Strategy Builder. Composes an AND/OR group of
// conditions over indicators/price/constants and posts a rule definition to
// the backend, which validates it and registers a custom (analysis-only)
// strategy. Nested groups and more operand types are supported by the backend
// rule engine; this UI focuses on the common single-group case.

type OperandKind = "ema" | "sma" | "rsi" | "atr" | "price" | "constant";
type Operator = "gt" | "lt" | "gte" | "lte" | "cross_above" | "cross_below";

interface Row {
  leftKind: OperandKind;
  leftParam: number;
  operator: Operator;
  rightKind: OperandKind;
  rightParam: number;
}

const OPERAND_KINDS: OperandKind[] = ["ema", "sma", "rsi", "atr", "price", "constant"];
const OPERATORS: { value: Operator; label: string }[] = [
  { value: "gt", label: ">" },
  { value: "lt", label: "<" },
  { value: "gte", label: "≥" },
  { value: "lte", label: "≤" },
  { value: "cross_above", label: "crosses above" },
  { value: "cross_below", label: "crosses below" },
];

function operand(kind: OperandKind, param: number) {
  if (kind === "constant") return { kind: "constant", value: param };
  if (kind === "price") return { kind: "price", field: "close" };
  return { kind, params: { period: param } };
}

export default function StrategyBuilderPage() {
  const [key, setKey] = useState("my_strategy");
  const [name, setName] = useState("My Strategy");
  const [description, setDescription] = useState("");
  const [timeframe, setTimeframe] = useState("15m");
  const [logic, setLogic] = useState<"and" | "or">("and");
  const [rows, setRows] = useState<Row[]>([
    { leftKind: "ema", leftParam: 20, operator: "gt", rightKind: "ema", rightParam: 50 },
  ]);
  const [result, setResult] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  function updateRow(i: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((rs) => [
      ...rs,
      { leftKind: "rsi", leftParam: 14, operator: "gt", rightKind: "constant", rightParam: 50 },
    ]);
  }
  function removeRow(i: number) {
    setRows((rs) => rs.filter((_, idx) => idx !== i));
  }

  function buildDefinition() {
    return {
      key,
      name,
      description,
      timeframe,
      long_rules: {
        type: "group",
        logic,
        children: rows.map((r) => ({
          type: "condition",
          left: operand(r.leftKind, r.leftParam),
          operator: r.operator,
          right: operand(r.rightKind, r.rightParam),
        })),
      },
    };
  }

  async function save() {
    setResult(null);
    setErrors([]);
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategies/custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildDefinition()),
      });
      const body = await res.json();
      if (!res.ok) {
        setErrors(body?.detail?.errors ?? [body?.detail ?? `HTTP ${res.status}`]);
        return;
      }
      setResult(`Saved custom strategy "${body.created}". It now appears in the Strategy Library.`);
    } catch (e) {
      setErrors([e instanceof Error ? e.message : "network error"]);
    }
  }

  const needsParam = (k: OperandKind) => k !== "price";
  const paramLabel = (k: OperandKind) => (k === "constant" ? "value" : "period");

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Strategy Builder</h2>
      <div className="notice">
        Build a rule-based strategy from conditions. Saved strategies are
        analysis-only and appear in the Strategy Library — they can never place
        an order.
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="grid grid-2">
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Key (unique)</div>
            <input value={key} onChange={(e) => setKey(e.target.value)} style={inp} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Name</div>
            <input value={name} onChange={(e) => setName(e.target.value)} style={inp} />
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Timeframe</div>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} style={inp}>
              {["1m", "5m", "15m", "30m", "1h", "4h", "1d"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            <div className="muted" style={{ fontSize: 12 }}>Combine with</div>
            <select value={logic} onChange={(e) => setLogic(e.target.value as "and" | "or")} style={inp}>
              <option value="and">AND (all)</option>
              <option value="or">OR (any)</option>
            </select>
          </label>
        </div>
        <label>
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>Description</div>
          <input value={description} onChange={(e) => setDescription(e.target.value)} style={inp} />
        </label>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>LONG conditions</h3>
        {rows.map((r, i) => (
          <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
            <select value={r.leftKind} onChange={(e) => updateRow(i, { leftKind: e.target.value as OperandKind })} style={inp}>
              {OPERAND_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            {needsParam(r.leftKind) && (
              <input type="number" value={r.leftParam} title={paramLabel(r.leftKind)}
                onChange={(e) => updateRow(i, { leftParam: Number(e.target.value) })} style={{ ...inp, width: 90 }} />
            )}
            <select value={r.operator} onChange={(e) => updateRow(i, { operator: e.target.value as Operator })} style={inp}>
              {OPERATORS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <select value={r.rightKind} onChange={(e) => updateRow(i, { rightKind: e.target.value as OperandKind })} style={inp}>
              {OPERAND_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            {needsParam(r.rightKind) && (
              <input type="number" value={r.rightParam} title={paramLabel(r.rightKind)}
                onChange={(e) => updateRow(i, { rightParam: Number(e.target.value) })} style={{ ...inp, width: 90 }} />
            )}
            <button className="mode-btn" onClick={() => removeRow(i)}>✕</button>
          </div>
        ))}
        <button className="tf-tab" onClick={addRow}>+ Add condition</button>
      </div>

      <button className="mode-btn active" onClick={save}>Save strategy</button>

      {result && <div className="notice" style={{ marginTop: 12 }}>{result}</div>}
      {errors.length > 0 && (
        <div className="notice warn" style={{ marginTop: 12 }}>
          {errors.map((e, i) => <div key={i}>• {e}</div>)}
        </div>
      )}
    </div>
  );
}

const inp: React.CSSProperties = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  color: "var(--text)",
  borderRadius: 6,
  padding: "6px 8px",
  width: "100%",
};
