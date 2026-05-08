import { useState } from 'react';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { AdaptiveChart } from '@/components/ui/AdaptiveChart';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { StatCard } from '@/components/ui/StatCard';
import { useStockDetail } from '@/api/hooks';
import { formatNum, pctText, pctColor } from '@/lib/utils';
import { chartTheme } from '@/lib/chart-theme';

export default function StockDetailPage() {
  const [code, setCode] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const { data, isLoading, isError, refetch } = useStockDetail(code);

  const handleSearch = () => {
    if (searchInput.trim()) {
      setCode(searchInput.trim().toUpperCase());
    }
  };

  const kline = (data as { kline?: Array<Record<string, unknown>> } | undefined)?.kline || [];

  function buildKlineOption() {
    if (kline.length === 0) return {};
    const dates = kline.map((k) => String(k.trade_date));
    const ohlc = kline.map((k) => [Number(k.open), Number(k.close), Number(k.low), Number(k.high)]);

    return {
      backgroundColor: 'transparent',
      textStyle: chartTheme.textStyle,
      title: { text: 'K线走势', left: '3%', textStyle: { fontSize: 14, fontWeight: 600 } },
      tooltip: { backgroundColor: chartTheme.tooltip.backgroundColor, textStyle: chartTheme.tooltip.textStyle },
      grid: { left: '8%', right: '3%', top: '12%', bottom: '12%' },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
      yAxis: { scale: true, axisLabel: { fontSize: 10 } },
      dataZoom: [
        { type: 'inside', start: 60, end: 100 },
        { show: true, type: 'slider', bottom: '2%', start: 60, end: 100 },
      ],
      series: [{
        type: 'candlestick', data: ohlc,
        itemStyle: { color: chartTheme.upColor, color0: chartTheme.downColor, borderColor: chartTheme.upColor, borderColor0: chartTheme.downColor },
      }],
    };
  }

  const info = data as Record<string, unknown> | undefined;
  const lastKline = kline[kline.length - 1];
  const lastPct = lastKline ? Number(lastKline.pct_chg || 0) : 0;

  return (
    <ErrorBoundary>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">个股查询</h2>

        {/* Search */}
        <div className="flex gap-2">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="输入股票代码或名称搜索..."
            className="flex-1 px-4 py-3 rounded-xl border border-[var(--c-border)] bg-white text-sm min-h-[44px] focus:outline-none focus:border-[var(--c-accent)]"
            aria-label="股票搜索"
          />
          <button
            onClick={handleSearch}
            className="px-6 py-3 rounded-xl bg-[var(--c-accent)] text-white font-medium text-sm touch-ripple min-h-[44px]"
          >
            查询
          </button>
        </div>

        {!code ? (
          <EmptyState title="输入股票代码开始查询" description="支持代码（如 000001.SZ）或名称搜索" />
        ) : isError ? (
          <EmptyState title="查询失败" description="请检查股票代码是否正确" action={<button onClick={() => refetch()} className="px-4 py-2 rounded-lg bg-[var(--c-accent)] text-white text-sm">重试</button>} />
        ) : isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-80" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="最新价" value={formatNum(lastKline?.close as number)} trend={lastPct > 0 ? 'up' : lastPct < 0 ? 'down' : 'neutral'} />
              <StatCard label="涨跌幅" value={pctText(lastPct)} trend={lastPct > 0 ? 'up' : lastPct < 0 ? 'down' : 'neutral'} />
              <StatCard label="成交量" value={formatNum(lastKline?.vol as number, 0)} />
              <StatCard label={String(info?.name || '')} value={code} />
            </div>
            <div className="glass rounded-xl p-4 sm:p-5">
              <AdaptiveChart option={buildKlineOption()} height={{ mobile: 280, tablet: 380, desktop: 450 }} />
            </div>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
}
