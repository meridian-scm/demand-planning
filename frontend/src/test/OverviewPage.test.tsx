import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import OverviewPage from '../pages/OverviewPage';
import { renderApp } from './render';
import { server } from './server';

describe('Overview', () => {
  it('shows demand, reliability, inventory exposure, and priority exceptions', async () => {
    renderApp(<OverviewPage />);

    expect(await screen.findByText('70,991')).toBeVisible();
    expect(screen.getByText('1%')).toBeVisible();
    expect(screen.getByText('36,367')).toBeVisible();
    expect(screen.getByText('21.7%')).toBeVisible();
    expect(screen.getByText('Potential stockout before replenishment')).toBeVisible();
    expect(
      screen.getByRole('img', { name: /portfolio demand chart for All stores/ }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: 'Review model evidence' })).toHaveAttribute(
      'href',
      '/forecast-runs',
    );
  });

  it('updates the complete planning view when a store is selected', async () => {
    const user = userEvent.setup();
    renderApp(<OverviewPage />);
    await screen.findByText('70,991');

    await user.selectOptions(screen.getByLabelText('Overview store'), 'store-001');

    expect(await screen.findByText('14,220')).toBeVisible();
    expect(screen.getByText(/24 Store \+ SKU series/)).toBeVisible();
    expect(
      screen.getByRole('img', { name: /portfolio demand chart for Toronto Central/ }),
    ).toBeVisible();
  });

  it('shows an actionable error state when portfolio evidence fails', async () => {
    server.use(
      http.get('*/api/v1/dashboard/summary', () =>
        HttpResponse.json({ detail: 'Artifact unavailable' }, { status: 503 }),
      ),
    );
    renderApp(<OverviewPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Portfolio overview could not be loaded.',
    );
  });
});
