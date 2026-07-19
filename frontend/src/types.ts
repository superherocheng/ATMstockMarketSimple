// API response types — MIRROR src/web/schemas.py field-for-field.
// Do not rename fields; they must match the backend JSON exactly (success GETs
// are bare data, no envelope).
//
// Serialization (server-side safe_dict): NaN/±inf -> null, numpy -> number,
// date/datetime/Timestamp -> ISO "YYYY-MM-DD" string.

export interface OverviewBar {
  ts_code: string;
  name: string;
  trade_date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  pre_close: number | null;
  vol: number | null;
  amount: number | null;
  pct_chg: number | null;
  share_change_qty: number | null;
  share_change_pct: number | null;
  share_change_10d_qty: number | null;
  share_change_10d_pct: number | null;
  latest_share: number | null;
  share_date: string | null;
}

export interface OverviewResponse {
  index_etf: OverviewBar[];
  sector_summary: OverviewBar[];
}

export interface HeatmapPoint {
  name: string;
  ts_code: string;
  pct_chg: number;
}

export interface SectorCard {
  ts_code: string;
  name: string;
  trade_date: string | null;
  pct_chg: number;
  close: number;
  amplitude: number;
  sparkline: number[];
}

export interface FetchStatus {
  running: boolean;
  log: string[];
  started_at: string | null;
  finished_at: string | null;
  current_step: string;
  progress: number;
  backtest_done: boolean;
}

// GET /api/etf-share/status — share-data coverage (TopBar status chips).
export interface EtfShareStatus {
  latest_trading_date: string; // "YYYYMMDD"
  is_up_to_date: boolean;
  summary: {
    total: number;
    fresh: number;
    not_fresh: number;
  };
}

// ETF detail (raw-dict endpoint, shape from etf.py _compute_*_etf).
export interface KlineBar {
  ts_code: string;
  trade_date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  vol: number | null;
  amount: number | null;
  pre_close: number | null;
  pct_chg: number | null;
}

export interface SharePoint {
  trade_date: string | null;
  fd_share: number | null;
}

export interface EtfDetail {
  kline: KlineBar[];
  shares: SharePoint[];
  anomalies: {
    price: Array<{ trade_date: string; pct_chg: number }>;
    share: Array<Record<string, number | string | null>>;
  };
  name: string;
}

// Error envelope — appears ONLY on non-2xx (global handlers in app.py).
export interface ApiErrorEnvelope {
  success: false;
  error: string;
  timestamp: string | null;
  data?: unknown;
}
