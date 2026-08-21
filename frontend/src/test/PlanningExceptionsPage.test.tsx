import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import PlanningExceptionsPage from '../pages/PlanningExceptionsPage';
import { renderApp } from './render';
import { server } from './server';

describe('Planning Exceptions', () => {
  it('shows a prioritized selected-series queue with traceable evidence', async () => {
    renderApp(<PlanningExceptionsPage />, '/planning-exceptions');

    const queue = await screen.findByRole('region', { name: 'Exception queue' });
    expect(within(queue).getByText('Potential stockout before replenishment')).toBeVisible();
    expect(within(queue).getByText('Review unusual demand spike')).toBeVisible();
    expect(within(queue).getByText('Significant forecast bias')).toBeVisible();
    expect(within(queue).getByLabelText('Priority 1')).toBeVisible();
    expect(within(queue).getByText('-51.13 units')).toBeVisible();
    expect(within(queue).getByText('Inventory projection')).toBeVisible();
    expect(screen.getByRole('option', { name: 'Toronto Central · TOR-01' })).toBeVisible();
  });

  it('filters the queue by business exception group without rerunning analysis', async () => {
    const user = userEvent.setup();
    renderApp(<PlanningExceptionsPage />, '/planning-exceptions');
    await screen.findByText('Potential stockout before replenishment');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Exception group' }), 'forecast');

    expect(screen.getByText('Significant forecast bias')).toBeVisible();
    expect(screen.queryByText('Potential stockout before replenishment')).not.toBeInTheDocument();
    expect(screen.queryByText('Review unusual demand spike')).not.toBeInTheDocument();
  });

  it('shows an explicit failure state when exception analysis is unavailable', async () => {
    server.use(
      http.get('*/api/v1/exceptions', () =>
        HttpResponse.json({ detail: 'Exception analysis unavailable.' }, { status: 503 }),
      ),
    );

    renderApp(<PlanningExceptionsPage />, '/planning-exceptions');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Planning exceptions could not be loaded.');
  });
});
