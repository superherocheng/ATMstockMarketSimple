import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EChartsChart } from "@/components/EChartsChart";
import { DivTag } from "@/components/DivergenceScatter";
import { useDivergence, useEtfDetail, useOverview } from "@/hooks/useApi";
import type { EtfDetail } from "@/types";

// ECharts can't read CSS variables directly; resolve --up/--down so the volume
// bars follow the design system (and the dark-mode overrides in index.css).
const cssVar = (name: string): string =>
  typeof document !== "undefined"
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    : "";

function calcVolPercentile(volumes: number[], lookback = 60): number[] {
  return volumes.map((v, i) => {
    const start = Math.max(0, i - lookback + 1);
    const window = volumes.slice(start, i + 1);
    const rank = window.filter((x) => x <= v).length;
    return Math.round((rank / window.length) * 100);
  });
}

function calcMA(closes: number[], period: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i < period - 1) return null;
    const slice = closes.slice(i - period + 1, i + 1);
    return slice.reduce((a, b) => a + b, 0) / period;
  });
}

/**
 * 价格 × 份额 三grid对齐图：K线(+MA5/20+价格异常点) / 成交量百分位 / 份额。
 * 三段共享同一时间轴、dataZoom 与十字光标 — 背离区间上下直接对齐可见。
 */
function buildCombinedOption(d?: EtfDetail): Record<string, unknown> {
  if (!d || !d.kline?.length) return {};
  const kline = d.kline;
  const dates = kline.map((k) => k.trade_date ?? "");
  const ohlc = kline.map((k) => [k.open ?? 0, k.close ?? 0, k.low ?? 0, k.high ?? 0]);
  const volumes = kline.map((k) => k.vol ?? 0);
  const pcts = kline.map((k) => k.pct_chg ?? 0);
  const closes = kline.map((k) => k.close ?? 0);
  const volPct = calcVolPercentile(volumes, 60);
  const ma5 = calcMA(closes, 5);
  const ma20 = calcMA(closes, 20);
  const shares = d.shares ?? [];
  const shareDates = shares.map((s) => s.trade_date ?? "");
  const shareVals = shares.map((s) => s.fd_share ?? null);

  const up = cssVar("--up") || "#ff4d4f";
  const down = cssVar("--down") || "#52c41a";
  const ma5Color = "#5b8ff9";
  const ma20Color = "#f5a623";
  const anomalyColor = "#e6a23c";

  const total = dates.length;
  // 默认展示最近 60 根（背离通常看 1-3 个月），可拖 zoom 看全历史
  const zoomStart = total > 60 ? ((total - 60) / total) * 100 : 0;

  // 异常点标注（接口已算好 z>2 的日期），标在对应日期的 K线高点 / 份额值上
  const highByDate = new Map(kline.map((k) => [k.trade_date ?? "", k.high ?? 0]));
  const priceMarks = (d.anomalies?.price ?? []).slice(-15).map((a) => ({
    coord: [a.trade_date, (highByDate.get(a.trade_date) ?? 0) * 1.004],
    symbol: "circle",
    symbolSize: 5,
  }));
  const shareByDate = new Map(shares.map((s) => [s.trade_date ?? "", s.fd_share ?? 0]));
  const shareMarks = (d.anomalies?.share ?? []).slice(-15).map((a) => {
    const date = a.trade_date == null ? "" : String(a.trade_date);
    return {
      coord: [date, shareByDate.get(date) ?? 0],
      symbol: "diamond",
      symbolSize: 7,
    };
  });

  return {
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 56, right: 20, top: 28, height: "40%" },
      { left: 56, right: 20, top: "54%", height: "12%" },
      { left: 56, right: 20, top: "71%", height: "20%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false }, axisTick: { show: false } },
      { type: "category", data: dates, gridIndex: 1, axisLabel: { show: false }, axisTick: { show: false } },
      { type: "category", data: shareDates, gridIndex: 2, axisLabel: { fontSize: 9 } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0 },
      { gridIndex: 1, min: 0, max: 100, axisLabel: { formatter: "{value}%", fontSize: 9 } },
      { scale: true, gridIndex: 2, name: "份额", nameTextStyle: { fontSize: 9 } },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        markPoint: {
          animation: false,
          label: { show: false },
          itemStyle: { color: anomalyColor },
          data: priceMarks,
        },
      },
      {
        name: "MA5",
        type: "line",
        data: ma5,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: ma5Color },
        itemStyle: { color: ma5Color },
      },
      {
        name: "MA20",
        type: "line",
        data: ma20,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: ma20Color },
        itemStyle: { color: ma20Color },
      },
      {
        name: "成交量百分位",
        type: "bar",
        data: volPct.map((pct, i) => ({
          value: pct,
          itemStyle: { color: (pcts[i] ?? 0) >= 0 ? up : down },
        })),
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
      {
        name: "份额",
        type: "line",
        data: shareVals,
        xAxisIndex: 2,
        yAxisIndex: 2,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5 },
        areaStyle: { opacity: 0.06 },
        markPoint: {
          animation: false,
          label: { show: false },
          itemStyle: { color: anomalyColor },
          data: shareMarks,
        },
      },
    ],
    legend: {
      top: 0,
      data: ["MA5", "MA20"],
      textStyle: { fontSize: 10 },
      itemWidth: 14,
      itemHeight: 2,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: function (params: unknown[]) {
        const arr = params as Record<string, unknown>[];
        if (!arr.length) return "";
        let html = "<b>" + (arr[0].axisValue ?? "") + "</b><br/>";
        arr.forEach((p) => {
          const val = p.value;
          const name = p.seriesName as string;
          if (name === "K线" && Array.isArray(val)) {
            html +=
              "开:" + Number(val[1]).toFixed(3) +
              " 收:" + Number(val[2]).toFixed(3) +
              " 低:" + Number(val[3]).toFixed(3) +
              " 高:" + Number(val[4]).toFixed(3) + "<br/>";
          } else if (name === "MA5" || name === "MA20") {
            if (val != null) html += (p.marker as string) + name + ": " + Number(val).toFixed(3) + "<br/>";
          } else if (name === "成交量百分位") {
            html += (p.marker as string) + "量百分位: " + Number(val).toFixed(0) + "%<br/>";
          } else if (name === "份额" && val != null) {
            html += (p.marker as string) + "份额: " + Number(val).toFixed(0) + "万份<br/>";
          }
        });
        return html;
      },
    },
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1, 2], start: zoomStart, end: 100 },
      { type: "slider", xAxisIndex: [0, 1, 2], start: zoomStart, end: 100, height: 18, bottom: 8 },
    ],
  };
}

