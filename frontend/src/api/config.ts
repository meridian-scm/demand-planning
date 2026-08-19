/** Browser API configuration with one environment-controlled backend origin. */

export interface ApiEnvironment {
  readonly VITE_API_BASE_URL?: string;
}

export interface ApiConfig {
  readonly baseUrl: string;
}

export function readApiConfig(environment: ApiEnvironment = import.meta.env): ApiConfig {
  const configuredBaseUrl = environment.VITE_API_BASE_URL?.trim();
  return {
    baseUrl: configuredBaseUrl ? configuredBaseUrl.replace(/\/+$/, '') : '',
  };
}

export const apiConfig = readApiConfig();
