import { apiConfig } from './config';

export function apiUrl(path: `/${string}`): string {
  return `${apiConfig.baseUrl}${path}`;
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

async function responseError(response: Response): Promise<ApiRequestError> {
  let message = `The planning service returned ${response.status}.`;
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === 'string' && payload.detail.trim()) message = payload.detail;
  } catch {
    // Keep the status-based fallback when the response is not JSON.
  }
  return new ApiRequestError(message, response.status);
}

export async function getJson<T>(path: `/${string}`, signal?: AbortSignal): Promise<T> {
  const configuredUrl = apiUrl(path);
  const requestUrl = configuredUrl.startsWith('/')
    ? new URL(configuredUrl, window.location.origin).toString()
    : configuredUrl;
  const request: RequestInit = {
    headers: { Accept: 'application/json' },
  };
  if (signal) request.signal = signal;
  const response = await fetch(requestUrl, request);
  if (!response.ok) {
    throw await responseError(response);
  }
  return (await response.json()) as T;
}

export async function postJson<TRequest, TResponse>(
  path: `/${string}`,
  body: TRequest,
): Promise<TResponse> {
  const configuredUrl = apiUrl(path);
  const requestUrl = configuredUrl.startsWith('/')
    ? new URL(configuredUrl, window.location.origin).toString()
    : configuredUrl;
  const response = await fetch(requestUrl, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as TResponse;
}
