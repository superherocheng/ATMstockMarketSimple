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
  quadrant: number | null; // 绝对象限 1-4（与散点同口径：价格符号×份额符号）
  factor_quadrant: number | null; // 因子引擎相对象限（EWMA份额斜率×波动调整动量）
  family_members: number | null; // >1 = 份额为同指数家族聚合值
}

export interface QuadrantStat {
  avg_fwd_15d_pct: number; // 该象限近60日 15日前瞻收益均值 %
  avg_etf_count: number;
  days: number;
}

export interface DivergenceResponse {
  date: string | null; // "YYYYMMDD"
  window: number;
  items: DivergenceItem[];
  quadrant_stats?: Record<string, QuadrantStat>; // 象限历史前瞻收益（角标）
}

// Error envelope — appears ONLY on non-2xx (global handlers in app.py).
export interface ApiErrorEnvelope {
  success: false;
  error: string;
  timestamp: string | null;
  data?: unknown;
}

// ── 择时仪表盘 (/api/timing/*) ───────────────────────────────────────

// GET /api/timing/thermometer — 大盘温度计（五面板 + 仓位合成）
export interface ValuationIndex {
  code: string;
  name: string;
  pe: number | null;
  pe_pct: number | null; // PE 历史百分位 0-100
  pb: number | null;
  pb_pct: number | null;
  days: number;
  date: string | null;
}

export interface TrendIndex {
  code: string;
  name: string;
  date: string | null;
  close: number;
  ma200: number | null;
  vs_ma200_pct: number | null;
  state: "above" | "below" | null;
  high_1y: number;
  low_1y: number;
  off_high_pct: number;
  off_low_pct: number;
}

export interface PanicPayload {
  code: string;
  name: string;
  date: string | null;
  current: {
    ret_5d: number | null;
    amount_z: number | null;
    triggered: boolean;
    last_event_idx: number | null;
  };
  stats: {
    n: number;
    mean_5d: number | null;
    win_5d: number | null;
    mean_10d: number | null;
    win_10d: number | null;
    mean_20d: number | null;
    win_20d: number | null;
  };
  recent_events: Array<{
    date: string;
    fwd_5d: number | null;
    fwd_10d: number | null;
    fwd_20d: number | null;
  }>;
}

export interface FamilyFlowIndex {
  code: string;
  name: string;
  family_members: number;
  chg_20d_pct: number | null;
  corr_60d: number | null; // 份额日变化×日收益 60日滚动相关
  regime: "dip_buying" | "chasing" | "neutral" | "unknown";
  series: Array<{ date: string; share: number; close: number | null }>;
}

export interface ThermometerResponse {
  date: string | null;
  valuation: { indices: ValuationIndex[] };
  valuation_median_pe_pct: number | null;
  trend: { indices: TrendIndex[] };
  panic: { market: PanicPayload | null; high_beta: PanicPayload[] };
  volatility: {
    date: string | null;
    vol_20d: number | null; // 年化 %
    vol_pct: number | null; // 历史百分位
    target_mult: number | null; // 建议仓位乘数 0.3-1.0
    target_vol: number;
    series: Array<{ date: string; vol: number }>;
  };
  family_flow: { indices: FamilyFlowIndex[] };
  position: {
    suggested_pct: number;
    decomposition: Array<{ name: string; value: number | null; note: string }>;
    icir_value: number | null;
  };
}

// GET /api/timing/rotation — 情绪×轮动 3×3（中信期货双指标框架）
export interface RotationResponse {
  date?: string;
  data_incomplete?: boolean;
  sentiment: {
    date: string;
    score: number;
    regime: string;
    regime_label: string;
    series?: Array<{ date: string; score: number }>;
  };
  rotation: {
    date: string;
    score: number;
    strength_pct: number;
    level: string;
    level_label: string;
    series?: Array<{ date: string; rolling_mean: number }>;
  };
  regime_matrix: {
    current_cell: string[];
    recommended_position: number;
    level: string;
    action: string;
    sentiment_order: string[];
    rotation_order: string[];
    rows: Array<{
      sentiment: string;
      label: string;
      cells: Array<{
        sentiment: string;
        rotation: string;
        position: number;
        level: string;
        action: string;
        current: boolean;
      }>;
    }>;
  };
  narrative?: string[];
}

// GET /api/timing/calendar — 月度×ETF 平均收益热力图
export interface CalendarResponse {
  rows: Array<{
    code: string;
    name: string;
    type: "index" | "sector";
    months: Array<number | null>;
    n_months: number;
    first_date: string;
  }>;
  notes: Array<{ month: number; tag: string; note: string }>;
}

// GET /api/timing/locator — 底部定位器
export interface LocatorResponse {
  indices: Array<{
    code: string;
    name: string;
    series: Array<{ date: string; close: number; drawdown: number }>;
    share_series: Array<{ date: string; chg20_pct: number }>;
    events: Array<{
      date: string;
      drawdown: number;
      share_20d_pct: number | null;
      fwd_60d_pct: number | null;
    }>;
    current: { drawdown_pct: number; share_20d_pct: number | null; active: boolean };
  }>;
}
