import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  DivergenceResponse,
  EtfDetail,
  EtfShareStatus,
  FetchStatus,
  HeatmapPoint,
  OverviewResponse,
  SectorCard,
} from "@/types";

// ── Read hooks — daily-grade data, 5-min staleTime ───────────────────
// (Replaces the spec's "30s polling" — market data changes once/day and the
// backend caches 4–24h. Only fetch-status polls fast, conditionally below.)

export function useOverview() {
  return useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<OverviewResponse>("/overview").then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useHeatmap() {
  return useQuery({
    queryKey: ["heatmap"],
    queryFn: () => api.get<HeatmapPoint[]>("/heatmap").then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useSectorCards() {
  return useQuery({
    queryKey: ["sector-cards"],
    queryFn: () => api.get<SectorCard[]>("/sector-cards").then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useSectorEtf(code: string | null) {
  return useQuery({
    queryKey: ["sector-etf", code],
    queryFn: () => api.get<EtfDetail>(`/sector-etf/${code}`).then((r) => r.data),
    enabled: !!code,
    staleTime: 5 * 60_000,
  });
}

// 详情接口二合一：宽基走 /index-etf、行业走 /sector-etf，两者返回同构 EtfDetail。
export function useEtfDetail(code: string | null, kind: "index" | "sector") {
  const base = kind === "index" ? "/index-etf" : "/sector-etf";
  return useQuery({
    queryKey: ["etf-detail", kind, code],
    queryFn: () => api.get<EtfDetail>(`${base}/${code}`).then((r) => r.data),
    enabled: !!code,
    staleTime: 5 * 60_000,
  });
}

// 价格×份额背离（多时间窗）。window ∈ 5/10/20/60，其它值后端回落到 10。
export function useDivergence(window = 10) {
  return useQuery({
    queryKey: ["divergence", window],
    queryFn: () =>
      api
        .get<DivergenceResponse>("/divergence", { params: { window } })
        .then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

// ── Fetch job: trigger + smart status polling ────────────────────────
// Polls /api/fetch/status every 2s ONLY while a job is running; otherwise
// the interval returns false and polling stops entirely (no idle hammering).

export function useFetchStatus() {
  return useQuery({
    queryKey: ["fetch-status"],
    queryFn: () => api.get<FetchStatus>("/fetch/status").then((r) => r.data),
    refetchInterval: (query) => (query.state.data?.running ? 2000 : false),
    staleTime: 0,
  });
}

// ETF share-data coverage + latest data date. Refreshed automatically when a
// fetch job finishes (useInvalidateOnFetchDone invalidates all queries).
export function useEtfShareStatus() {
  return useQuery({
    queryKey: ["etf-share-status"],
    queryFn: () => api.get<EtfShareStatus>("/etf-share/status").then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useTriggerFetch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (task: "all" | "etf" | "tushare") =>
      api.post(`/fetch/${task}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fetch-status"] }),
    onError: (e: Error) => {
      // No toast lib yet — console + alert so a failed refresh is not silent.
      // (The axios response interceptor already extracted a friendly message.)
      console.error("[fetch] refresh failed:", e.message);
      if (typeof window !== "undefined") window.alert(`刷新失败：${e.message}`);
    },
  });
}

/**
 * When a data-refresh job transitions running -> done, bust ALL read caches.
 * The backend already invalidated Redis (_cache_invalidate in fetch.py); the
 * frontend must follow suit or read pages keep showing pre-job data until their
 * 5-min staleTime expires. Call once, at the app root.
 */
export function useInvalidateOnFetchDone() {
  const qc = useQueryClient();
  const prevRunning = useRef(false);
  const status = useFetchStatus();
  const running = !!status.data?.running;
  useEffect(() => {
    if (prevRunning.current && !running) {
      qc.invalidateQueries();
    }
    prevRunning.current = running;
  }, [running, qc]);
}
