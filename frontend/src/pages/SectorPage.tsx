import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { useSearchParams } from 'react-router-dom';

export default function SectorPage() {
  const [params] = useSearchParams();
  const code = params.get('code');

  // Redirect to Jinja2 version
  window.location.href = code ? `/sector?code=${code}` : '/sector';

  return null;
}
