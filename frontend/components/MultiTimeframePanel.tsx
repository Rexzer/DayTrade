// Multi-timeframe analysis panel. Phase 1 shows UNKNOWN everywhere — the
// analysis engine that populates these fields arrives in Phase 2.
const TFS = ["4H", "1H", "15M", "5M"] as const;

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="row">
      <span className="label">{label}</span>
      <span>{value}</span>
    </div>
  );
}

export function MultiTimeframePanel() {
  return (
    <div className="card">
      <h3>Multi-Timeframe Analysis</h3>
      <div className="mtf-grid">
        {TFS.map((tf) => (
          <div className="mtf-cell" key={tf}>
            <div className="mtf-tf">{tf}</div>
            <Field label="Trend" value="UNKNOWN" />
            <Field label="Momentum" value="UNKNOWN" />
            <Field label="Structure" value="UNKNOWN" />
            <Field label="Signal" value="NONE" />
          </div>
        ))}
      </div>
    </div>
  );
}
