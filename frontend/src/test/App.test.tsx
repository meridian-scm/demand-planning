import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { App } from '../App';
import { renderApp } from './render';

describe('Meridian application shell', () => {
  it.each([
    ['/', 'Overview'],
    ['/demand-explorer', 'Demand Explorer'],
    ['/planning-exceptions', 'Planning Exceptions'],
    ['/forecast-runs', 'Forecast Runs'],
  ])('renders %s as the %s route', async (route, heading) => {
    renderApp(<App />, route);

    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument();
  });

  it('navigates between the main planner routes', async () => {
    const user = userEvent.setup();
    renderApp(<App />);

    await user.click(await screen.findByRole('link', { name: 'Demand Explorer' }));

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Demand Explorer' }),
    ).toBeInTheDocument();
  });

  it('exposes accessible navigation and a main-content shortcut', async () => {
    renderApp(<App />);

    expect(
      await screen.findByRole('navigation', { name: 'Primary navigation' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute(
      'href',
      '#main-content',
    );
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content');
  });

  it('renders an explicit not-found state', async () => {
    renderApp(<App />, '/not-a-planning-view');

    expect(
      await screen.findByRole('heading', { name: 'That planning view does not exist.' }),
    ).toBeInTheDocument();
  });
});
