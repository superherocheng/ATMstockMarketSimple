import { useQuery } from '@tanstack/react-query';
import api from './client';

// ── Types ──
export interface ETFInfo {
  ts_code: string;
  name: string;
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  vol: number;
  amount: number;
  pre_close: number;
  pct_chg: number;
}

export interface SectorSummary {
  name: string;
  ts_code: string;
  pct_chg: number;
}

export interface OverviewData {
  index_etf: ETFInfo[];
  sector_summary: SectorSummary[];
}

export interface KlineItem {
  trade_date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  vol: number;
  amount: number;
  pct_chg: number;
}

export interface AnomalyItem {
  trade_date: string;
  pct_chg?: number;
  chg_pct?: number;
  z_score?: number;
}

export interface ETFDetailData {
  name: string;
  ts_code: string;
  kline: KlineItem[];
  shares: { trade_date: string; fd_share: number }[];
  anomalies: {
    price: AnomalyItem[];
    share: AnomalyItem[];
  };
}

export interface DataRangeInfo {
  [table: string]: {
    display_name: string;
    exists: boolean;
    count: number;
    min_date: string | null;
    max_date: string | null;
  };
}

export interface FetchStatus {
  running: boolean;
  progress: number;
  current_step: string;
  log: string[];
  finished_at: string | null;
}

export interface SectorCard {
  ts_code: string;
  name: string;
  trade_date: string;
  pct_chg: number;
  close: number;
  amplitude: number;
  sparkline: number[];
}

// ── Hooks ──
export function useOverview() {
  return useQuery<OverviewData>({
    queryKey: ['overview'],
    queryFn: () => api.get('/api/overview'),
    staleTime: 4 * 60 * 60 * 1000, // 4 hours
  });
}

export function useETFDetail(code: string) {
  return useQuery<ETFDetailData>({
    queryKey: ['etf-detail', code],
    queryFn: () => api.get(`/api/index-etf/${code}`),
    enabled: !!code,
  });
}

export function useSectorDetail(code: string) {
  return useQuery<ETFDetailData>({
    queryKey: ['sector-detail', code],
    queryFn: () => api.get(`/api/sector-etf/${code}`),
    enabled: !!code,
  });
}

export function useDataRange() {
  return useQuery<DataRangeInfo>({
    queryKey: ['data-range'],
    queryFn: () => api.get('/api/data-range'),
    staleTime: 10 * 60 * 1000,
  });
}

export function useFetchStatus() {
  return useQuery<FetchStatus>({
    queryKey: ['fetch-status'],
    queryFn: () => api.get('/api/fetch/status'),
    refetchInterval: (query) => (query?.state?.data?.running ? 2000 : false),
  });
}

export function useStockRanking(type: string) {
  return useQuery({
    queryKey: ['stock-ranking', type],
    queryFn: () => api.get(`/api/stocks/ranking?type=${type}`),
  });
}

export function useStockDetail(code: string) {
  return useQuery({
    queryKey: ['stock-detail', code],
    queryFn: () => api.get(`/api/stock/${code}`),
    enabled: !!code,
  });
}

export function useBarraSummary() {
  return useQuery({
    queryKey: ['barra-summary'],
    queryFn: () => api.get('/api/barra/summary'),
  });
}

export function useConceptData() {
  return useQuery({
    queryKey: ['concept'],
    queryFn: () => api.get('/api/concept'),
  });
}

export function useIndustryData() {
  return useQuery({
    queryKey: ['industry'],
    queryFn: () => api.get('/api/industry'),
  });
}

export interface SectorETFsData {
  ts_code: string;
  name: string;
  kline: KlineItem[];
  shares: { trade_date: string; fd_share: number }[];
}

export function useSectorCards() {
  return useQuery<SectorCard[]>({
    queryKey: ['sector-cards'],
    queryFn: () => api.get('/api/sector-cards'),
    staleTime: 4 * 60 * 60 * 1000,
  });
}

export function useAllSectorETFs() {
  return useQuery<SectorETFsData[]>({
    queryKey: ['all-sector-etfs'],
    queryFn: () => api.get('/api/sector-etf'),
    staleTime: 4 * 60 * 60 * 1000,
  });
}
