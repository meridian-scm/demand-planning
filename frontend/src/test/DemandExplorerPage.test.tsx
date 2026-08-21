import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import DemandExplorerPage from '../pages/DemandExplorerPage';
import { renderApp } from './render';
import { forecastPreviewResponse, server } from './server';

describe('Demand Explorer', () => {
  it('loads Store + SKU history and presents planner-facing evidence', async () => {
    renderApp(<DemandExplorerPage />, '/demand-explorer');

    expect(await screen.findByRole('option', { name: 'Toronto Central · TOR-01' })).toBeVisible();
    expect(
      await screen.findByRole('option', {
        name: 'SKU-00001 · Northstar Herbal Tea 34',
      }),
    ).toBeVisible();
    expect(await screen.findByText('312')).toBeVisible();
    expect(
      screen.getByRole('img', { name: 'Historical monthly demand chart for SKU-00001' }),
    ).toBeVisible();
    expect(screen.getByText('14 days')).toBeVisible();
    expect(screen.getByText('31 units')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Generate forecast' })).toBeEnabled();
    expect(await screen.findByRole('heading', { name: 'Demand signals' })).toBeVisible();
    expect(screen.getByText('Demand is growing')).toBeVisible();
    expect(screen.getByText('Annual seasonality detected')).toBeVisible();
    expect(screen.getByText('Demand spike detected')).toBeVisible();
    expect(screen.getByText('147.1 units')).toBeVisible();
    expect(screen.getByText('210 units')).toBeVisible();
    const inventory = await screen.findByRole('region', { name: 'Inventory risk' });
    expect(within(inventory).getAllByText('Below safety stock').length).toBeGreaterThan(0);
    expect(within(inventory).getByText('15 units')).toBeVisible();
    expect(within(inventory).getByText(/80 on hand.*20 allocated/)).toBeVisible();
    expect(within(inventory).getByText('55')).toBeVisible();
    expect(within(inventory).getAllByText(/SeasonalNaive/).length).toBeGreaterThan(0);
  });

  it('generates a selected horizon and displays forecast evidence on the chart', async () => {
    const user = userEvent.setup();
    renderApp(<DemandExplorerPage />, '/demand-explorer');
    await screen.findByRole('button', { name: 'Generate forecast' });

    await user.selectOptions(screen.getByRole('combobox', { name: 'Forecast horizon' }), '3');
    await user.click(screen.getByRole('button', { name: 'Generate forecast' }));

    expect(await screen.findByText('Selected model')).toBeVisible();
    expect(screen.getAllByText('SeasonalNaive').length).toBeGreaterThan(0);
    const metrics = screen.getByRole('region', { name: 'Forecast validation metrics' });
    expect(within(metrics).getByText('20.6%')).toBeVisible();
    expect(within(metrics).getByText('1.01')).toBeVisible();
    expect(within(metrics).getByText('91.7%')).toBeVisible();
    expect(
      screen.getByRole('img', { name: 'Actual and forecast monthly demand chart for SKU-00001' }),
    ).toBeVisible();
    expect(screen.getByText('90% interval')).toBeVisible();
    expect(
      screen.getByText(/Compared 2 eligible models across 2 expanding validation origins/),
    ).toBeVisible();
  });

  it('shows an explicit loading state while candidate models are evaluated', async () => {
    server.use(
      http.post('*/api/v1/forecast-previews', async () => {
        await delay(150);
        return HttpResponse.json(forecastPreviewResponse());
      }),
    );
    const user = userEvent.setup();
    renderApp(<DemandExplorerPage />, '/demand-explorer');
    await screen.findByRole('button', { name: 'Generate forecast' });

    await user.click(screen.getByRole('button', { name: 'Generate forecast' }));

    expect(screen.getByRole('button', { name: 'Generating…' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Evaluating candidate models');
    expect(await screen.findByText('Selected model')).toBeVisible();
  });

  it('shows the backend validation explanation when a preview cannot run', async () => {
    server.use(
      http.post('*/api/v1/forecast-previews', () =>
        HttpResponse.json(
          { detail: 'At least 48 completed months are required for this horizon.' },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderApp(<DemandExplorerPage />, '/demand-explorer');
    await screen.findByRole('button', { name: 'Generate forecast' });

    await user.click(screen.getByRole('button', { name: 'Generate forecast' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Forecast could not be generated.');
    expect(alert).toHaveTextContent('At least 48 completed months are required');
    expect(screen.getByRole('button', { name: 'Generate forecast' })).toBeEnabled();
  });

  it('keeps demand available when signal analysis fails', async () => {
    server.use(
      http.get('*/api/v1/signals', () =>
        HttpResponse.json({ detail: 'Signal analysis unavailable.' }, { status: 503 }),
      ),
    );

    renderApp(<DemandExplorerPage />, '/demand-explorer');

    expect(await screen.findByText('Northstar Herbal Tea 34')).toBeVisible();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Demand signals are unavailable.');
    expect(
      screen.getByRole('img', { name: 'Historical monthly demand chart for SKU-00001' }),
    ).toBeVisible();
  });

  it('keeps demand available when inventory-risk calculation fails', async () => {
    server.use(
      http.get('*/api/v1/inventory/risks', () =>
        HttpResponse.json({ detail: 'Inventory risk unavailable.' }, { status: 503 }),
      ),
    );

    renderApp(<DemandExplorerPage />, '/demand-explorer');

    expect(await screen.findByText('Northstar Herbal Tea 34')).toBeVisible();
    expect(await screen.findByText('Inventory risk is unavailable.')).toBeVisible();
    expect(
      screen.getByRole('img', { name: 'Historical monthly demand chart for SKU-00001' }),
    ).toBeVisible();
  });
});
