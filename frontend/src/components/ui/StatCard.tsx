import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  trend?: 'up' | 'down' | 'neutral';
  onClick?: () => void;
  className?: string;
}

export function StatCard({ label, value, subValue, trend, onClick, className }: StatCardProps) {
  const trendColor =
    trend === 'up' ? 'var(--c-up)' : trend === 'down' ? 'var(--c-down)' : 'var(--c-text-secondary)';

  return (
    <div
      className={cn(
        'glass rounded-xl p-4 sm:p-5',
        onClick && 'cursor-pointer hover:border-[var(--c-accent)] transition-all',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="text-xs text-[var(--c-text-tertiary)] mb-1">{label}</div>
      <div className="text-xl sm:text-2xl font-bold font-mono" style={{ color: trendColor }}>
        {value}
      </div>
      {subValue && (
        <div className="text-xs mt-1 text-[var(--c-text-tertiary)]">{subValue}</div>
      )}
    </div>
  );
}
