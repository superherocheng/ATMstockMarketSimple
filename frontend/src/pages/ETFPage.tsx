import { useState } from 'react';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { AdaptiveChart } from '@/components/ui/AdaptiveChart';
import { useETFDetail, useSectorDetail, useSectorCards, type ETFDetailData } from '@/api/hooks';
import { formatNum, pctText, pctColor, fmtDate } from '@/lib/utils';
import { chartTheme } from '@/lib/chart-theme';

const INDEX_ETF_TABS = [
  { code: '510300.SH', label: '沪深300ETF' },
  { code: '510500.SH', label: '中证500ETF' },
  { code: '510050.SH', label: '上证50ETF' },
];

export default function ETFPage() {
  const [mode, setMode] = useState<'index' | 'sector'>('index');
  const [activeCode, setActiveCode] = useState('510300.SH');
  const { data: sectorCards, isLoading: scLoading } = useSectorCards();

  const queryCode = mode === 'sector' ? activeCode : activeCode;
  const isIndexCode = INDEX_ETF_TABS.some((t) => t.code === queryCode);
  const { data, isLoading, isError, refetch } = isIndexCode
    ? useETFDetail(queryCode)
    : useSectorDetail(queryCode);

  if (isError) {
    return (
      <ErrorBoundary>
        <EmptyState
          title="数据加载失败"
          description="请检查网络连接或返回重试"
          action={
            <button onClick={() => refetch()} className="px-4 py-2 rounded-lg bg-[var(--c-accent)] text-white text-sm">
              重试
            </button>
          }
        />
      </ErrorBoundary>
    );
  }

  const kline = data?.kline || [];
  const shares = data?.shares || [];
  const anomalies = data?.anomalies || { price: [], share: [] };

  // ── Build Candlestick + Volume Percentile option ──
  function buildKlineOption() {
    if (kline.length === 0) return {};
    const dates = kline.map((k) => k.trade_date);
    const ohlc = kline.map((k) => [k.open, k.close, k.low, k.high]);
    const volumes = kline.map((k) => k.vol);
    const sortedVols = [...volumes].sort((a, b) => a - b);
    const volPercentiles = volumes.map((v) => {
      const rank = sortedVols.filter((x) => x <= v).length;
      return Math.round((rank / sortedVols.length) * 100);
    });
    const pcts = kline.map((k) => k.pct_chg);
    const anomalyDates = new Set((anomalies.price || []).map((a) => a.trade_date));
    const markPoints = kline
      .filter((k) => anomalyDates.has(k.trade_date))
      .map((k) => ({
        name: `${k.trade_date} ${pctText(k.pct_chg)}`,
        coord: [k.trade_date, k.high],
        symbolSize: 8,
        itemStyle: { color: chartTheme.upColor },
      }));

    return {
      backgroundColor: 'transparent',
      textStyle: chartTheme.textStyle,
      title: { text: 'K线走势', left: '3%', top: '2%', textStyle: { color: '#2C2C2C', fontWeight: 600, fontSize: 14 } },
      tooltip: {
        backgroundColor: chartTheme.tooltip.backgroundColor,
        borderColor: chartTheme.tooltip.borderColor,
        textStyle: chartTheme.tooltip.textStyle,
        formatter: (params: Array<{ axisValue: string; marker: string; seriesName: string; value: number | number[] }>) => {
          let result = `<b>${params[0].axisValue}</b><br/>`;
          params.forEach((p) => {
            if (Array.isArray(p.value)) {
              result += `${p.marker} 开:${p.value[1]?.toFixed(2)} 收:${p.value[2]?.toFixed(2)} 低:${p.value[3]?.toFixed(2)} 高:${p.value[4]?.toFixed(2)}<br/>`;
            } else {
              result += `${p.marker} ${p.seriesName}: ${p.value}%<br/>`;
            }
          });
          return result;
        },
      },
      legend: { data: ['K线', '成交量百分位'], textStyle: chartTheme.legend.textStyle, top: '2%', right: '3%' },
      grid: [
        { left: '8%', right: '3%', top: '12%', height: '50%' },
        { left: '8%', right: '3%', top: '68%', height: '20%' },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, axisLabel: { fontSize: 10 }, boundaryGap: true },
        { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false }, boundaryGap: true },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, axisLabel: { fontSize: 10 } },
        { scale: true, gridIndex: 1, axisLabel: { fontSize: 10, formatter: '{value}%' }, min: 0, max: 100 },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
        { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: '2%', start: 60, end: 100 },
      ],
      series: [
        {
          name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
          itemStyle: { color: chartTheme.upColor, color0: chartTheme.downColor, borderColor: chartTheme.upColor, borderColor0: chartTheme.downColor },
          markPoint: { data: markPoints, symbol: 'pin', symbolSize: 30, label: { show: false } },
        },
        {
          name: '成交量百分位', type: 'bar',
          data: volPercentiles.map((pct, i) => ({
            value: pct,
            itemStyle: { color: pcts[i] >= 0 ? chartTheme.upColor + '66' : chartTheme.downColor + '66' },
          })),
          xAxisIndex: 1, yAxisIndex: 1,
          label: { show: true, position: 'top', fontSize: 8, formatter: '{c}%' },
        },
      ],
    };
  }

  // ── Build Share Percentile Scatter option ──
  function buildSharesOption() {
    if (shares.length === 0) return {};
    const recent = shares.slice(-20);
    const dates = recent.map((s) => s.trade_date);
    const allValues = shares.map((s) => s.fd_share);
    const sortedAll = [...allValues].sort((a, b) => a - b);
    const toPercentile = (val: number) => {
      const rank = sortedAll.filter((v) => v <= val).length;
      return Math.round((rank / sortedAll.length) * 100);
    };
    const pctValues = recent.map((s) => toPercentile(s.fd_share));
    const anomalyDates = new Set((anomalies.share || []).map((a) => a.trade_date));
    const markPoints = recent
      .filter((s) => anomalyDates.has(s.trade_date))
      .map((s) => ({
        name: s.trade_date,
        coord: [s.trade_date, toPercentile(s.fd_share)],
        symbolSize: 8,
        itemStyle: { color: chartTheme.upColor },
      }));

    return {
      backgroundColor: 'transparent',
      textStyle: chartTheme.textStyle,
      tooltip: {
        trigger: 'axis',
        backgroundColor: chartTheme.tooltip.backgroundColor,
        borderColor: chartTheme.tooltip.borderColor,
        textStyle: chartTheme.tooltip.textStyle,
        formatter: (params: Array<{ dataIndex: number; value: number; axisValueLabel: string }>) => {
          const p = params[0];
          if (!p) return '';
          const idx = p.dataIndex;
          const rawVal = recent[idx]?.fd_share || 0;
          return `<b>${p.axisValueLabel}</b><br/>历史百分位: <b>${p.value}%</b><br/>份额: ${(rawVal / 1e8).toFixed(2)}亿份`;
        },
      },
      grid: { left: '10%', right: '3%', top: '10%', bottom: '15%' },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
      series: [{
        name: '份额百分位', type: 'scatter',
        data: pctValues.map((v) => ({ value: v, itemStyle: { color: chartTheme.upColor } })),
        symbolSize: 10,
        markPoint: { data: markPoints, symbol: 'diamond', symbolSize: 16, label: { show: false } },
        markLine: {
          silent: true,
          lineStyle: { color: 'rgba(60,60,60,0.06)', type: 'dashed' as const, width: 1 },
          label: { position: 'insideEndTop', fontSize: 10 },
          data: [
            { yAxis: 80, label: { formatter: '高位 80%' } },
            { yAxis: 50, label: { formatter: '中位 50%' } },
            { yAxis: 20, label: { formatter: '低位 20%' } },
          ],
        },
      }],
    };
  }

  const lastKline = kline[kline.length - 1];
  const lastPct = lastKline?.pct_chg || 0;

  // Build sector tab list from sector cards
  const sectorTabs = (sectorCards || []).map((c) => ({
    code: c.ts_code,
    label: c.name,
  }));

  return (
    <ErrorBoundary>
      <div className="space-y-4 sm:space-y-6">
        {/* Mode toggle */}
        <div className="flex gap-2 mb-2">
          <button
            onClick={() => { setMode('index'); setActiveCode('510300.SH'); }}
            className={`rounded-lg px-4 py-2 text-sm font-semibold touch-ripple min-h-[44px] transition-colors ${
              mode === 'index'
                ? 'bg-[var(--c-accent)] text-white'
                : 'glass border-[var(--c-border)]'
            }`}
          >
            指数ETF
          </button>
          <button
            onClick={() => {
              setMode('sector');
              if (sectorCards && sectorCards.length > 0) {
                setActiveCode(sectorCards[0].ts_code);
              }
            }}
            className={`rounded-lg px-4 py-2 text-sm font-semibold touch-ripple min-h-[44px] transition-colors ${
              mode === 'sector'
                ? 'bg-[var(--c-accent)] text-white'
                : 'glass border-[var(--c-border)]'
            }`}
          >
            行业ETF
          </button>
        </div>

        {/* Tab buttons (index or sector) */}
        <div className="flex gap-2 flex-wrap">
          {(mode === 'index' ? INDEX_ETF_TABS : sectorTabs).map((tab) => (
            <button
              key={tab.code}
              onClick={() => setActiveCode(tab.code)}
              className={`glass rounded-lg px-4 py-2.5 text-sm font-semibold touch-ripple min-h-[44px] transition-colors ${
                activeCode === tab.code
                  ? 'border-[var(--c-accent)] text-[var(--c-accent)] bg-[var(--c-accent-bg)]'
                  : 'border-[var(--c-border)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Info card */}
        {isLoading ? (
          <Skeleton className="h-20" />
        ) : (
          <div className="glass rounded-xl p-4 sm:p-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <span className="text-xl font-bold mr-2">{data?.name || '--'}</span>
                <span className="text-sm text-[var(--c-text-tertiary)]">{activeCode}</span>
              </div>
              <div className="flex gap-4 sm:gap-6 text-sm">
                <div>
                  <span className="text-[var(--c-text-tertiary)]">最新价(元) </span>
                  <span className="text-xl font-bold font-mono ml-1">{formatNum(lastKline?.close)}</span>
                </div>
                <div>
                  <span className="text-[var(--c-text-tertiary)]">涨跌幅 </span>
                  <span className="text-xl font-bold font-mono ml-1" style={{ color: pctColor(lastPct) }}>
                    {pctText(lastPct)}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--c-text-tertiary)]">成交额(万) </span>
                  <span className="text-xl font-bold font-mono ml-1">
                    {formatNum(((lastKline?.amount || 0) / 10000), 0)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* K-line chart */}
        <section className="glass rounded-xl p-4 sm:p-5">
          <h3 className="font-bold mb-3 flex items-center gap-2">
            <span className="w-1 h-5 rounded bg-[var(--c-accent)]" />
            K线走势
            <span className="text-xs text-[var(--c-text-tertiary)]">（红色标记 = 异常涨跌幅）</span>
          </h3>
          <AdaptiveChart
            option={buildKlineOption()}
            height={{ mobile: 320, tablet: 400, desktop: 450 }}
            loading={isLoading}
          />
        </section>

        {/* Share chart */}
        <section className="glass rounded-xl p-4 sm:p-5">
          <h3 className="font-bold mb-3 flex items-center gap-2">
            <span className="w-1 h-5 rounded bg-[var(--c-accent)]" />
            份额变化
            <span className="text-xs text-[var(--c-text-tertiary)]">（蓝色标记 = 份额异常变动）</span>
          </h3>
          <AdaptiveChart
            option={buildSharesOption()}
            height={{ mobile: 280, tablet: 350, desktop: 400 }}
            loading={isLoading}
          />
        </section>

        {/* Anomaly lists */}
        <section className="glass rounded-xl p-4 sm:p-5">
          <h3 className="font-bold mb-4 flex items-center gap-2">
            <span className="w-1 h-5 rounded bg-[var(--c-accent)]" />
            异常事件标记
            <span className="text-xs text-[var(--c-text-tertiary)]">（超过2倍标准差）</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm mb-2 text-[var(--c-text-tertiary)]">价格异常</h4>
              {isLoading ? (
                <Skeleton className="h-24" />
              ) : (anomalies.price || []).length === 0 ? (
                <div className="text-sm text-[var(--c-text-tertiary)]">暂无价格异常事件</div>
              ) : (
                <div className="space-y-2 text-sm">
                  {(anomalies.price || []).slice(-10).reverse().map((a) => (
                    <div key={a.trade_date} className="flex items-center justify-between glass rounded px-3 py-2">
                      <span>
                        <span className="inline-block w-2 h-2 rounded-full bg-[var(--c-up)] mr-2" />
                        {fmtDate(a.trade_date)}
                      </span>
                      <span className="font-bold font-mono" style={{ color: pctColor(a.pct_chg) }}>
                        {pctText(a.pct_chg)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <h4 className="text-sm mb-2 text-[var(--c-text-tertiary)]">份额异常</h4>
              {isLoading ? (
                <Skeleton className="h-24" />
              ) : (anomalies.share || []).length === 0 ? (
                <div className="text-sm text-[var(--c-text-tertiary)]">暂无份额异常事件</div>
              ) : (
                <div className="space-y-2 text-sm">
                  {(anomalies.share || []).slice(-10).reverse().map((a) => (
                    <div key={a.trade_date} className="flex items-center justify-between glass rounded px-3 py-2">
                      <span>
                        <span className="inline-block w-2 h-2 rounded-full bg-[var(--c-accent)] mr-2" />
                        {fmtDate(a.trade_date)}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono" style={{ color: (a.chg_pct || 0) >= 0 ? 'var(--c-up)' : 'var(--c-down)' }}>
                          {(a.chg_pct || 0) >= 0 ? '+' : ''}{(a.chg_pct || 0).toFixed(2)}%
                        </span>
                        {a.z_score != null && (
                          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-[var(--c-accent-bg)] text-[var(--c-accent)]">
                            {a.z_score.toFixed(1)}σ
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </ErrorBoundary>
  );
}
