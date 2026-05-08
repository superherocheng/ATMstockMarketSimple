import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { StatCard } from '@/components/ui/StatCard';
import { useOverview, useDataRange, useFetchStatus, useSectorCards } from '@/api/hooks';
import api from '@/api/client';
import { formatNum, pctText, pctColor } from '@/lib/utils';
import { useState, useCallback, useEffect, useRef } from 'react';

export default function HomePage() {
  const { data, isLoading, isError, refetch } = useOverview();
  const { data: sectorCards, isLoading: scLoading } = useSectorCards();
  const { data: dataRange, isLoading: drLoading } = useDataRange();
  const { data: fetchStatus } = useFetchStatus();

  const [fetchLog, setFetchLog] = useState<string[]>([]);
  const [fetchProgress, setFetchProgress] = useState(0);
  const [fetchRunning, setFetchRunning] = useState(false);
  const [fetchStep, setFetchStep] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  const pollStatus = useCallback(async () => {
    try {
      const st = await api.get<{
        running: boolean;
        progress: number;
        current_step: string;
        log: string[];
        finished_at: string | null;
      }>('/api/fetch/status');
      setFetchLog(st.log || []);
      setFetchProgress(st.progress || 0);
      setFetchRunning(st.running);
      setFetchStep(st.current_step || '');
      if (!st.running && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = undefined;
        refetch();
      }
    } catch {
      // ignore
    }
  }, [refetch]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startFetch = async (type: 'tushare' | 'akshare' | 'all') => {
    try {
      setFetchRunning(true);
      await api.post(`/api/fetch/${type}`);
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(pollStatus, 1500);
      setTimeout(pollStatus, 500);
    } catch {
      // 409 = already running
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(pollStatus, 1500);
    }
  };

  if (isError) {
    return (
      <EmptyState
        title="数据加载失败"
        description="请检查网络连接或后端服务状态"
        action={
          <button onClick={() => refetch()} className="px-4 py-2 rounded-lg bg-[var(--c-accent)] text-white font-medium text-sm">
            重试
          </button>
        }
      />
    );
  }

  return (
    <ErrorBoundary>
      <div className="space-y-4 sm:space-y-6">
        {/* Index ETF Cards */}
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-[var(--c-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            三大指数ETF
          </h2>
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {(data?.index_etf || []).map((etf) => (
                <StatCard
                  key={etf.ts_code}
                  label={`${etf.name} ${etf.ts_code}`}
                  value={formatNum(etf.close)}
                  subValue={`${pctText(etf.pct_chg)} · 成交额 ${formatNum((etf.amount || 0) / 10000, 0)}万`}
                  trend={etf.pct_chg > 0 ? 'up' : etf.pct_chg < 0 ? 'down' : 'neutral'}
                  onClick={() => (window.location.href = '/etf')}
                />
              ))}
            </div>
          )}
        </section>

        {/* Sector ETF Cards */}
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-[var(--c-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            行业ETF行情
            <a href="/sector" className="text-xs font-normal ml-auto text-[var(--c-accent)]">查看全部 →</a>
          </h2>
          {scLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-24" />
              ))}
            </div>
          ) : !sectorCards || sectorCards.length === 0 ? (
            <EmptyState title="暂无行业ETF数据" description="请先点击「全部数据」获取" />
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
              {[...sectorCards]
                .sort((a, b) => b.pct_chg - a.pct_chg)
                .map((card) => (
                  <div
                    key={card.ts_code}
                    className="glass rounded-xl p-3 sm:p-4 cursor-pointer touch-ripple"
                    onClick={() => (window.location.href = `/sector?code=${card.ts_code}`)}
                  >
                    <div className="font-medium text-sm mb-1 text-[var(--c-ink)]">{card.name}</div>
                    <div className="text-lg font-bold font-mono" style={{ color: pctColor(card.pct_chg) }}>
                      {pctText(card.pct_chg)}
                    </div>
                    <div className="text-xs text-[var(--c-text-tertiary)] mt-1">
                      {card.close ? formatNum(card.close) : '--'}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </section>

        {/* Sector Heatmap */}
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-[var(--c-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            行业板块热力图
          </h2>
          <div className="glass rounded-xl p-4 sm:p-5">
            {isLoading ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                {Array.from({ length: 10 }).map((_, i) => (
                  <Skeleton key={i} className="h-20" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                {[...(data?.sector_summary || [])]
                  .sort((a, b) => b.pct_chg - a.pct_chg)
                  .map((s) => {
                    const pct = s.pct_chg;
                    const intensity = Math.min(Math.abs(pct) / 3, 1);
                    const bg =
                      pct > 0
                        ? `rgba(212,114,106,${0.08 + intensity * 0.12})`
                        : pct < 0
                          ? `rgba(106,175,124,${0.08 + intensity * 0.12})`
                          : undefined;
                    return (
                      <div
                        key={s.ts_code}
                        className="rounded-lg p-3 sm:p-4 cursor-pointer touch-ripple"
                        style={{ background: bg }}
                        onClick={() => (window.location.href = `/sector?code=${s.ts_code}`)}
                      >
                        <div className="font-medium text-sm mb-1 text-[var(--c-ink)]">{s.name}</div>
                        <div className="text-lg font-bold font-mono" style={{ color: pctColor(pct) }}>
                          {pctText(pct)}
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        </section>

        {/* Data Management */}
        <section>
          <div className="glass rounded-xl p-4 sm:p-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <svg className="w-5 h-5 text-[var(--c-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                </svg>
                数据管理
              </h2>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => startFetch('tushare')}
                  disabled={fetchRunning}
                  className="px-4 py-2 rounded-lg border border-[var(--c-border)] text-sm font-medium touch-ripple disabled:opacity-50 min-h-[44px]"
                >
                  Tushare数据
                </button>
                <button
                  onClick={() => startFetch('akshare')}
                  disabled={fetchRunning}
                  className="px-4 py-2 rounded-lg border border-[var(--c-border)] text-sm font-medium touch-ripple disabled:opacity-50 min-h-[44px]"
                >
                  AKShare数据
                </button>
                <button
                  onClick={() => startFetch('all')}
                  disabled={fetchRunning}
                  className="px-4 py-2 rounded-lg bg-[var(--c-accent)] text-white text-sm font-medium touch-ripple disabled:opacity-50 min-h-[44px]"
                >
                  {fetchRunning ? '获取中...' : '全部数据'}
                </button>
              </div>
            </div>

            {/* Data freshness table */}
            {drLoading ? (
              <Skeleton className="h-48" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--c-border)]">
                      <th className="px-3 py-2 text-left">数据类型</th>
                      <th className="px-3 py-2 text-left">数据表</th>
                      <th className="px-3 py-2 text-right">记录数</th>
                      <th className="px-3 py-2 text-left hidden sm:table-cell">日期范围</th>
                      <th className="px-3 py-2 text-center">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataRange &&
                      Object.entries(dataRange).map(([key, info]) => {
                        const isFresh = info.exists && info.count > 0;
                        const color = isFresh ? 'var(--c-down)' : 'var(--c-gold)';
                        return (
                          <tr key={key} className="border-b border-[var(--c-border)] last:border-b-0">
                            <td className="px-3 py-2 font-medium">--</td>
                            <td className="px-3 py-2 text-[var(--c-text-secondary)]">{info.display_name}</td>
                            <td className="px-3 py-2 text-right font-mono">{info.count.toLocaleString()}</td>
                            <td className="px-3 py-2 text-xs font-mono hidden sm:table-cell text-[var(--c-text-tertiary)]">
                              {info.min_date && info.max_date
                                ? `${info.min_date} ~ ${info.max_date}`
                                : '-'}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span
                                className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
                                style={{ background: `${color}15`, color }}
                              >
                                <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
                                {isFresh ? '正常' : '待更新'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Fetch progress */}
            {fetchRunning && (
              <div className="border-t border-[var(--c-border)] pt-3 mt-3 space-y-2">
                <div className="flex items-center gap-3">
                  <div className="w-5 h-5 border-2 border-[var(--c-accent)] border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm font-semibold text-[var(--c-accent)]">获取中...</span>
                  <span className="text-sm text-[var(--c-text-tertiary)]">{fetchStep}</span>
                </div>
                <div className="h-1.5 bg-[var(--c-bg-tertiary)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[var(--c-accent)] rounded-full transition-all duration-500"
                    style={{ width: `${Math.max(fetchProgress, 2)}%` }}
                  />
                </div>
                {fetchLog.length > 0 && (
                  <details>
                    <summary className="text-sm cursor-pointer text-[var(--c-text-tertiary)]">实时日志</summary>
                    <div className="rounded-lg p-3 mt-2 max-h-48 overflow-y-auto text-xs font-mono bg-[var(--c-bg-secondary)] border border-[var(--c-border)]">
                      {fetchLog.map((line, i) => (
                        <div
                          key={i}
                          className={
                            line.startsWith('[ERROR]')
                              ? 'text-[var(--c-up)]'
                              : line.startsWith('[OK]') || line.startsWith('[DONE]')
                                ? 'text-[var(--c-down)] font-semibold'
                                : 'text-[var(--c-text-secondary)]'
                          }
                        >
                          {line}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Quick Links (Mobile only) */}
        <section className="desktop:hidden grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { href: '/etf', label: '指数ETF分析', desc: '沪深300 / 中证500 / 上证50', color: 'var(--c-watercolor-terracotta)', bg: 'var(--c-watercolor-terracotta-bg)' },
            { href: '/sector', label: '行业ETF轮动', desc: '板块资金流向，横向对比', color: 'var(--c-watercolor-green)', bg: 'var(--c-watercolor-green-bg)' },
            { href: '/stocks', label: '个股排行榜', desc: '波动率 / 涨跌幅 TOP10', color: 'var(--c-watercolor-blue)', bg: 'var(--c-watercolor-blue-bg)' },
            { href: '/barra', label: 'BARRA因子分析', desc: '行业/量价/市值/成长价值', color: 'var(--c-watercolor-lavender)', bg: 'var(--c-watercolor-lavender-bg)' },
          ].map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="glass rounded-xl p-5 block transition-all hover:border-[var(--c-accent)] group touch-ripple"
            >
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
                style={{ background: link.bg }}
              >
                <div className="w-5 h-5" style={{ color: link.color }}>
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
              </div>
              <h3 className="font-semibold mb-1">{link.label}</h3>
              <p className="text-sm text-[var(--c-text-tertiary)]">{link.desc}</p>
            </a>
          ))}
        </section>
      </div>
    </ErrorBoundary>
  );
}
