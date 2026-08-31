import { AccountInfo } from "@/lib/api";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="row">
      <span className="label">{label}</span>
      <span>{value}</span>
    </div>
  );
}

export function AccountPanel({ account }: { account: AccountInfo | null }) {
  const na = "N/A";
  return (
    <div className="card">
      <h3>Account</h3>
      {!account?.connected && (
        <div className="notice" style={{ marginBottom: 12 }}>
          ACCOUNT NOT CONNECTED — no balances are fabricated. MetaTrader
          integration is added in Phase 5.
        </div>
      )}
      <Row label="Balance" value={na} />
      <Row label="Equity" value={na} />
      <Row label="Margin" value={na} />
      <Row label="Free Margin" value={na} />
      <Row label="Open Positions" value={String(account?.open_positions ?? 0)} />
      <Row label="Today's P&L" value={na} />
      <Row label="Daily Drawdown" value={na} />
    </div>
  );
}
