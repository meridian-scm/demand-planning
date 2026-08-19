import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { LoadingState } from './components/LoadingState';

const OverviewPage = lazy(() => import('./pages/OverviewPage'));
const DemandExplorerPage = lazy(() => import('./pages/DemandExplorerPage'));
const PlanningExceptionsPage = lazy(() => import('./pages/PlanningExceptionsPage'));
const ForecastRunsPage = lazy(() => import('./pages/ForecastRunsPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

export function App() {
  return (
    <Suspense fallback={<LoadingState />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="demand-explorer" element={<DemandExplorerPage />} />
          <Route path="planning-exceptions" element={<PlanningExceptionsPage />} />
          <Route path="forecast-runs" element={<ForecastRunsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
