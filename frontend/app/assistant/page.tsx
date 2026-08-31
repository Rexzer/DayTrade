"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/config";
import { apiGet } from "@/lib/api";

interface Turn {
  q: string;
  a: string;
  intent: string;
  sufficient: boolean;
  sources: string[];
}

export default function AssistantPage() {
  const [examples, setExamples] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    apiGet<{ examples: string[] }>("/assistant/examples").then((r) => {
      if (r.data) setExamples(r.data.examples);
    });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function ask(q: string) {
    const query = q.trim();
    if (!query || busy) return;
    setBusy(true);
    setQuestion("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/assistant/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });
      const data = await res.json();
      setTurns((t) => [
        ...t,
        {
          q: query,
          a: data.text ?? "(no answer)",
          intent: data.intent ?? "",
          sufficient: data.sufficient ?? true,
          sources: data.sources ?? [],
        },
      ]);
    } catch (e) {
      setTurns((t) => [
        ...t,
        { q: query, a: `Error: ${e instanceof Error ? e.message : "network"}`, intent: "", sufficient: false, sources: [] },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2 style={{ marginBottom: 8 }}>AI Trading Assistant</h2>
      <div className="notice">
        The assistant answers ONLY from the platform&apos;s own data. It never
        invents prices, indicators, trades, news or statistics — if data is
        missing it will say &quot;INSUFFICIENT DATA&quot;. A score is a
        transparent rubric, not a probability of profit.
      </div>

      <div className="card" style={{ minHeight: 300, maxHeight: 460, overflowY: "auto", marginBottom: 12 }}>
        {turns.length === 0 && <div className="muted">Ask a question to begin.</div>}
        {turns.map((t, i) => (
          <div key={i} style={{ marginBottom: 14 }}>
            <div style={{ fontWeight: 600 }}>You: {t.q}</div>
            <div
              style={{
                marginTop: 4,
                whiteSpace: "pre-wrap",
                color: t.sufficient ? "var(--text)" : "var(--warn)",
              }}
            >
              {t.a}
            </div>
            {t.sources.length > 0 && (
              <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                sources: {t.sources.join(", ")}
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(question)}
          placeholder="Ask about the current market, setups, trades, risk…"
          style={{
            flex: 1,
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            borderRadius: 8,
            padding: "10px 12px",
          }}
        />
        <button className="mode-btn active" disabled={busy} onClick={() => ask(question)}>
          {busy ? "…" : "Ask"}
        </button>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
        {examples.map((ex) => (
          <button key={ex} className="tf-tab" onClick={() => ask(ex)}>
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
