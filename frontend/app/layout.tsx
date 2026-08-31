import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "RexDayTrades — XAUUSD Trading Intelligence",
  description:
    "RexDayTrades: an XAUUSD day-trading intelligence platform. Live execution is user-initiated and gated by an independent risk engine — never automatic.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
