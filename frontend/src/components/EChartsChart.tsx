import { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface Props {
  /** Full ECharts option object. The backend chart_builder assembles it (series,
   * axes, colors); we pass it straight through — no palette re-injection. */
  option: Record<string, unknown>;
  height?: number | string;
  className?: string;
  loading?: boolean;
  /** ECharts 事件绑定（如 { click: fn }）。按事件名在 mount/键变化时绑定一次，
   * handler 本体经 ref 读取最新闭包，避免每次渲染重绑。 */
  onEvents?: Partial<Record<string, (params: echarts.ECElementEvent) => void>>;
}

/** Count data points across all series to gate the perf constraint (>1000 → no animation). */
function countPoints(option: Record<string, unknown>): number {
  const series = option.series;
  if (!Array.isArray(series)) return 0;
  return series.reduce(
    (n, s) => n + (Array.isArray((s as Record<string, unknown>)?.data) ? (s as { data: unknown[] }).data.length : 0),
    0,
  );
}

export function EChartsChart({ option, height = 280, className, loading, onEvents }: Props) {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const onEventsRef = useRef(onEvents);
  onEventsRef.current = onEvents;
  // 事件键集合（"click,legendselectchanged"）——键列表变了才重绑。
  const eventKeys = onEvents ? Object.keys(onEvents).join(",") : "";

  useEffect(() => {
    if (!elRef.current) return;
    if (!chartRef.current) {
      // "dark" theme makes axis/legend text legible on our dark cards.
      // Override background to transparent so the card surface shows through.
      chartRef.current = echarts.init(elRef.current);
    }
    const points = countPoints(option);
    const opt = {
      backgroundColor: "transparent",
      ...option,
      animation: points > 1000 ? false : (option.animation ?? true),
    } as echarts.EChartsOption;
    chartRef.current.setOption(opt, true);
  }, [option]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !eventKeys) return;
    const bound: Array<[string, (...args: unknown[]) => void]> = eventKeys
      .split(",")
      .map((key) => [
        key,
        (...args: unknown[]) => onEventsRef.current?.[key]?.(args[0] as echarts.ECElementEvent),
      ]);
    for (const [key, handler] of bound) chart.on(key, handler);
    return () => {
      // unbind 时实例可能已被 dispose（卸载顺序），静默忽略。
      try {
        for (const [key, handler] of bound) chart.off(key, handler);
      } catch {
        /* disposed */
      }
    };
  }, [eventKeys]);

  useEffect(() => {
    const onResize = () => chartRef.current?.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  if (loading) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-muted-foreground ${className ?? ""}`}
        style={{ width: "100%", height }}
      >
        加载中…
      </div>
    );
  }

  return <div ref={elRef} style={{ width: "100%", height }} className={className} />;
}
