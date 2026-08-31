import { MarketSnapshot } from "@/lib/api";

function Card({ title, value }: { title: string; value: string | null }) {
  const isNa = value === null;
  return (
    <div className="card">
      <h3>{title}</h3>
      <div className={`metric ${isNa ? "na" : ""}`}>{isNa ? "N/A" : value}</div>
    </div>
  );
}

export function MarketOverview({
  snapshot,
  timeframe,
}: {
  snapshot: MarketSnapshot | null;
  timeframe: string;
}) {
  const s = snapshot;
  const connected = s?.connected ?? false;
  const num = (v: number | null | undefined) =>
    v === null || v === undefined ? null : v.toString();

  return (
    <>
      <div className="section-title">Market Overview</div>
      {!connected && (
        <div className="notice">
          DATA SOURCE NOT CONNECTED — market values are not fabricated. A
          real-time provider is wired up in Phase 2.
        </div>
      )}
      <div className="grid grid-4">
        <Card title="Current Price" value={num(s?.last)} />
        <Card title="Bid" value={num(s?.bid)} />
        <Card title="Ask" value={num(s?.ask)} />
        <Card title="Spread" value={num(s?.spread)} />
        <Card
          title="Market Status"
          value={connected ? "Open" : "Disconnected"}
        />
        <Card
          title="Data Connection"
          value={(s?.connection_status ?? "disconnected").toUpperCase()}
        />
        <Card title="Current Timeframe" value={timeframe} />
        <Card title="Market Regime" value={connected ? "Unknown" : "Unknown"} />
      </div>
    </>
  );
}
