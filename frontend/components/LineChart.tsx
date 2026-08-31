"use client";

// Minimal dependency-free SVG line chart for equity/drawdown curves. Avoids
// pulling a charting library for simple series and renders crisply at any size.
export function LineChart({
  points,
  height = 180,
  color = "#26a69a",
  fill = "rgba(38,166,154,0.12)",
  label,
}: {
  points: number[];
  height?: number;
  color?: string;
  fill?: string;
  label?: string;
}) {
  const width = 640;
  if (!points || points.length < 2) {
    return <div className="muted">No data to plot.</div>;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const stepX = width / (points.length - 1);
  const toY = (v: number) => height - ((v - min) / range) * (height - 10) - 5;
  const path = points
    .map((v, i) => `${i === 0 ? "M" : "L"} ${(i * stepX).toFixed(1)} ${toY(v).toFixed(1)}`)
    .join(" ");
  const area =
    `M 0 ${height} ` +
    points.map((v, i) => `L ${(i * stepX).toFixed(1)} ${toY(v).toFixed(1)}`).join(" ") +
    ` L ${width} ${height} Z`;

  return (
    <div>
      {label && (
        <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
          {label} · min {min.toFixed(2)} · max {max.toFixed(2)}
        </div>
      )}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={{ width: "100%", height, background: "var(--bg-elevated)", borderRadius: 8 }}
      >
        <path d={area} fill={fill} stroke="none" />
        <path d={path} fill="none" stroke={color} strokeWidth={1.5} />
      </svg>
    </div>
  );
}
