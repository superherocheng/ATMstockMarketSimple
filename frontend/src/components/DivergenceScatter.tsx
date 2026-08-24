import { useMemo } from "react";
import { EChartsChart } from "@/components/EChartsChart";
import type { DivergenceItem, QuadrantStat } from "@/types";

// ECharts can't read CSS variables directly; resolve --up/--down so the chart
// follows the design system (same pattern as ETFDetail/BenchMarketETF).
const cssVar = (name: string, fallback: string): string =>
  typeof document !== "undefined"
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback;

// 语义色（双主题可读的中间色调，不随涨跌 token 走）：
// risk 背离（价涨份额缩）= 琥珀警告色；lurk 背离（价跌份额增）= 蓝色潜伏色。
export const RISK_COLOR = "#d97706";
export const LURK_COLOR = "#3b82f6";

/** 绝对背离标签 chip：risk=价涨份额缩（琥珀）、lurk=价跌份额增（蓝），带连续天数。 */
export function DivTag({ it }: { it?: DivergenceItem }) {
  if (!it || it.divergence === "none") {
    return <span className="text-muted-foreground">—</span>;
  }
  const risk = it.divergence === "risk";
  const streak = risk ? it.risk_streak : it.lurk_streak;
  return (
    <span
      className="inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs"
      style={{
        color: risk ? RISK_COLOR : LURK_COLOR,
        backgroundColor: (risk ? RISK_COLOR : LURK_COLOR) + "1f", // /12 透明度
      }}
    >
      {risk ? "风险背离" : "潜伏背离"}
      {streak > 0 ? `·${streak}日` : ""}
    </span>
  );
}

const QUADRANT_LABEL: Record<number, string> = {
  1: "强势",
  2: "潜伏",
  3: "撤离",
  4: "风险",
};

function colorOf(it: DivergenceItem, up: string, down: string): string {
  if (it.divergence === "risk") return RISK_COLOR;
  if (it.divergence === "lurk") return LURK_COLOR;
  // 共振：份额与价格同向 — 涨红跌绿
  return (it.share_chg_pct ?? 0) >= 0 ? up : down;
}

/**
 * 价格 × 份额背离散点图（共享组件）。
 * X=区间价格涨跌%、Y=区间份额变化%、气泡=最新成交额。
 * 右下象限（价涨份额缩）与左上象限（价跌份额增）铺淡色底，
 * 一眼定位「指数涨但份额跌」式的反比背离。
 */
export function DivergenceScatter({
  items,
  height = 340,
  labelAll = false,
  onPick,
  quadrantStats,
}: {
  items: DivergenceItem[];
  height?: number;
  /** 点少时（如 5 只宽基）给每个气泡标注名称 */
  labelAll?: boolean;
  /** 点击气泡回调（跳转 ETF 详情） */
  onPick?: (tsCode: string) => void;
  /** 各象限近60日15日前瞻收益（四角角标，来自 quadrant_perf） */
  quadrantStats?: Record<string, QuadrantStat>;
}) {
  const option = useMemo(
    () => buildOption(items, labelAll, quadrantStats),
    [items, labelAll, quadrantStats],
  );

  return (
    <EChartsChart
      option={option}
      height={height}
      onEvents={
        onPick
          ? {
              click: (p) => {
                const data = p.data as { ts_code?: string } | undefined;
                if (data?.ts_code) onPick(data.ts_code);
              },
            }
          : undefined
      }
    />
  );
}

