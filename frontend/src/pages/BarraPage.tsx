import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { AdaptiveChart } from '@/components/ui/AdaptiveChart';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { useBarraSummary } from '@/api/hooks';
import { chartTheme } from '@/lib/chart-theme';

export default function BarraPage() {
  const { data, isLoading, isError, refetch } = useBarraSummary();

  // Build radar-style bar chart from barra data
  function buildFactorChart() {
    const factors = data as Record<string, { name: string; value: number }[]> | undefined;
    if (!factors) return {};

    // Flatten factor data for a simple bar chart
    const entries = Object.entries(factors).flatMap(([category, items]) =>
      (items || []).map((item) => ({
        name: item.name,
        value: item.value,
        category,
      }))
    );

    if (entries.length === 0) return {};

    return {
      backgroundColor: 'transparent',
      textStyle: chartTheme.textStyle,
      title: { text: 'BARRA因子分析', left: '3%', textStyle: { fontSize: 14, fontWeight: 600 } },
      tooltip: { backgroundColor: chartTheme.tooltip.backgroundColor, textStyle: chartTheme.tooltip.textStyle },
      grid: { left: '15%', right: '5%', top: '12%', bottom: '10%' },
      xAxis: { type: 'value', axisLabel: { fontSize: 10 } },
      yAxis: { type: 'category', data: entries.map((e) => e.name), axisLabel: { fontSize: 10 } },
      series: [{
        type: 'bar',
        data: entries.map((e) => ({
          value: e.value,
          itemStyle: { color: e.value > 0 ? chartTheme.upColor : chartTheme.downColor },
        })),
        barMaxWidth: 24,
        label: { show: true, position: 'right', fontSize: 10, formatter: '{c}' },
      }],
    };
  }

  return (
    <ErrorBoundary>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">BARRA因子分析</h2>
        {isError ? (
          <EmptyState title="加载失败" action={<button onClick={() => refetch()} className="px-4 py-2 rounded-lg bg-[var(--c-accent)] text-white text-sm">重试</button>} />
        ) : isLoading ? (
          <Skeleton className="h-96" />
        ) : (
          <div className="glass rounded-xl p-4 sm:p-5">
            <AdaptiveChart
              option={buildFactorChart()}
              height={{ mobile: 400, tablet: 500, desktop: 600 }}
              loading={isLoading}
            />
          </div>
        )}
        <div className="text-sm text-[var(--c-text-tertiary)] text-center">
          BARRA因子数据展示：行业因子 / 量价因子 / 市值因子 / 成长价值因子
        </div>
      </div>
    </ErrorBoundary>
  );
}
