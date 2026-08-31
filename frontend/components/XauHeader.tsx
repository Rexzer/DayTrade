import { MarketSnapshot } from "@/lib/api";

function fmt(v: number | null): string {
  return v === null || v === undefined ? "N/A" : v.toString();
}

export function XauHeader({ snapshot }: { snapshot: MarketSnapshot | null }) {
  const connected = snapshot?.connected ?? false;
  return (
    <div className="xau-header">
      <div>
        <div className="xau-symbol">XAUUSD</div>
        <span className={`badge ${connected ? "green" : "gray"}`}>
          <span className="status-dot" />
          {connected ? "LIVE" : "Disconnected"}
        </span>
      </div>
      <div className="xau-quotes">
        <div>
          <div className="quote-label">Price</div>
          <div className="quote-value">{fmt(snapshot?.last ?? null)}</div>
        </div>
        <div>
          <div className="quote-label">Bid</div>
          <div className="quote-value">{fmt(snapshot?.bid ?? null)}</div>
        </div>
        <div>
          <div className="quote-label">Ask</div>
          <div className="quote-value">{fmt(snapshot?.ask ?? null)}</div>
        </div>
        <div>
          <div className="quote-label">Spread</div>
          <div className="quote-value">{fmt(snapshot?.spread ?? null)}</div>
        </div>
        <div>
          <div className="quote-label">Data</div>
          <div className="quote-value">
            <span className={`badge ${connected ? "green" : "gray"}`}>
              {snapshot?.data_status?.toUpperCase() ?? "NOT CONNECTED"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
