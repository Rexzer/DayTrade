import { NewsResponse } from "@/lib/api";

export function NewsPanel({ data }: { data: NewsResponse | null }) {
  return (
    <div className="card">
      <h3>News</h3>
      <div className="row">
        <span className="label">Next high-impact event</span>
        <span className="muted">{data?.status ?? "Data unavailable."}</span>
      </div>
      <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
        Economic calendar is connected in a later phase. Events are never
        fabricated.
      </div>
    </div>
  );
}
