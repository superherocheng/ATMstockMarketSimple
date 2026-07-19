import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EChartsChart } from "@/components/EChartsChart";
import { useSectorCards, useSectorEtf } from "@/hooks/useApi";
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

function buildKlineOption(d?: EtfDetail): Record<string, unknown> {
  if (!d || !d.kline?.length) return {};
  const kline = d.kline;
  const dates = kline.map((k) => k.trade_date ?? "");
  const ohlc = kline.map((k) => [k.open ?? 0, k.close ?? 0, k.low ?? 0, k.high ?? 0]);
  const volumes = kline.map((k) => k.vol ?? 0);
  const pcts = kline.map((k) => k.pct_chg ?? 0);
  const volPct = calcVolPercentile(volumes, 60);

  const up = cssVar("--up") || "#ff4d4f";
  const down = cssVar("--down") || "#52c41a";

  const total = dates.length;
  const zoomStart = total > 20 ? ((total - 20) / total) * 100 : 0;

  return {
    grid: [
      { left: 50, right: 20, top: 16, height: "55%" },
      { left: 50, right: 20, top: "72%", height: "20%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { fontSize: 9 } },
      { type: "category", data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, type: "value" },
      { scale: true, gridIndex: 1, type: "value", min: 0, max: 100, axisLabel: { formatter: "{value}%" } },
    ],
    series: [
      { type: "candlestick", data: ohlc, xAxisIndex: 0, yAxisIndex: 0 },
      {
        type: "bar",
        data: volPct.map((pct, i) => ({
          value: pct,
          itemStyle: { color: (pcts[i] ?? 0) >= 0 ? up : down },
        })),
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
    ],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: function (params: unknown[]) {
        const arr = params as Record<string, unknown>[];
        if (!arr.length) return "";
        let html = "<b>" + (arr[0].axisValue ?? "") + "</b><br/>";
        arr.forEach((p) => {
          const val = p.value;
          if (Array.isArray(val)) {
            html +=
              "K线 开:" +
              Number(val[1]).toFixed(2) +
              " 收:" +
              Number(val[2]).toFixed(2) +
              " 低:" +
              Number(val[3]).toFixed(2) +
              " 高:" +
              Number(val[4]).toFixed(2) +
              "<br/>";
          } else {
            html += (p.marker as string) + " 成交量百分位: " + Number(val).toFixed(0) + "%<br/>";
          }
        });
        return html;
      },
    },
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: zoomStart, end: 100 },
      { type: "slider", xAxisIndex: [0, 1], start: zoomStart, end: 100, height: 18, bottom: 8 },
    ],
  };
}

function buildShareOption(d?: EtfDetail): Record<string, unknown> {
  if (!d || !d.shares?.length) return {};
  const shares = d.shares;
  const total = shares.length;
  const zoomStart = total > 20 ? ((total - 20) / total) * 100 : 0;
  return {
    grid: { left: 60, right: 20, top: 16, bottom: 56 },
    xAxis: {
      type: "category",
      data: shares.map((s) => s.trade_date ?? ""),
      axisLabel: { fontSize: 9, rotate: 45 },
    },
    yAxis: { type: "value", name: "份额" },
    series: [
      {
        type: "line",
        data: shares.map((s) => s.fd_share ?? null),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5 },
      },
    ],
    tooltip: { trigger: "axis" },
    dataZoom: [
      { type: "inside", start: zoomStart, end: 100 },
      { type: "slider", start: zoomStart, end: 100, height: 18, bottom: 8 },
    ],
  };
}

export default function ETFDetail() {
  const cards = useSectorCards();
  const [searchParams, setSearchParams] = useSearchParams();
  // 选中项：URL ?code=（来自首页热度芯片点击）> 默认第一只 > null
  const selected = searchParams.get("code") ?? cards.data?.[0]?.ts_code ?? null;
  const detail = useSectorEtf(selected);

  const klineOption = useMemo(() => buildKlineOption(detail.data), [detail.data]);
  const shareOption = useMemo(() => buildShareOption(detail.data), [detail.data]);

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
          {cards.data?.map((c) => (
            <option key={c.ts_code} value={c.ts_code}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>K 线（前复权）</CardTitle>
          </CardHeader>
          <CardContent>
            {detail.data ? (
              <EChartsChart option={klineOption} height={360} />
            ) : (
              <p className="text-sm text-muted-foreground">加载中…</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>份额变动</CardTitle>
          </CardHeader>
          <CardContent>
            {detail.data ? (
              <EChartsChart option={shareOption} height={360} />
            ) : (
              <p className="text-sm text-muted-foreground">加载中…</p>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
