import { type ReactNode } from 'react';
import BottomTabBar from './BottomTabBar';
import MoreDrawer from './MoreDrawer';
import { MoreDrawerProvider } from '@/components/layout/MoreDrawerContext';

interface AppLayoutProps {
  children: ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  return (
    <MoreDrawerProvider>
      <div className="app-shell flex flex-col min-h-screen">
        {/* Top skip-link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:rounded-lg focus:bg-accent focus:text-white"
        >
          跳转到主要内容
        </a>

        {/* Desktop sidebar */}
        <aside className="hidden desktop:flex flex-col fixed left-0 top-0 bottom-0 w-16 bg-white/80 backdrop-blur border-r border-[var(--c-border)] z-40 pt-[var(--safe-area-top)]">
          <BottomTabBar variant="desktop" />
        </aside>

        {/* Main content */}
        <main
          id="main-content"
          className="flex-1 px-4 py-4 pb-[calc(var(--bottom-nav-height)+var(--safe-area-bottom)+1rem)] desktop:pl-20 desktop:pt-6 desktop:pb-6 max-w-7xl mx-auto w-full"
        >
          {children}
        </main>

        {/* Mobile bottom tab bar */}
        <nav
          className="desktop:hidden fixed bottom-0 inset-x-0 z-50 bg-white/90 backdrop-blur border-t border-[var(--c-border)]"
          style={{ paddingBottom: 'var(--safe-area-bottom)' }}
          role="navigation"
          aria-label="主导航"
        >
          <BottomTabBar variant="mobile" />
        </nav>

        {/* More drawer (mobile: bottom sheet, desktop: side drawer) */}
        <MoreDrawer />
      </div>
    </MoreDrawerProvider>
  );
}
