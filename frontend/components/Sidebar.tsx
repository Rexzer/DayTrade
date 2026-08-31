"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

// The 15 pages from the spec. Phase 1 ships Dashboard + Settings as working
// pages; the rest are listed so navigation is complete and honest about what
// is available now.
const NAV: Array<{ href: string; label: string; ready: boolean }> = [
  { href: "/", label: "Dashboard", ready: true },
  { href: "/chart", label: "Live XAUUSD Chart", ready: false },
  { href: "/strategies", label: "Strategies", ready: true },
  { href: "/strategy-builder", label: "Strategy Builder", ready: true },
  { href: "/backtesting", label: "Backtesting", ready: true },
  { href: "/paper-trading", label: "Paper Trading", ready: true },
  { href: "/live-trading", label: "Live Trading", ready: true },
  { href: "/journal", label: "Trade Journal", ready: true },
  { href: "/analytics", label: "Performance Analytics", ready: true },
  { href: "/news", label: "Market News", ready: false },
  { href: "/account", label: "Account", ready: false },
  { href: "/settings", label: "Settings", ready: true },
  { href: "/risk", label: "Risk Management", ready: false },
  { href: "/connections", label: "Data Connections", ready: true },
  { href: "/assistant", label: "AI Assistant", ready: true },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <nav className="sidebar">
      <div className="brand">
        <span className="dot" />
        <span>XAUUSD Platform</span>
      </div>
      {NAV.map((item) => {
        const active = pathname === item.href;
        if (!item.ready) {
          return (
            <span
              key={item.href}
              className="nav-item locked"
              title="Available in a later phase"
            >
              {item.label}
            </span>
          );
        }
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-item ${active ? "active" : ""}`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
