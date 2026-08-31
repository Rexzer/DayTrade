"use client";

import { useEffect, useState } from "react";
import {
  AccountInfo,
  MarketSnapshot,
  ModesResponse,
  NewsResponse,
  StrategiesResponse,
  apiGet,
} from "./api";

export interface DashboardData {
  snapshot: MarketSnapshot | null;
  account: AccountInfo | null;
  modes: ModesResponse | null;
  strategies: StrategiesResponse | null;
  news: NewsResponse | null;
  backendOnline: boolean;
  loading: boolean;
}

export function useDashboardData(pollMs = 5000): DashboardData {
  const [data, setData] = useState<DashboardData>({
    snapshot: null,
    account: null,
    modes: null,
    strategies: null,
    news: null,
    backendOnline: false,
    loading: true,
  });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [snap, acct, modes, strat, news] = await Promise.all([
        apiGet<MarketSnapshot>("/market/snapshot"),
        apiGet<AccountInfo>("/account"),
        apiGet<ModesResponse>("/mode"),
        apiGet<StrategiesResponse>("/strategies"),
        apiGet<NewsResponse>("/news/next"),
      ]);
      if (cancelled) return;
      setData({
        snapshot: snap.data,
        account: acct.data,
        modes: modes.data,
        strategies: strat.data,
        news: news.data,
        backendOnline: snap.ok || modes.ok,
        loading: false,
      });
    }

    load();
    const id = setInterval(load, pollMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [pollMs]);

  return data;
}