function buildOption(
  items: DivergenceItem[],
  labelAll: boolean,
  quadrantStats?: Record<string, QuadrantStat>,
): Record<string, unknown> {
  const pts = items.filter(
    (i) => i.price_chg_pct != null && i.share_chg_pct != null,
  );
  if (!pts.length) return {};

  const up = cssVar("--up", "#ff4d4f");
  const down = cssVar("--down", "#52c41a");
  const maxAmount = Math.max(...pts.map((i) => i.amount ?? 0), 1);

  const scatterData = pts.map((it) => ({
    ts_code: it.ts_code,
    name: it.name,
    value: [it.price_chg_pct, it.share_chg_pct],
    itemStyle: { color: colorOf(it, up, down), opacity: 0.85 },
    // 面积感知：sqrt 缩放，8~34px
    symbolSize: 8 + 26 * Math.sqrt((it.amount ?? 0) / maxAmount),
  }));

  // 四角角标：各象限近60日的15日前瞻收益（quadrant_perf 聚合）
  const graphic: unknown[] = [];
  if (quadrantStats) {
    const corners: Array<{ q: string; x: string; y: string; label: string }> = [
      { q: "2", x: "left", y: "top", label: "潜伏" },
      { q: "1", x: "right", y: "top", label: "强势" },
      { q: "3", x: "left", y: "bottom", label: "撤离" },
      { q: "4", x: "right", y: "bottom", label: "风险" },
    ];
    for (const c of corners) {
      const st = quadrantStats[c.q];
      if (!st) continue;
      const v = st.avg_fwd_15d_pct;
      graphic.push({
        type: "text",
        left: c.x,
        top: c.y,
        style: {
          text: `${c.label} 15日${v >= 0 ? "+" : ""}${v.toFixed(1)}%`,
          fill: v >= 0 ? up : down,
          fontSize: 10,
          opacity: 0.8,
        },
        silent: true,
      });
    }
  }

  return {
    graphic,
    grid: { left: 56, right: 24, top: 20, bottom: 40 },
    xAxis: {
      type: "value",
      name: "价格 %",
      nameLocation: "middle",
      nameGap: 26,
      nameTextStyle: { fontSize: 10 },
      axisLine: { show: false },
      splitLine: { lineStyle: { type: "dashed", opacity: 0.3 } },
    },
    yAxis: {
      type: "value",
      name: "份额 %",
      nameTextStyle: { fontSize: 10 },
      axisLine: { show: false },
      splitLine: { lineStyle: { type: "dashed", opacity: 0.3 } },
    },
    series: [
      {
        type: "scatter",
        data: scatterData,
        // 0 轴参考线 + 两个背离象限的淡色底
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed", opacity: 0.5 },
          label: { show: false },
          data: [{ xAxis: 0 }, { yAxis: 0 }],
        },
        markArea: {
          silent: true,
          data: [
            // 右下：价涨份额缩（风险背离）
            [
              {
                xAxis: 0,
                yAxis: "min",
                itemStyle: { color: RISK_COLOR, opacity: 0.07 },
              },
              { xAxis: "max", yAxis: 0 },
            ],
            // 左上：价跌份额增（潜伏背离）
            [
              {
                xAxis: "min",
                yAxis: 0,
                itemStyle: { color: LURK_COLOR, opacity: 0.07 },
              },
              { xAxis: 0, yAxis: "max" },
            ],
          ],
        },
        label: labelAll
          ? { show: true, position: "top", fontSize: 10, formatter: (p: { data: { name: string } }) => p.data.name }
          : { show: false },
        emphasis: { focus: "self" },
      },
    ],
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const param = p as {
          data: { name?: string; ts_code?: string; value?: number[] };
        };
        const d = param.data;
        if (!d?.value) return "";
        const it = pts.find((x) => x.ts_code === d.ts_code);
        if (!it) return "";
        const flow =
          it.net_inflow != null
            ? `${it.net_inflow >= 0 ? "+" : ""}${(it.net_inflow / 1e4).toFixed(1)}亿`
            : "—";
        const streak =
          it.divergence === "risk" && it.risk_streak > 0
            ? `<br/>连续背离 ${it.risk_streak} 日`
            : it.divergence === "lurk" && it.lurk_streak > 0
              ? `<br/>连续背离 ${it.lurk_streak} 日`
              : "";
        const quad = it.quadrant != null ? ` · ${QUADRANT_LABEL[it.quadrant]}` : "";
        const fam =
          it.family_members && it.family_members > 1
            ? ` · 家族聚合(${it.family_members})`
            : "";
        const fquad =
          it.factor_quadrant != null && it.factor_quadrant !== it.quadrant
            ? `<br/><span style="opacity:.7">因子象限（相对口径） ${QUADRANT_LABEL[it.factor_quadrant]}</span>`
            : "";
        return (
          `<b>${it.name}</b>${quad}${fam}<br/>` +
          `价格 ${it.price_chg_pct!.toFixed(2)}% · 份额 ${it.share_chg_pct!.toFixed(2)}%<br/>` +
          `净流入 ${flow}${streak}${fquad}`
        );
      },
    },
  };
}
