import { apiConfig } from './config';

export function apiUrl(path: `/${string}`): string {
  return `${apiConfig.baseUrl}${path}`;
}
