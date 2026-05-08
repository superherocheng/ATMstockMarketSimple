import { NavLink, useLocation } from 'react-router-dom';
import { Home, TrendingUp, PieChart, BarChart3, Menu } from 'lucide-react';
import { useMoreDrawer } from './MoreDrawerContext';
import { cn } from '@/lib/utils';

const TABS = [
  { path: '/', label: '首页', icon: Home, id: 'home' },
  { path: '/etf', label: 'ETF', icon: TrendingUp, id: 'etf' },
  { path: '/sector', label: '行业', icon: PieChart, id: 'sector' },
  { path: '/stocks', label: '排行', icon: BarChart3, id: 'stocks' },
] as const;

interface BottomTabBarProps {
  variant: 'mobile' | 'desktop';
}

export default function BottomTabBar({ variant }: BottomTabBarProps) {
  const location = useLocation();
  const { toggle } = useMoreDrawer();

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  if (variant === 'desktop') {
    return (
      <div className="flex flex-col items-center gap-1 py-4">
        {TABS.map((tab) => (
          <NavLink
            key={tab.id}
            to={tab.path}
            className={cn(
              'flex flex-col items-center gap-0.5 py-2 px-2 rounded-lg w-full text-center transition-colors',
              'min-h-[44px] min-w-[44px] justify-center touch-ripple',
              isActive(tab.path)
                ? 'text-[var(--c-accent)] bg-[var(--c-accent-bg)]'
                : 'text-[var(--c-text-tertiary)] hover:text-[var(--c-text-primary)]'
            )}
            aria-label={tab.label}
          >
            <tab.icon size={20} strokeWidth={2} aria-hidden="true" />
            <span className="text-[10px] leading-tight">{tab.label}</span>
          </NavLink>
        ))}
        <button
          onClick={toggle}
          className={cn(
            'flex flex-col items-center gap-0.5 py-2 px-2 rounded-lg w-full text-center transition-colors',
            'min-h-[44px] min-w-[44px] justify-center touch-ripple',
            'text-[var(--c-text-tertiary)] hover:text-[var(--c-text-primary)]'
          )}
          aria-label="更多菜单"
        >
          <Menu size={20} strokeWidth={2} aria-hidden="true" />
          <span className="text-[10px] leading-tight">更多</span>
        </button>
      </div>
    );
  }

  // Mobile variant
  return (
    <div className="flex items-center justify-around h-[var(--bottom-nav-height)]">
      {TABS.map((tab) => (
        <NavLink
          key={tab.id}
          to={tab.path}
          className={cn(
            'flex flex-col items-center gap-0.5 py-1 px-3 rounded-lg text-center transition-colors',
            'min-h-[44px] min-w-[44px] justify-center touch-ripple',
            isActive(tab.path)
              ? 'text-[var(--c-accent)]'
              : 'text-[var(--c-text-tertiary)]'
          )}
          aria-label={tab.label}
          aria-current={isActive(tab.path) ? 'page' : undefined}
        >
          <tab.icon size={22} strokeWidth={2} aria-hidden="true" />
          <span className="text-[11px] leading-tight font-medium">{tab.label}</span>
        </NavLink>
      ))}
      <button
        onClick={toggle}
        className={cn(
          'flex flex-col items-center gap-0.5 py-1 px-3 rounded-lg text-center transition-colors',
          'min-h-[44px] min-w-[44px] justify-center touch-ripple',
          'text-[var(--c-text-tertiary)]'
        )}
        aria-label="更多菜单"
        aria-expanded={false}
      >
        <Menu size={22} strokeWidth={2} aria-hidden="true" />
        <span className="text-[11px] leading-tight font-medium">更多</span>
      </button>
    </div>
  );
}
