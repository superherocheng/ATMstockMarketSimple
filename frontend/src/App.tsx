import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import AppLayout from '@/components/layout/AppLayout';
import { Skeleton } from '@/components/ui/Skeleton';

// Lazy-loaded pages
const HomePage = lazy(() => import('@/pages/HomePage'));
const ETFPage = lazy(() => import('@/pages/ETFPage'));
const SectorPage = lazy(() => import('@/pages/SectorPage'));
const StocksPage = lazy(() => import('@/pages/StocksPage'));
const StockDetailPage = lazy(() => import('@/pages/StockDetailPage'));
const BarraPage = lazy(() => import('@/pages/BarraPage'));
const ConceptPage = lazy(() => import('@/pages/ConceptPage'));
const IndustryPage = lazy(() => import('@/pages/IndustryPage'));

function PageFallback() {
  return (
    <div className="space-y-4 p-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

export default function App() {
  return (
    <AppLayout>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/etf" element={<ETFPage />} />
          <Route path="/sector" element={<SectorPage />} />
          <Route path="/stocks" element={<StocksPage />} />
          <Route path="/stock/:code" element={<StockDetailPage />} />
          <Route path="/barra" element={<BarraPage />} />
          <Route path="/concept" element={<ConceptPage />} />
          <Route path="/industry" element={<IndustryPage />} />
        </Routes>
      </Suspense>
    </AppLayout>
  );
}
