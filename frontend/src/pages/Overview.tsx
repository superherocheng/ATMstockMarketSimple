import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EChartsChart } from "@/components/EChartsChart";
import {
  DivergenceScatter,
  DivTag,
  RISK_COLOR,
  LURK_COLOR,
} from "@/components/DivergenceScatter";
import {
  useDivergence,
  useFetchStatus,
  useHeatmap,
  useOverview,
  useTriggerFetch,
} from "@/hooks/useApi";
import type { DivergenceItem, OverviewBar } from "@/types";

const DIV_WINDOWS = [5, 10, 20, 60] as const;

const QUADRANT_LABEL: Record<number, string> = {
  1: "强势",
  2: "潜伏",
  3: "撤离",
  4: "风险",
};

// ECharts can't read CSS variables directly (same helper as other chart pages).
const cssVar = (name: string, fallback: string): string =>
  typeof document !== "undefined"
    ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    : fallback;

function Pct({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  const cls = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted-foreground";
  return (
    <span className={cls}>
      {value > 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

function fmtQty(v: number | null | undefined): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "+";
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(0) + "万";
  return sign + abs.toFixed(0);
}

// 单元格内嵌红绿条：10日份额变化的量级一眼可比
function MiniBar({ v, max }: { v: number | null; max: number }) {
  if (v == null || max <= 0) return <div className="h-1" />;
  const w = Math.min(100, (Math.abs(v) / max) * 100);
  return (
    <div className="mt-1 h-1 w-full max-w-24 overflow-hidden rounded bg-muted">
      <div className={`h-full ${v >= 0 ? "bg-up" : "bg-down"}`} style={{ width: `${w}%` }} />
    </div>
  );
}

function EtfTable({
  rows,
  title,
  divByCode,
}: {
  rows?: OverviewBar[];
  title: string;
  divByCode: Map<string, DivergenceItem>;
}) {
  const sorted = useMemo(() => {
    return [...(rows ?? [])].sort((a, b) => {
      const pa = a.share_change_10d_qty ?? -Infinity;
      const pb = b.share_change_10d_qty ?? -Infinity;
      return pb - pa;
    });
  }, [rows]);
  const maxAbs10d = useMemo(
    () => Math.max(...sorted.map((r) => Math.abs(r.share_change_10d_qty ?? 0)), 0),
    [sorted],
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title} <span className="text-xs font-normal text-muted-foreground">按10日变化比例降序</span></CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead className="text-right">当日份额变化</TableHead>
              <TableHead className="text-right">10日份额变化</TableHead>
              <TableHead className="text-right">当日变化比例</TableHead>
              <TableHead>10日信号</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((r) => {
              const div = divByCode.get(r.ts_code);
              return (
                <TableRow key={r.ts_code}>
                  <TableCell className="font-medium">
                    <Link to={`/etf?code=${r.ts_code}`} className="hover:underline">
                      {r.name}
                    </Link>
                    {div?.quadrant != null && (
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        {QUADRANT_LABEL[div.quadrant]}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    <span className={r.share_change_qty != null ? (r.share_change_qty >= 0 ? "text-up" : "text-down") : ""}>
                      {fmtQty(r.share_change_qty)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    <div className="flex flex-col items-end">
                      <span className={r.share_change_10d_qty != null ? (r.share_change_10d_qty >= 0 ? "text-up" : "text-down") : ""}>
                        {fmtQty(r.share_change_10d_qty)}
                      </span>
                      <MiniBar v={r.share_change_10d_qty} max={maxAbs10d} />
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    <Pct value={r.share_change_pct} />
                  </TableCell>
                  <TableCell>
                    <DivTag it={div} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

/** 行业热度 treemap：面积=最新成交额、颜色=当日涨跌、点击跳详情。 */
function HeatmapTreemap({ data }: { data: { name: string; ts_code: string; pct_chg: number; amount: number | null }[] }) {
  const navigate = useNavigate();
  const option = useMemo(() => {
    if (!data.length) return {};
    const up = cssVar("--up", "#ff4d4f");
    const down = cssVar("--down", "#52c41a");
    const mid = "rgba(120,113,108,0.35)";
    return {
      tooltip: {
        formatter: (p: { name?: string; value?: number[] }) =>
          `<b>${p.name ?? ""}</b> ${p.value && p.value[1] >= 0 ? "+" : ""}${p.value ? p.value[1].toFixed(2) : "—"}%` +
          `<br/>成交 ${p.value ? (p.value[0] / 1e5).toFixed(1) : "—"}亿`,
      },
      visualMap: {
        type: "continuous",
        show: false,
        min: -3,
        max: 3,
        dimension: 1,
        inRange: { color: [down, mid, up] },
      },
      series: [
        {
          type: "treemap",
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          itemStyle: { borderColor: "rgba(128,128,128,0.5)", borderWidth: 1, gapWidth: 2 },
          label: {
            show: true,
            fontSize: 11,
            formatter: (p: { name?: string; value?: number[] }) =>
              `${p.name ?? ""}\n${p.value && p.value[1] >= 0 ? "+" : ""}${p.value ? p.value[1].toFixed(1) : "—"}%`,
          },
          // value=[面积(成交额千元), 颜色(涨跌%)]；无成交额时退化为等面积(1)
          data: data.map((h) => ({
            name: h.name,
            ts_code: h.ts_code,
            value: [Math.max(h.amount ?? 0, 1), h.pct_chg],
          })),
        },
      ],
    };
  }, [data]);

  if (!data.length) return null;
  return (
    <EChartsChart
      option={option}
      height={320}
      onEvents={{
        click: (p) => {
          const d = p.data as { ts_code?: string } | undefined;
          if (d?.ts_code) navigate(`/etf?code=${d.ts_code}`);
        },
      }}
    />
  );
}

/** 价格×份额背离面板：全市场散点象限 + rank-gap 排行。 */
function DivergencePanel() {
  const [win, setWin] = useState<number>(10);
  const navigate = useNavigate();
  const divergence = useDivergence(win);

  const items = divergence.data?.items ?? [];
  const valid = items.filter((i) => i.price_chg_pct != null && i.share_chg_pct != null);
  const top = valid.slice(0, 8);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>价格 × 份额背离</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            <span style={{ color: RISK_COLOR }}>右下=价涨份额缩</span> ·{" "}
            <span style={{ color: LURK_COLOR }}>左上=价跌份额增</span> · 气泡=成交额 · 点击查看详情
          </p>
        </div>
        <div className="flex gap-1">
          {DIV_WINDOWS.map((w) => (
            <Button
              key={w}
              size="sm"
              variant={w === win ? "default" : "ghost"}
              className="h-7 px-2 text-xs"
              onClick={() => setWin(w)}
            >
              {w}日
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {divergence.isError ? (
          <p className="py-8 text-center text-sm text-destructive">背离数据加载失败</p>
        ) : valid.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">加载中…</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <DivergenceScatter items={items} height={320} onPick={(c) => navigate(`/etf?code=${c}`)} />
            </div>
            <div className="lg:col-span-2">
              <div className="mb-2 text-xs text-muted-foreground">背离强度榜（价格排名与份额排名差距最大）</div>
              <div className="space-y-1.5">
                {top.map((it) => (
                  <Link
                    key={it.ts_code}
                    to={`/etf?code=${it.ts_code}`}
                    className="flex items-center gap-2 rounded border border-border px-2 py-1.5 text-sm transition-colors hover:bg-accent"
                  >
                    <span className="min-w-0 flex-1 truncate">{it.name}</span>
                    <span className="w-14 text-right tabular-nums">
                      <Pct value={it.price_chg_pct} />
                    </span>
                    <span className="w-14 text-right tabular-nums">
                      <Pct value={it.share_chg_pct} />
                    </span>
                    <DivTag it={it} />
                    <span className="w-8 text-right font-mono text-xs text-muted-foreground">
                      Δ{it.rank_gap}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function Overview() {
  const overview = useOverview();
  const heatmap = useHeatmap();
  const status = useFetchStatus();
  const trigger = useTriggerFetch();

  // index_etf + sector_summary 的表格共用同一份 10 日背离数据
  const divergence = useDivergence(10);
  const divByCode = useMemo(
    () => new Map((divergence.data?.items ?? []).map((i) => [i.ts_code, i])),
    [divergence.data],
  );

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">概览</h1>
          <p className="text-sm text-muted-foreground">A股 ETF 量化监控</p>
        </div>
        <Button
          onClick={() => trigger.mutate("all")}
          disabled={trigger.isPending || !!status.data?.running}
        >
          {status.data?.running ? `刷新中 ${status.data.progress}%` : "刷新数据"}
        </Button>
      </div>

      {status.data?.running && (
        <Card>
          <CardContent className="space-y-1 py-3">
            <div className="text-sm">{status.data.current_step || "处理中…"}</div>
            {status.data.log.slice(-1).map((l, i) => (
              <div key={i} className="font-mono text-xs text-muted-foreground">
                {l}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {heatmap.data && heatmap.data.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>行业热度 <span className="text-xs font-normal text-muted-foreground">面积=成交额 · 颜色=当日涨跌 · 点击查看详情</span></CardTitle>
          </CardHeader>
          <CardContent>
            <HeatmapTreemap data={heatmap.data} />
          </CardContent>
        </Card>
      )}

      <DivergencePanel />

      {overview.data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <EtfTable rows={overview.data.index_etf} title="宽基 ETF" divByCode={divByCode} />
          <EtfTable rows={overview.data.sector_summary} title="行业 ETF" divByCode={divByCode} />
        </div>
      )}

      {(overview.isError || trigger.isError) && (
        <p className="text-sm text-destructive">
          {trigger.isError ? "刷新失败，请稍后重试。" : "数据加载失败，请稍后重试。"}
        </p>
      )}
    </main>
  );
}
