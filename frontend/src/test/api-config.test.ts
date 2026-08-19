import { describe, expect, it } from 'vitest';

import { readApiConfig } from '../api/config';

describe('API configuration', () => {
  it('reads and normalizes the Vite API base URL', () => {
    expect(readApiConfig({ VITE_API_BASE_URL: ' https://api.example.test/ ' })).toEqual({
      baseUrl: 'https://api.example.test',
    });
  });

  it('uses same-origin requests when no API base URL is configured', () => {
    expect(readApiConfig({})).toEqual({ baseUrl: '' });
  });
});
