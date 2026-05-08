import { useState } from 'react';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { ResponsiveTable, type ColumnDef } from '@/components/ui/ResponsiveTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useStockRanking } from '@/api/hooks';
import { formatNum, pctText, pctColor } from '@/lib/utils';

const RANKING_TYPES = [
  { key: 'volatility', label: '波动率排行' },
  { key: 'pct_chg', label: '涨跌幅排行' },
  { key: 'score', label: '综合评分' },
];

interface StockRow {
  ts_code: string;
  name: string;
  close: number;
  pct_chg: number;
  vol: number;
  amount: number;
  [key: string]: unknown;
}

export default function StocksPage() {
  const [type, setType] = useState('volatility');
  const { data, isLoading, isError, refetch } = useStockRanking(type);

  const stocks = (data as StockRow[] | undefined) || [];

  const columns: ColumnDef<StockRow>[] = [
    { key: 'ts_code', header: '代码', render: (r) => <span className="font-mono text-xs">{r.ts_code}</span> },
    { key: 'name', header: '名称', render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'close', header: '最新价', align: 'right', render: (r) => <span className="font-mono">{formatNum(r.close)}</span> },
    { key: 'pct_chg', header: '涨跌幅', align: 'right', render: (r) => <span className="font-mono" style={{ color: pctColor(r.pct_chg) }}>{pctText(r.pct_chg)}</span>, hiddenOnMobile: false },
    { key: 'vol', header: '成交量', align: 'right', render: (r) => <span className="font-mono text-xs">{formatNum(r.vol, 0)}</span>, hiddenOnMobile: true },
    { key: 'amount', header: '成交额', align: 'right', render: (r) => <span className="font-mono text-xs">{formatNum(r.amount, 0)}</span>, hiddenOnMobile: true },
  ];

  return (
    <ErrorBoundary>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">个股排行</h2>
        <div className="flex gap-2 flex-wrap">
          {RANKING_TYPES.map((t) => (
            <button
              key={t.key}
              onClick={() => setType(t.key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium touch-ripple min-h-[44px] border ${
                type === t.key
                  ? 'border-[var(--c-accent)] text-[var(--c-accent)] bg-[var(--c-accent-bg)]'
                  : 'border-[var(--c-border)]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        {isError ? (
          <EmptyState title="加载失败" action={<button onClick={() => refetch()} className="px-4 py-2 rounded-lg bg-[var(--c-accent)] text-white text-sm">重试</button>} />
        ) : isLoading ? (
          <div className="space-y-3"><Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-full" /></div>
        ) : (
          <ResponsiveTable
            data={stocks}
            columns={columns}
            keyField="ts_code"
            mobileCardTitle={(r) => `${r.name} (${r.ts_code})`}
            mobileCardSubtitle={(r) => `最新价 ${formatNum(r.close)}`}
            emptyMessage="暂无排行数据"
          />
        )}
      </div>
    </ErrorBoundary>
  );
}
