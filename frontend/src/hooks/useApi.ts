import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  CalendarResponse,
  DivergenceResponse,
  EtfDetail,
  EtfShareStatus,
  FetchStatus,
  HeatmapPoint,
  LocatorResponse,
  OverviewResponse,
  RotationResponse,
  SectorCard,
  ThermometerResponse,
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

// ── 择时仪表盘（/api/timing/*）— 派生指标，10 分钟 staleTime ─────────
export function useThermometer() {
  return useQuery({
    queryKey: ["timing-thermometer"],
    queryFn: () => api.get<ThermometerResponse>("/timing/thermometer").then((r) => r.data),
    staleTime: 10 * 60_000,
  });
}

export function useRotation() {
  return useQuery({
    queryKey: ["timing-rotation"],
    queryFn: () => api.get<RotationResponse>("/timing/rotation").then((r) => r.data),
    staleTime: 10 * 60_000,
  });
}

export function useCalendar() {
  return useQuery({
    queryKey: ["timing-calendar"],
    queryFn: () => api.get<CalendarResponse>("/timing/calendar").then((r) => r.data),
    staleTime: 30 * 60_000,
  });
}

export function useLocator() {
  return useQuery({
    queryKey: ["timing-locator"],
    queryFn: () => api.get<LocatorResponse>("/timing/locator").then((r) => r.data),
    staleTime: 10 * 60_000,
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

// Write-ops need the admin API token. Read-only builds no longer bake it into
// the public bundle, so ask for it once and keep it in this browser's
// localStorage — the request interceptor picks it up from there.
function ensureAdminToken(): boolean {
  if (typeof window === "undefined") return true;
  if (window.localStorage.getItem("atm_admin_token")) return true;
  if (import.meta.env.VITE_API_TOKEN) return true;
  const t = window.prompt("刷新数据需要管理 Token（仅首次输入，保存在本浏览器）：");
  if (t && t.trim()) {
    window.localStorage.setItem("atm_admin_token", t.trim());
    return true;
  }
  return false;
}

export function useTriggerFetch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (task: "all" | "etf" | "tushare") => {
      if (!ensureAdminToken()) throw new Error("未提供管理 Token，已取消刷新");
      return api.post(`/fetch/${task}`).then((r) => r.data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fetch-status"] }),
    onError: (e: Error) => {
      // A rejected token (e.g. rotated server-side) must not linger in
      // localStorage — drop it so the next click prompts for a fresh one.
      if (typeof window !== "undefined" && e.message.includes("未授权")) {
        try {
          window.localStorage.removeItem("atm_admin_token");
        } catch { /* storage blocked — nothing to clear */ }
      }
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
