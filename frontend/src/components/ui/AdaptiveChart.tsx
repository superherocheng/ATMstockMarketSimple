import { useEffect, useRef } from 'react';
import echarts from '@/lib/echarts-setup';
import { simplifyOptionForMobile } from '@/lib/chart-theme';

export interface AdaptiveChartProps {
  option: Record<string, unknown>;
  height?: number | { mobile: number; tablet: number; desktop: number };
  className?: string;
  loading?: boolean;
}

function resolveHeight(
  h: AdaptiveChartProps['height'],
  width: number
): number {
  if (typeof h === 'number') return h;
  if (typeof h === 'object') {
    if (width < 640) return h.mobile;
    if (width < 1024) return h.tablet;
    return h.desktop;
  }
  return 350;
}

export function AdaptiveChart({ option, height = 350, className, loading }: AdaptiveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const widthRef = useRef<number>(typeof window !== 'undefined' ? window.innerWidth : 768);

  // Init
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    const observer = new ResizeObserver(() => {
      if (chartRef.current && !chartRef.current.isDisposed()) {
        widthRef.current = containerRef.current?.clientWidth ?? widthRef.current;
        chartRef.current.resize();
      }
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  // Update option
  useEffect(() => {
    if (!chartRef.current || chartRef.current.isDisposed()) return;
    const simplified = simplifyOptionForMobile(option, widthRef.current);
    chartRef.current.setOption(simplified, true);
  }, [option]);

  // Manual resize on orientation change
  useEffect(() => {
    const handler = () => {
      setTimeout(() => {
        if (chartRef.current && !chartRef.current.isDisposed()) {
          widthRef.current = containerRef.current?.clientWidth ?? widthRef.current;
          chartRef.current.resize();
          const simplified = simplifyOptionForMobile(option, widthRef.current);
          chartRef.current.setOption(simplified, true);
        }
      }, 200);
    };
    window.addEventListener('orientationchange', handler);
    return () => window.removeEventListener('orientationchange', handler);
  }, [option]);

  const resolvedH = resolveHeight(height, widthRef.current);

  return (
    <div className={className} style={{ height: resolvedH, position: 'relative' }}>
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/50 rounded-lg">
          <div className="w-8 h-8 border-2 border-[var(--c-accent)] border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}
