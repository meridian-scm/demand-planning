import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import ForecastRunsPage from '../pages/ForecastRunsPage';
import { renderApp } from './render';
import { server } from './server';

describe('Forecast Runs', () => {
  it('shows published run metadata, series results, evaluations, and forecasts', async () => {
    renderApp(<ForecastRunsPage />, '/forecast-runs');

    expect(await screen.findByText('forecast-test-run-1')).toBeVisible();
    const summary = screen.getByRole('region', { name: 'Forecast run summary' });
    expect(within(summary).getByText('119')).toBeVisible();
    expect(within(summary).getByText('570')).toBeVisible();
    expect((await screen.findAllByText('Northstar Herbal Tea 34')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('AutoETS').length).toBeGreaterThan(0);
    expect(await screen.findByRole('cell', { name: 'Yes' })).toBeVisible();
    expect(screen.getByRole('columnheader', { name: 'Forecast' })).toBeVisible();
    expect(screen.getAllByText('17.3%').length).toBeGreaterThan(0);
  });

  it('switches selected series and loads its stored governance evidence', async () => {
    const user = userEvent.setup();
    renderApp(<ForecastRunsPage />, '/forecast-runs');
    await screen.findAllByText('Northstar Herbal Tea 34');

    await user.click(screen.getByRole('button', { name: /SKU-00002/ }));

    expect(await screen.findByRole('heading', { name: 'Harbor Sparkling Water 12' })).toBeVisible();
    expect(screen.getAllByText('SeasonalNaive').length).toBeGreaterThan(0);
  });

  it('shows an empty state when no immutable run has been published', async () => {
    server.use(http.get('*/api/v1/forecast-runs', () => HttpResponse.json([])));

    renderApp(<ForecastRunsPage />, '/forecast-runs');

    expect(await screen.findByText('No forecast runs available')).toBeVisible();
  });
});
