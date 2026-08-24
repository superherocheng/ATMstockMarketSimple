import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EChartsChart } from "@/components/EChartsChart";
import { useCalendar, useLocator, useRotation, useThermometer } from "@/hooks/useApi";
import type {
  FamilyFlowIndex,
  PanicPayload,
} from "@/types";

const cssVar = (name: string, fallback: string): string =>
  typeof document !== "undefined"
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback;

const UP = () => cssVar("--up", "#ff4d4f");
const DOWN = () => cssVar("--down", "#52c41a");
const ACCENT = "#3b82f6";

const REGIME_TEXT: Record<string, string> = {
  dip_buying: "越跌越买（机构承接）",
  chasing: "追涨申购（动量）",
  neutral: "中性",
  unknown: "样本不足",
};

function fmt(v: number | null | undefined, digits = 1, suffix = ""): string {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(digits)}${suffix}`;
}

/** 0-100 百分位 → 温度色（低=蓝冷、高=红热） */
function heatColor(pct: number | null): string {
  if (pct == null) return "var(--muted)";
  if (pct <= 25) return "#3b82f6";
  if (pct <= 50) return "#0ea5e9";
  if (pct <= 75) return "#f59e0b";
  return "#dc2626";
}

/** 百分位横条（温度计样式） */
function PctBar({ pct, label }: { pct: number | null; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-14 shrink-0 text-muted-foreground">{label}</span>
      <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
        {pct != null && (
          <div
            className="absolute inset-y-0 left-0 rounded-full transition-all"
            style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: heatColor(pct) }}
          />
        )}
      </div>
      <span className="w-12 shrink-0 text-right font-mono">
        {pct == null ? "—" : `${pct.toFixed(0)}%`}
      </span>
    </div>
  );
}

// ── 仓位合成卡 ─────────────────────────────────────────────────────
function PositionCard({ data }: { data: ReturnType<typeof useThermometer>["data"] }) {
  const pos = data?.position;
  if (!pos) return null;
  const total = pos.suggested_pct;
  return (
    <Card>
      <CardHeader>
        <CardTitle>仓位合成 <span className="text-xs font-normal text-muted-foreground">波动为底 × 恐慌/估值修正（分解透明，非黑盒）</span></CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
          <div className="flex shrink-0 flex-col items-center">
            <div className="font-mono text-5xl font-bold" style={{ color: heatColor(100 - total) }}>
              {total.toFixed(0)}
              <span className="text-2xl">%</span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">建议权益仓位上限</div>
            <div className="mt-2 h-2.5 w-40 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full"
                style={{ width: `${total}%`, background: ACCENT }}
              />
            </div>
          </div>
          <div className="flex-1 space-y-2.5">
            {pos.decomposition.map((d) => (
              <div key={d.name} className="flex items-center gap-3 text-xs">
                <span className="w-36 shrink-0 truncate" title={d.name}>{d.name}</span>
                <span
                  className="w-14 shrink-0 text-right font-mono font-medium"
                  style={{
                    color:
                      d.value == null
                        ? "var(--muted-foreground)"
                        : d.value > 0
                          ? UP()
                          : d.value < 0
                            ? DOWN()
                            : "inherit",
                  }}
                >
                  {d.value == null ? "—" : `${d.value > 0 ? "+" : ""}${d.value}%`}
                </span>
                <span className="flex-1 truncate text-muted-foreground" title={d.note}>
                  {d.note}
                </span>
              </div>
            ))}
            <p className="pt-1 text-[11px] leading-relaxed text-muted-foreground">
              定位=仓位管理工具而非收益引擎：空仓部分计入货基收益后，回测总回报接近买入持有而最大回撤约减半。方向判断请勿依赖单一信号。
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── 估值卡 ─────────────────────────────────────────────────────────
function ValuationCard({ data }: { data: ReturnType<typeof useThermometer>["data"] }) {
  const indices = data?.valuation.indices ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>① 估值温度计 <span className="text-xs font-normal text-muted-foreground">PE/PB 历史百分位（长周期）</span></CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {indices.length === 0 && <p className="text-sm text-muted-foreground">估值数据加载中…</p>}
        {indices.map((i) => (
          <div key={i.code} className="space-y-1.5">
            <div className="flex items-baseline justify-between text-xs">
              <span className="font-medium">{i.name}</span>
              <span className="font-mono text-muted-foreground">
                PE {i.pe ?? "—"} · PB {i.pb ?? "—"}
                {i.days > 0 && <span className="ml-1 opacity-60">({i.days}日)</span>}
              </span>
            </div>
            <PctBar pct={i.pe_pct} label="PE分位" />
            <PctBar pct={i.pb_pct} label="PB分位" />
          </div>
        ))}
        {data?.valuation_median_pe_pct != null && (
          <p className="text-[11px] text-muted-foreground">
            PE 分位中位数 <b className="font-mono">{data.valuation_median_pe_pct}%</b>
            （≤20% 触发仓位合成+10%，≥80% 触发−10%）
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── 趋势状态卡 ─────────────────────────────────────────────────────
function TrendCard({ data }: { data: ReturnType<typeof useThermometer>["data"] }) {
  const indices = data?.trend.indices ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>② 趋势状态 <span className="text-xs font-normal text-muted-foreground">MA200 上/下 = 状态标签，非交易信号</span></CardTitle>
      </CardHeader>
      <CardContent>
        <table className="w-full text-xs">
          <thead className="text-muted-foreground">
            <tr className="border-b border-border">
              <th className="py-1.5 text-left font-normal">指数</th>
              <th className="py-1.5 text-right font-normal">vs MA200</th>
              <th className="py-1.5 text-right font-normal">距1年高</th>
              <th className="py-1.5 text-right font-normal">距1年低</th>
              <th className="py-1.5 text-right font-normal">状态</th>
            </tr>
          </thead>
          <tbody>
            {indices.map((i) => (
              <tr key={i.code} className="border-b border-border/50">
                <td className="py-1.5 font-medium">{i.name}</td>
                <td
                  className="py-1.5 text-right font-mono"
                  style={{ color: (i.vs_ma200_pct ?? 0) >= 0 ? UP() : DOWN() }}
                >
                  {fmt(i.vs_ma200_pct, 1, "%")}
                </td>
                <td className="py-1.5 text-right font-mono">{fmt(i.off_high_pct, 1, "%")}</td>
                <td className="py-1.5 text-right font-mono">{fmt(i.off_low_pct, 1, "%")}</td>
                <td className="py-1.5 text-right">
                  {i.state == null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <span
                      className="rounded px-1.5 py-0.5"
                      style={{
                        color: i.state === "above" ? UP() : DOWN(),
                        background: (i.state === "above" ? UP() : DOWN()) + "1f",
                      }}
                    >
                      {i.state === "above" ? "MA200上" : "MA200下"}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          回测提示：MA200 趋势过滤 2019 年后样本外失效（宽幅震荡反复打脸趋势线），只作状态分层参考。
        </p>
      </CardContent>
    </Card>
  );
}

// ── 恐慌卡 ─────────────────────────────────────────────────────────
function PanicSub({ p, highlight }: { p: PanicPayload; highlight?: boolean }) {
  const cur = p.current;
  const triggered = cur.triggered;
  return (
    <div className={highlight ? "" : "rounded-lg border border-border p-3"}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">{p.name}</span>
        <span
          className="rounded px-1.5 py-0.5 text-[11px]"
          style={{
            color: triggered ? "#16a34a" : "var(--muted-foreground)",
            background: triggered ? "#16a34a1f" : "transparent",
          }}
        >
          {triggered ? "● 恐慌触发区" : "未触发"}
        </span>
      </div>
      <div className="mt-1.5 grid grid-cols-2 gap-x-4 font-mono text-[11px] text-muted-foreground">
        <span>5日累计 {fmt(cur.ret_5d, 2, "%")}</span>
        <span>量能z {cur.amount_z == null ? "—" : cur.amount_z.toFixed(2)}</span>
      </div>
      <div className="mt-1.5 font-mono text-[11px]">
        <span className="text-muted-foreground">历史事件 n={p.stats.n}：</span>
        {(["5d", "10d", "20d"] as const).map((h) => (
          <span key={h} className="ml-2">
            <span className="text-muted-foreground">{h}</span>{" "}
            <span style={{ color: (p.stats[`mean_${h}`] ?? 0) >= 0 ? UP() : DOWN() }}>
              {fmt(p.stats[`mean_${h}`], 2, "%")}
            </span>
            <span className="text-muted-foreground">/{p.stats[`win_${h}`] ?? "—"}%</span>
          </span>
        ))}
      </div>
      {p.recent_events.length > 0 && (
        <div className="mt-2 space-y-0.5 font-mono text-[10px] text-muted-foreground">
          {p.recent_events.slice(-3).map((e) => (
            <div key={e.date} className="flex gap-3">
              <span>{e.date}</span>
              <span style={{ color: (e.fwd_10d ?? 0) >= 0 ? UP() : DOWN() }}>
                +10日 {fmt(e.fwd_10d, 1, "%")}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PanicCard({ data }: { data: ReturnType<typeof useThermometer>["data"] }) {
  const market = data?.panic.market;
  return (
    <Card>
      <CardHeader>
        <CardTitle>③ 恐慌仪表 <span className="text-xs font-normal text-muted-foreground">5日跌≥5%且放量 → 历史前瞻均值/胜率</span></CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!market && <p className="text-sm text-muted-foreground">加载中…</p>}
        {market && <PanicSub p={market} highlight />}
        {(data?.panic.high_beta ?? []).map((p) => (
          <PanicSub key={p.code} p={p} />
        ))}
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          唯一样本外稳健的方法族：事件后 5-10 日反转（20年9只宽基，n=85 市场级episode，5日超额+1.4%/胜率60%）；反弹弹性集中在高β品种。
        </p>
      </CardContent>
    </Card>
  );
}

// ── 波动卡 ─────────────────────────────────────────────────────────
function VolatilityCard({ data }: { data: ReturnType<typeof useThermometer>["data"] }) {
  const v = data?.volatility;
  const option = useMemo(() => {
    if (!v?.series?.length) return {};
    return {
      grid: { left: 44, right: 12, top: 10, bottom: 24 },
      xAxis: {
        type: "category",
        data: v.series.map((s) => s.date.slice(4)),
        axisLabel: { fontSize: 9, interval: 40 },
      },
      yAxis: { type: "value", axisLabel: { fontSize: 9, formatter: "{value}%" } },
      series: [
        {
          type: "line",
          data: v.series.map((s) => s.vol),
          showSymbol: false,
          lineStyle: { width: 1.4, color: ACCENT },
          areaStyle: { opacity: 0.08 },
        },
      ],
      tooltip: {
        trigger: "axis",
        formatter: (ps: unknown) => {
          const a = ps as { name?: string; value?: number }[];
          return a.length ? `${a[0].name}<br/>年化波动 ${a[0].value?.toFixed(1)}%` : "";
        },
      },
    };
  }, [v]);
  return (
    <Card>
      <CardHeader>
        <CardTitle>④ 波动状态 <span className="text-xs font-normal text-muted-foreground">量能/波动可预测，方向不可</span></CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-3 grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="font-mono text-xl font-bold">{v?.vol_20d ?? "—"}<span className="text-xs">%</span></div>
            <div className="text-[10px] text-muted-foreground">20日年化波动</div>
          </div>
          <div>
            <div className="font-mono text-xl font-bold" style={{ color: heatColor(v?.vol_pct ?? null) }}>
              {v?.vol_pct == null ? "—" : `${v.vol_pct.toFixed(0)}%`}
            </div>
            <div className="text-[10px] text-muted-foreground">历史百分位</div>
          </div>
          <div>
            <div className="font-mono text-xl font-bold" style={{ color: ACCENT }}>
              {v?.target_mult == null ? "—" : `${(v.target_mult * 100).toFixed(0)}%`}
            </div>
            <div className="text-[10px] text-muted-foreground">仓位乘数 (目标12%)</div>
          </div>
        </div>
        <EChartsChart option={option} height={160} />
      </CardContent>
    </Card>
  );
}

// ── 家族份额流卡 ───────────────────────────────────────────────────
function FamilyFlowCard({ data }: { data: ReturnType<typeof useThermometer>["data"] }) {
  const indices = data?.family_flow.indices ?? [];
  const [sel, setSel] = useState<string>("");
  const cur: FamilyFlowIndex | undefined =
    indices.find((i) => i.code === sel) ?? indices[0];
  const option = useMemo(() => {
    if (!cur?.series?.length) return {};
    const s = cur.series;
    return {
      grid: { left: 56, right: 56, top: 14, bottom: 24 },
      xAxis: {
        type: "category",
        data: s.map((x) => x.date.slice(4)),
        axisLabel: { fontSize: 9, interval: 20 },
      },
      yAxis: [
        { type: "value", name: "家族份额(亿份)", nameTextStyle: { fontSize: 9 }, axisLabel: { fontSize: 9, formatter: (v: number) => (v / 1e4).toFixed(0) }, scale: true },
        { type: "value", name: "价格", nameTextStyle: { fontSize: 9 }, axisLabel: { fontSize: 9 }, scale: true, splitLine: { show: false } },
      ],
      series: [
        {
          name: "家族份额",
          type: "line",
          yAxisIndex: 0,
          data: s.map((x) => x.share),
          showSymbol: false,
          lineStyle: { width: 1.6, color: ACCENT },
          areaStyle: { opacity: 0.06 },
        },
        {
          name: "价格",
          type: "line",
          yAxisIndex: 1,
          data: s.map((x) => x.close),
          showSymbol: false,
          lineStyle: { width: 1.2, color: cssVar("--foreground", "#888"), opacity: 0.7 },
        },
      ],
      tooltip: { trigger: "axis" },
    };
  }, [cur]);
  if (indices.length === 0) return null;
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>⑤ 家族份额流 <span className="text-xs font-normal text-muted-foreground">同指数全部ETF加总（剔除工具轮动）</span></CardTitle>
          {cur && (
            <p className="mt-1 text-xs text-muted-foreground">
              20日份额 {fmt(cur.chg_20d_pct, 1, "%")} · 60日滚动相关{" "}
              <span className="font-mono" style={{ color: (cur.corr_60d ?? 0) < 0 ? DOWN() : UP() }}>
                {cur.corr_60d == null ? "—" : cur.corr_60d.toFixed(2)}
              </span>{" "}
              → {REGIME_TEXT[cur.regime]}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {indices.map((i) => (
            <Button
              key={i.code}
              size="sm"
              variant={cur?.code === i.code ? "default" : "ghost"}
              className="h-7 px-2 text-xs"
              onClick={() => setSel(i.code)}
            >
              {i.name.replace("ETF", "")}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <EChartsChart option={option} height={200} />
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          相关为负=份额与价格反向（机构/配置盘承接，regime 历史上底部特征）；翻正=追涨申购。单只ETF份额被同指数内申赎搬家污染，必须看家族口径。
        </p>
      </CardContent>
    </Card>
  );
}

// ── 轮动矩阵卡 ─────────────────────────────────────────────────────
function RotationCard() {
  const { data } = useRotation();
  const m = data?.regime_matrix;
  const rotLabels: Record<string, string> = {
    weak: "轮动弱(主线清晰)",
    mid: "轮动中",
    strong: "轮动强(主线不清)",
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          轮动仪表 · 情绪×轮动强度
          {data?.sentiment && (
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              情绪 {data.sentiment.regime_label}（{data.sentiment.score >= 0 ? "+" : ""}
              {data.sentiment.score.toFixed(2)}） · {data.rotation.level_label}（百分位{" "}
              {data.rotation.strength_pct?.toFixed(0)}%）
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {data?.data_incomplete || !m ? (
          <p className="text-sm text-muted-foreground">
            {data?.data_incomplete ? "因子数据覆盖不足（等待数据更新后自动恢复）。" : "加载中…"}
          </p>
        ) : (
          <div className="space-y-3">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-xs">
                <thead>
                  <tr className="text-muted-foreground">
                    <th className="py-1 text-left font-normal">情绪＼轮动</th>
                    {m.rotation_order.map((r) => (
                      <th key={r} className="py-1 text-center font-normal">{rotLabels[r] ?? r}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {m.rows.map((row) => (
                    <tr key={row.sentiment}>
                      <td className="py-1 pr-2 text-muted-foreground">{row.label}</td>
                      {row.cells.map((c) => (
                        <td key={c.rotation} className="p-1">
                          <div
                            className={`rounded px-2 py-1.5 text-center ${c.current ? "ring-2 ring-offset-1 ring-offset-card" : ""}`}
                            style={{
                              background: c.current ? ACCENT + "26" : "var(--muted)",
                              borderColor: c.current ? ACCENT : "transparent",
                            }}
                          >
                            <div className="font-mono font-bold">{(c.position * 100).toFixed(0)}%</div>
                            <div className="text-[10px] text-muted-foreground">{c.action}</div>
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              当前格 [{m.current_cell.join(" × ")}] → 建议总仓位{" "}
              <b className="font-mono">{(m.recommended_position * 100).toFixed(0)}%</b>（{m.level}）：{m.action}
            </p>
            {(data.narrative ?? []).map((n, i) => (
              <p key={i} className="text-[11px] text-muted-foreground">· {n}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── 底部定位卡 ─────────────────────────────────────────────────────
function LocatorCard() {
  const { data } = useLocator();
  const indices = data?.indices ?? [];
  const [sel, setSel] = useState("");
  const cur = indices.find((i) => i.code === sel) ?? indices[0];
  const option = useMemo(() => {
    if (!cur?.series?.length) return {};
    const dd = cur.series.map((s) => s.drawdown);
    const shareMap = new Map(cur.share_series.map((s) => [s.date, s.chg20_pct]));
    return {
      grid: { left: 44, right: 44, top: 14, bottom: 24 },
      xAxis: {
        type: "category",
        data: cur.series.map((s) => s.date.slice(2)),
        axisLabel: { fontSize: 9, interval: 60 },
      },
      yAxis: [
        { type: "value", axisLabel: { fontSize: 9, formatter: "{value}%" }, max: 0 },
        { type: "value", axisLabel: { fontSize: 9, formatter: "{value}%" }, splitLine: { show: false } },
      ],
      series: [
        {
          name: "回撤",
          type: "line",
          data: dd,
          showSymbol: false,
          lineStyle: { width: 1.4, color: DOWN() },
          areaStyle: { opacity: 0.08 },
          markLine: {
            silent: true,
            symbol: "none",
            label: { fontSize: 9, formatter: "-20%" },
            lineStyle: { type: "dashed", opacity: 0.6 },
            data: [{ yAxis: -20 }],
          },
        },
        {
          name: "家族20日份额%",
          type: "line",
          yAxisIndex: 1,
          data: cur.series.map((s) => shareMap.get(s.date) ?? null),
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1, color: ACCENT, opacity: 0.8 },
        },
      ],
      tooltip: { trigger: "axis" },
    };
  }, [cur]);
  if (indices.length === 0) return null;
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>底部定位器 <span className="text-xs font-normal text-muted-foreground">深跌≥20% × 家族份额逆势流入</span></CardTitle>
          {cur && (
            <p className="mt-1 text-xs text-muted-foreground">
              当前回撤 <span className="font-mono">{fmt(cur.current.drawdown_pct, 1, "%")}</span> ·
              家族20日份额 {fmt(cur.current.share_20d_pct, 1, "%")} ·{" "}
              {cur.current.active ? (
                <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-emerald-600">● 底部区域信号激活</span>
              ) : (
                <span>未激活</span>
              )}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {indices.map((i) => (
            <Button
              key={i.code}
              size="sm"
              variant={cur?.code === i.code ? "default" : "ghost"}
              className="h-7 px-2 text-xs"
              onClick={() => setSel(i.code)}
            >
              {i.name.replace("ETF", "")}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <EChartsChart option={option} height={200} />
        {cur && cur.events.length > 0 && (
          <div className="mt-2 space-y-0.5 font-mono text-[10px] text-muted-foreground">
            {cur.events.slice(-4).reverse().map((e) => (
              <div key={e.date} className="flex gap-3">
                <span>{e.date}</span>
                <span>回撤 {e.drawdown.toFixed(0)}%</span>
                <span>份额20日 {fmt(e.share_20d_pct, 1, "%")}</span>
                <span style={{ color: (e.fwd_60d_pct ?? 0) >= 0 ? UP() : DOWN() }}>
                  后60日 {fmt(e.fwd_60d_pct, 1, "%")}
                </span>
              </div>
            ))}
          </div>
        )}
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          区域定位器而非精确择时：历史触发（2018Q4 / 2024初 / 2025-04）方向全对，但作为持续策略不可行（时点偏早）。
        </p>
      </CardContent>
    </Card>
  );
}

// ── 日历热力卡 ─────────────────────────────────────────────────────
function CalendarCard() {
  const { data } = useCalendar();
  const rows = useMemo(
    () => (data?.rows ?? []).filter((r) => r.type === "index" || r.n_months >= 24).slice(0, 24),
    [data],
  );
  const option = useMemo(() => {
    if (!rows.length) return {};
    const up = UP();
    const down = DOWN();
    const cellData: Array<[number, number, number | null]> = [];
    rows.forEach((r, yi) => {
      r.months.forEach((v, mi) => cellData.push([mi, yi, v]));
    });
    const vals = cellData.map((c) => c[2]).filter((v): v is number => v != null);
    const absMax = Math.max(...vals.map(Math.abs), 1);
    return {
      grid: { left: 76, right: 16, top: 10, bottom: 56 },
      xAxis: {
        type: "category",
        data: Array.from({ length: 12 }, (_, i) => `${i + 1}月`),
        axisLabel: { fontSize: 9 },
      },
      yAxis: {
        type: "category",
        data: rows.map((r) => r.name),
        axisLabel: { fontSize: 9 },
      },
      series: [
        {
          type: "heatmap",
          data: cellData,
          label: { show: false },
        },
      ],
      visualMap: {
        min: -absMax,
        max: absMax,
        calculable: false,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        itemWidth: 10,
        itemHeight: 90,
        textStyle: { fontSize: 9 },
        inRange: { color: [down, "#e5e7eb", up] },
      },
      tooltip: {
        trigger: "item",
        formatter: (p: { data?: [number, number, number | null] }) =>
          p.data ? `${rows[p.data[1]].name} ${p.data[0] + 1}月：${p.data[2] == null ? "—" : fmt(p.data[2], 2, "%")}` : "",
      },
    };
  }, [rows]);
  return (
    <Card>
      <CardHeader>
        <CardTitle>日历效应 <span className="text-xs font-normal text-muted-foreground">月度平均收益（历史，红=正）</span></CardTitle>
      </CardHeader>
      <CardContent>
        {!rows.length ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : (
          <>
            <EChartsChart option={option} height={Math.max(240, rows.length * 22 + 80)} />
            <div className="mt-1 space-y-0.5">
              {(data?.notes ?? []).map((n, i) => (
                <p key={i} className="text-[11px] text-muted-foreground">
                  · {n.month}月【{n.tag}】{n.note}
                </p>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── 页面 ───────────────────────────────────────────────────────────
export default function Timing() {
  const thermo = useThermometer();
  const date = thermo.data?.date;
  const dateDisplay =
    date && date.length === 8 ? `${date.slice(4, 6)}-${date.slice(6, 8)}` : null;

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold">择时仪表盘</h1>
        <p className="text-sm text-muted-foreground">
          大盘温度计 · 仓位合成 · 轮动矩阵 · 底部定位 · 日历效应
          {dateDisplay ? ` · 数据 ${dateDisplay}` : ""}
          <span className="ml-2 text-xs">（不做方向预测，只做状态分层与仓位管理）</span>
        </p>
      </div>

      {thermo.isError && (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            温度计数据加载失败，请稍后重试。
          </CardContent>
        </Card>
      )}

      <PositionCard data={thermo.data} />

      <div className="grid gap-6 lg:grid-cols-3">
        <ValuationCard data={thermo.data} />
        <TrendCard data={thermo.data} />
        <PanicCard data={thermo.data} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <VolatilityCard data={thermo.data} />
        <FamilyFlowCard data={thermo.data} />
      </div>

      <RotationCard />

      <div className="grid gap-6 lg:grid-cols-2">
        <LocatorCard />
        <CalendarCard />
      </div>
    </main>
  );
}
