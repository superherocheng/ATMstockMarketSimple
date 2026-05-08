import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useMoreDrawer } from './MoreDrawerContext';
import { cn } from '@/lib/utils';
import { Search, Activity, Layers, BarChart3 } from 'lucide-react';

const MORE_ITEMS = [
  { path: '/stock/', label: '个股查询', icon: Search, id: 'stock' },
  { path: '/concept', label: '概念轮动', icon: Layers, id: 'concept' },
  { path: '/industry', label: '申万行业', icon: Activity, id: 'industry' },
  { path: '/barra', label: 'BARRA分析', icon: BarChart3, id: 'barra' },
];

export default function MoreDrawer() {
  const { open, setOpen } = useMoreDrawer();
  const panelRef = useRef<HTMLDivElement>(null);
  const touchStartY = useRef(0);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, setOpen]);

  // Pull-down to dismiss (mobile)
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartY.current = e.touches[0].clientY;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    const delta = e.changedTouches[0].clientY - touchStartY.current;
    if (delta > 80) setOpen(false);
  };

  return (
    <>
      {/* Backdrop — softened to avoid blocking taps */}
      <div
        className={cn(
          'fixed inset-0 z-40 transition-opacity duration-300',
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        )}
        style={{ background: open ? 'rgba(0,0,0,0.2)' : 'transparent' }}
        onClick={() => setOpen(false)}
        onTouchEnd={(e) => { e.preventDefault(); setOpen(false); }}
        aria-hidden="true"
      />

      {/* Panel: mobile = bottom sheet, desktop = right drawer */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="更多菜单"
        className={cn(
          'fixed z-50 bg-white/95 backdrop-blur-xl shadow-lg transition-transform duration-300',
          'desktop:top-0 desktop:right-0 desktop:w-72 desktop:bottom-0 desktop:border-l desktop:border-[var(--c-border)]',
          'mobile:inset-x-0 mobile:bottom-0 mobile:rounded-t-2xl mobile:max-h-[70vh] mobile:overflow-y-auto',
          'desktop:translate-x-full',
          'mobile:translate-y-full'
        )}
        style={{
          ...(open
            ? { transform: 'translate(0, 0)' }
            : {}),
        }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {/* Drag handle (mobile only) */}
        <div className="desktop:hidden flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-[var(--c-border)]" />
        </div>

        <div className="p-4 space-y-1">
          <h2 className="text-sm font-semibold text-[var(--c-text-tertiary)] px-3 mb-2 uppercase tracking-wide">
            更多功能
          </h2>
          {MORE_ITEMS.map((item) => (
            <Link
              key={item.id}
              to={item.path}
              onClick={() => setOpen(false)}
              className={cn(
                'flex items-center gap-3 px-3 py-3 rounded-xl transition-colors',
                'min-h-[48px] touch-ripple',
                'hover:bg-[var(--c-accent-bg)] text-[var(--c-text-primary)]'
              )}
            >
              <item.icon size={20} strokeWidth={2} className="text-[var(--c-text-secondary)]" aria-hidden="true" />
              <span className="font-medium">{item.label}</span>
            </Link>
          ))}
        </div>

        {/* Safe area padding for mobile bottom */}
        <div className="desktop:hidden h-[var(--safe-area-bottom)]" />
      </div>
    </>
  );
}
