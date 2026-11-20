import { Suspense, lazy, useEffect, useRef } from 'react';
import { Spinner } from '@fluentui/react-components';
import { MOCK_MODE } from './data/repo';
import { useRoute } from './hooks/useRoute';
import type { Route } from './hooks/useRoute';
import { ContractsList } from './screens/ContractsList';
import { ReviewScreen } from './screens/ReviewScreen';

// The about pages carry the 3D library, so they download only when someone opens them.
const HowItWorksScreen = lazy(() => import('./about/HowItWorksScreen'));
const CostScreen = lazy(() => import('./about/CostScreen'));

const NAV: readonly { label: string; href: string; isCurrent: (route: Route) => boolean }[] = [
  { label: 'Contracts', href: '#/', isCurrent: (route) => route.name === 'list' || route.name === 'contract' },
  { label: 'How it works', href: '#/how-it-works', isCurrent: (route) => route.name === 'how-it-works' },
  { label: 'Time and cost', href: '#/cost', isCurrent: (route) => route.name === 'cost' },
];

function Page({ route }: { route: Route }) {
  switch (route.name) {
    case 'contract':
      return <ReviewScreen key={route.id} contractId={route.id} />;
    case 'how-it-works':
      return (
        <Suspense fallback={<PageLoading />}>
          <HowItWorksScreen />
        </Suspense>
      );
    case 'cost':
      return (
        <Suspense fallback={<PageLoading />}>
          <CostScreen />
        </Suspense>
      );
    default:
      return <ContractsList />;
  }
}

function PageLoading() {
  return (
    <div className="screen-state">
      <Spinner label="Loading" />
    </div>
  );
}

export function App() {
  const route = useRoute();
  const mainRef = useRef<HTMLElement>(null);

  // The about pages start at the top, even when the page before was scrolled.
  useEffect(() => {
    if (route.name === 'how-it-works' || route.name === 'cost') mainRef.current?.scrollTo({ top: 0 });
  }, [route.name]);

  return (
    <div className="shell">
      <div className="shell__top">
        <header className="vz-appbar">
          <a className="vz-appbar__title" href="#/">
            Contract Review
          </a>
          <span className="vz-appbar__spacer" />
          <nav className="vz-appbar__nav" aria-label="Pages">
            {NAV.map((item) => (
              <a key={item.href} className="vz-appbar__link" href={item.href} aria-current={item.isCurrent(route) ? 'page' : undefined}>
                {item.label}
              </a>
            ))}
          </nav>
          {MOCK_MODE ? (
            <span className="vz-chip vz-chip--warning" title="Running on local sample data. Nothing is read from or saved to Dataverse.">
              Mock data
            </span>
          ) : null}
        </header>
      </div>
      <main ref={mainRef} className="shell__main">
        <Page route={route} />
      </main>
    </div>
  );
}
