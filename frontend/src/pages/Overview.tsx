import { useMemo } from "react";
import { Link } from "react-router-dom";
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
import { useFetchStatus, useHeatmap, useOverview, useTriggerFetch } from "@/hooks/useApi";
import type { OverviewBar } from "@/types";

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

function EtfTable({ rows, title }: { rows?: OverviewBar[]; title: string }) {
  const sorted = useMemo(() => {
    return [...(rows ?? [])].sort((a, b) => {
      const pa = a.share_change_10d_qty ?? -Infinity;
      const pb = b.share_change_10d_qty ?? -Infinity;
      return pb - pa;
    });
  }, [rows]);
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((r) => (
              <TableRow key={r.ts_code}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-right tabular-nums">
                  <span className={r.share_change_qty != null ? (r.share_change_qty >= 0 ? "text-up" : "text-down") : ""}>
                    {fmtQty(r.share_change_qty)}
                  </span>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <span className={r.share_change_10d_qty != null ? (r.share_change_10d_qty >= 0 ? "text-up" : "text-down") : ""}>
                    {fmtQty(r.share_change_10d_qty)}
                  </span>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <Pct value={r.share_change_pct} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export default function Overview() {
  const overview = useOverview();
  const heatmap = useHeatmap();
  const status = useFetchStatus();
  const trigger = useTriggerFetch();

  const sortedHeatmap = useMemo(() => {
    if (!heatmap.data) return [];
    return [...heatmap.data].sort((a, b) => b.pct_chg - a.pct_chg);
  }, [heatmap.data]);

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

      {sortedHeatmap.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>行业热度（当日涨跌 · 降序）</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {sortedHeatmap.map((h) => (
              <Link
                key={h.ts_code}
                to={`/etf?code=${h.ts_code}`}
                className={`inline-block rounded border border-border px-2 py-1 text-xs transition-colors hover:bg-accent ${
                  h.pct_chg >= 0 ? "text-up" : "text-down"
                }`}
              >
                {h.name} {h.pct_chg >= 0 ? "+" : ""}
                {h.pct_chg.toFixed(2)}%
              </Link>
            ))}
          </CardContent>
        </Card>
      )}

      {overview.data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <EtfTable rows={overview.data.index_etf} title="宽基 ETF" />
          <EtfTable rows={overview.data.sector_summary} title="行业 ETF" />
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
