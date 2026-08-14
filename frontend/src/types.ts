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
  amount: number | null; // 最新成交额（tushare 千元）— treemap 面积维度
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

// GET /api/divergence?window=10 — 价格×份额背离分析（宽基+行业全量）。
// divergence 是绝对口径：不看横截面排名，价涨份额缩=risk、价跌份额增=lurk。
export interface DivergenceItem {
  ts_code: string;
  name: string;
  type: "index" | "sector";
  price_chg_pct: number | null; // 区间价格涨跌 %（前复权）
  share_chg_pct: number | null; // 区间份额变化 %
  share_chg_qty: number | null; // 万份
  nav: number | null; // 元（最新收盘价近似单位净值）
  net_inflow: number | null; // 万元 = 份额变化 × nav（资金口径）
  amount: number | null; // 千元（最新成交额）
  divergence: "risk" | "lurk" | "none";
  risk_streak: number; // 连续「价涨份额缩」交易日数
  lurk_streak: number; // 连续「价跌份额增」交易日数
  rank_gap: number | null; // |价格排名 − 份额排名|（相对背离强度）
  quadrant: number | null; // 相对象限 1-4（仅行业 ETF 有）
}

export interface DivergenceResponse {
  date: string | null; // "YYYYMMDD"
  window: number;
  items: DivergenceItem[];
}

// Error envelope — appears ONLY on non-2xx (global handlers in app.py).
export interface ApiErrorEnvelope {
  success: false;
  error: string;
  timestamp: string | null;
  data?: unknown;
}