export default function ETFDetail() {
  const overview = useOverview();
  const [searchParams, setSearchParams] = useSearchParams();
  // 选中项：URL ?code=（来自概览点击）> 默认第一只行业 > 第一只宽基 > null
  const selected =
    searchParams.get("code") ??
    overview.data?.sector_summary[0]?.ts_code ??
    overview.data?.index_etf[0]?.ts_code ??
    null;
  const indexCodes = useMemo(
    () => new Set((overview.data?.index_etf ?? []).map((r) => r.ts_code)),
    [overview.data],
  );
  const kind: "index" | "sector" = indexCodes.has(selected ?? "") ? "index" : "sector";
  const detail = useEtfDetail(selected, kind);

  // 头部统计条：10日价格/份额/净流入 + 绝对背离标签
  const divergence = useDivergence(10);
  const divItem = (divergence.data?.items ?? []).find((i) => i.ts_code === selected);
  const price10 = divItem?.price_chg_pct ?? null;
  const share10 = divItem?.share_chg_pct ?? null;
  const flow10 = divItem?.net_inflow ?? null;

  const combinedOption = useMemo(() => buildCombinedOption(detail.data), [detail.data]);

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">
          ETF 详情{detail.data?.name ? ` · ${detail.data.name}` : ""}
        </h1>
        <select
          value={selected ?? ""}
          onChange={(e) => setSearchParams(e.target.value ? { code: e.target.value } : {})}
          className="border border-input bg-card px-3 py-1.5 text-sm"
        >
          {overview.data && (
            <>
              <optgroup label="宽基指数">
                {overview.data.index_etf.map((r) => (
                  <option key={r.ts_code} value={r.ts_code}>{r.name}</option>
                ))}
              </optgroup>
              <optgroup label="行业主题">
                {overview.data.sector_summary.map((r) => (
                  <option key={r.ts_code} value={r.ts_code}>{r.name}</option>
                ))}
              </optgroup>
            </>
          )}
        </select>
      </div>

      {divItem && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 font-mono text-xs text-muted-foreground">
          <span>
            10日价格{" "}
            <span className={price10 != null && price10 >= 0 ? "text-up" : "text-down"}>
              {price10 != null ? `${price10 >= 0 ? "+" : ""}${price10.toFixed(2)}%` : "—"}
            </span>
          </span>
          <span>
            10日份额{" "}
            <span className={share10 != null && share10 >= 0 ? "text-up" : "text-down"}>
              {share10 != null ? `${share10 >= 0 ? "+" : ""}${share10.toFixed(2)}%` : "—"}
            </span>
          </span>
          <span>
            10日净流入{" "}
            <span className={flow10 != null && flow10 >= 0 ? "text-up" : "text-down"}>
              {flow10 != null ? `${flow10 >= 0 ? "+" : ""}${(flow10 / 1e4).toFixed(1)}亿` : "—"}
            </span>
          </span>
          <DivTag it={divItem} />
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            价格 × 份额（上下对齐）
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              前/复权K线 · MA5/MA20 · ○ 价格异常点 · ◇ 份额异常点 · 共享缩放
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {detail.data ? (
            <EChartsChart option={combinedOption} height={560} />
          ) : detail.isError ? (
            <p className="py-16 text-center text-sm text-destructive">数据加载失败</p>
          ) : (
            <p className="py-16 text-center text-sm text-muted-foreground">加载中…</p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
