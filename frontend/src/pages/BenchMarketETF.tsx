import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EChartsChart } from "@/components/EChartsChart";
import { useOverview } from "@/hooks/useApi";
import type { OverviewBar } from "@/types";

// ECharts can't read CSS variables directly; resolve --up/--down so the bars
// follow the design system (and the dark-mode overrides in index.css).
const cssVar = (name: string): string =>
  typeof document !== "undefined"
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    : "";

const UP = () => cssVar("--up") || "#ff4d4f";
const DOWN = () => cssVar("--down") || "#52c41a";

/**
 * Build a horizontal bar-chart option for one metric across the (already
 * pct_chg-sorted) ETF list. Bars are coloured by their own sign — positive →
 * up(red), negative → down(green) — matching the Chinese market convention.
 */
function buildBarOption(
  names: string[],
  values: number[],
  unit: string,
): Record<string, unknown> {
  const up = UP();
  const down = DOWN();
  return {
    grid: { left: 84, right: 56, top: 12, bottom: 24 },
    xAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { type: "dashed", opacity: 0.4 } },
    },
    yAxis: {
      type: "category",
      data: names,
      inverse: true, // pct_chg-desc data → highest gain sits at the top
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        barWidth: 18,
        data: values.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? up : down },
          // Label outside the bar end: right for positive, left for negative.
          label: {
            show: true,
            position: v >= 0 ? "right" : "left",
            formatter: () => `${v >= 0 ? "+" : ""}${v.toFixed(2)}${unit}`,
            fontSize: 11,
          },
        })),
      },
    ],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const arr = params as { name?: string; value?: number | { value?: number } }[];
        if (!arr.length) return "";
        const raw = arr[0].value;
        const v = typeof raw === "number" ? raw : (raw?.value ?? 0);
        return `<b>${arr[0].name ?? ""}</b><br/>${v >= 0 ? "+" : ""}${v.toFixed(2)} ${unit}`;
      },
    },
  };
}

export default function BenchMarketETF() {
  const overview = useOverview();

  // Sort once by 当天涨跌 desc and reuse the order for all three charts so the
  // same ETF lines up across charts for easy cross-comparison.
  const rows = useMemo(() => {
    const list: OverviewBar[] = overview.data?.index_etf ?? [];
    return [...list].sort(
      (a, b) => (b.pct_chg ?? -Infinity) - (a.pct_chg ?? -Infinity),
    );
  }, [overview.data]);

  const names = rows.map((r) => r.name);
  const dateRaw = rows[0]?.trade_date ?? null;
  const dateDisplay =
    dateRaw && dateRaw.length >= 10 ? dateRaw.slice(5, 10).replace("-", "/") : null;

  // fd_share is in 万份 → divide by 1e4 for 亿份 on the share charts.
  const chgOption = useMemo(
    () => buildBarOption(names, rows.map((r) => r.pct_chg ?? 0), "%"),
    [rows],
  );
  const shareOption = useMemo(
    () =>
      buildBarOption(
        names,
        rows.map((r) => (r.share_change_qty ?? 0) / 10000),
        "亿份",
      ),
    [rows],
  );
  const share10dOption = useMemo(
    () =>
      buildBarOption(
        names,
        rows.map((r) => (r.share_change_10d_qty ?? 0) / 10000),
        "亿份",
      ),
    [rows],
  );

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold">指数 ETF</h1>
        <p className="text-sm text-muted-foreground">
          宽基指数 ETF 当日表现
          {dateDisplay ? ` · 数据 ${dateDisplay}` : ""}
          <span className="ml-2 text-xs">（按当日涨跌降序）</span>
        </p>
      </div>

      {!overview.data || rows.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {overview.isError ? "数据加载失败，请稍后重试。" : "加载中…"}
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>当天涨跌 <span className="text-xs font-normal text-muted-foreground">%</span></CardTitle>
            </CardHeader>
            <CardContent>
              <EChartsChart option={chgOption} height={260} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>当天份额变化 <span className="text-xs font-normal text-muted-foreground">亿份（净申购 + / 净赎回 −）</span></CardTitle>
            </CardHeader>
            <CardContent>
              <EChartsChart option={shareOption} height={260} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>10 日累计份额变化 <span className="text-xs font-normal text-muted-foreground">亿份</span></CardTitle>
            </CardHeader>
            <CardContent>
              <EChartsChart option={share10dOption} height={260} />
            </CardContent>
          </Card>
        </>
      )}
    </main>
  );
}
