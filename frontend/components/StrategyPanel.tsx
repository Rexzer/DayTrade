import { StrategiesResponse } from "@/lib/api";

export function StrategyPanel({ data }: { data: StrategiesResponse | null }) {
  const planned = data?.planned ?? [];
  const connected = data?.connected ?? false;
  return (
    <div className="card">
      <h3>Strategies</h3>
      {!connected && (
        <div className="notice" style={{ marginBottom: 12 }}>
          No strategies connected. The built-in strategy families below are
          added in Phase 2.
        </div>
      )}
      {planned.map((s) => (
        <div className="row" key={s.key}>
          <span>{s.name}</span>
          <span className="badge gray">No setup</span>
        </div>
      ))}
    </div>
  );
}
