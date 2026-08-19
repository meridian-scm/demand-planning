export interface NavigationItem {
  readonly label: string;
  readonly path: string;
  readonly shortLabel: string;
}

export const navigationItems: readonly NavigationItem[] = [
  { label: 'Overview', shortLabel: 'OV', path: '/' },
  { label: 'Demand Explorer', shortLabel: 'DE', path: '/demand-explorer' },
  { label: 'Planning Exceptions', shortLabel: 'PE', path: '/planning-exceptions' },
  { label: 'Forecast Runs', shortLabel: 'FR', path: '/forecast-runs' },
];
