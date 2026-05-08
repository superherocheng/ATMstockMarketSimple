import { cn } from '@/lib/utils';

export interface ColumnDef<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  hiddenOnMobile?: boolean;
  align?: 'left' | 'right' | 'center';
  className?: string;
}

interface ResponsiveTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  mobileCardTitle?: (row: T) => string;
  mobileCardSubtitle?: (row: T) => string;
  keyField?: keyof T;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function ResponsiveTable<T extends Record<string, unknown>>({
  data,
  columns,
  mobileCardTitle,
  mobileCardSubtitle,
  keyField,
  onRowClick,
  emptyMessage = '暂无数据',
}: ResponsiveTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-[var(--c-text-tertiary)] text-sm">
        {emptyMessage}
      </div>
    );
  }

  // Desktop: standard <table>
  return (
    <>
      {/* Desktop table */}
      <div className="hidden sm:block overflow-x-auto rounded-xl border border-[var(--c-border)]">
        <table className="w-full text-sm">
          <thead className="bg-[var(--c-bg-secondary)] border-b border-[var(--c-border)]">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    'px-4 py-3 text-left font-semibold text-[var(--c-text-secondary)] whitespace-nowrap',
                    col.align === 'right' && 'text-right',
                    col.align === 'center' && 'text-center'
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={String(keyField ? row[keyField] : i)}
                className={cn(
                  'border-b border-[var(--c-border)] last:border-b-0',
                  onRowClick && 'cursor-pointer hover:bg-[var(--c-accent-bg)] transition-colors'
                )}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-4 py-3',
                      col.align === 'right' && 'text-right font-mono',
                      col.align === 'center' && 'text-center',
                      col.className
                    )}
                  >
                    {col.render ? col.render(row) : String(row[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile card list */}
      <div className="sm:hidden space-y-3">
        {data.map((row, i) => (
          <div
            key={String(keyField ? row[keyField] : i)}
            className={cn(
              'glass rounded-xl p-4',
              onRowClick && 'cursor-pointer touch-ripple'
            )}
            onClick={() => onRowClick?.(row)}
          >
            {mobileCardTitle && (
              <div className="font-semibold text-[var(--c-text-primary)] mb-1">
                {mobileCardTitle(row)}
              </div>
            )}
            {mobileCardSubtitle && (
              <div className="text-xs text-[var(--c-text-tertiary)] mb-2">
                {mobileCardSubtitle(row)}
              </div>
            )}
            <div className="space-y-1.5">
              {columns
                .filter((col) => !col.hiddenOnMobile)
                .map((col) => (
                  <div key={col.key} className="flex justify-between items-center text-sm">
                    <span className="text-[var(--c-text-tertiary)]">{col.header}</span>
                    <span className={cn('font-medium text-[var(--c-text-primary)]', col.className)}>
                      {col.render ? col.render(row) : String(row[col.key] ?? '')}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
