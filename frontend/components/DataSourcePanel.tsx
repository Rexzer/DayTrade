import { FeedHealth, MarketStatus } from "@/lib/api";

function fmtTime(epoch: number | null | undefined): string {
  if (!epoch) return "—";
  const d = new Date(epoch * 1000);
  return d.toISOString().replace("T", " ").replace(".000Z", " UTC");
}

function statusBadge(status: string | undefined) {
  const s = (status ?? "disconnected").toLowerCase();
  const cls =
    s === "live" ? "green" : s === "delayed" ? "warn" : s === "stale" ? "red" : "gray";
  return <span className={`badge ${cls}`}>{s.toUpperCase()}</span>;
}

// Shows DATA SOURCE / LAST UPDATE / STATUS per the spec, plus a clear label
// when the feed is simulated (never presenting synthetic data as real).
export function DataSourcePanel({
  status,
  health,
}: {
  status: MarketStatus | null;
  health: FeedHealth | null;
}) {
  const dataStatus = health?.status ?? status?.health?.status;
  const source = status?.source ?? "not connected";
  const lastUpdate = health?.last_update_epoch ?? status?.last_update_epoch ?? null;

  return (
    <div className="card">
      <h3>Data Source</h3>
      {status?.simulated && (
        <div className="notice warn" style={{ marginBottom: 10 }}>
          SIMULATED FEED — synthetic prices for development only. This is NOT
          real market data.
        </div>
      )}
      <div className="row">
        <span className="label">Data source</span>
        <span>{source}</span>
      </div>
      <div className="row">
        <span className="label">Broker symbol</span>
        <span>{status?.broker_symbol ?? "—"}</span>
      </div>
      <div className="row">
        <span className="label">Last update</span>
        <span>{fmtTime(lastUpdate)}</span>
      </div>
      <div className="row">
        <span className="label">Connection</span>
        <span>{(status?.connection_state ?? "disconnected").toUpperCase()}</span>
      </div>
      <div className="row">
        <span className="label">Status</span>
        <span>{statusBadge(dataStatus)}</span>
      </div>
    </div>
  );
}
