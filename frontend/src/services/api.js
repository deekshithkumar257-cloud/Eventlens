/**
 * Thin client for the EventLens backend.
 * Requests go to the same origin (/api), which the Vite dev/preview server
 * forwards to the FastAPI backend. Override with VITE_API_BASE_URL if needed.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, { status = 0, details = null, network = false } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
    this.network = network;
  }
}

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: 'application/json' },
      ...options,
    });
  } catch {
    throw new ApiError(
      'The EventLens API is unavailable. Start the backend (see README.md) and try again.',
      { network: true },
    );
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  // 502/503/504 from the dev/preview proxy mean the backend is not running.
  if ([502, 503, 504].includes(response.status)) {
    throw new ApiError(
      'The EventLens API is unavailable. Start the backend (see README.md) and try again.',
      { status: response.status, network: true },
    );
  }

  if (!response.ok) {
    const message = body?.error?.message || `Request failed with status ${response.status}.`;
    throw new ApiError(message, { status: response.status, details: body?.error?.details ?? null });
  }
  return body;
}

export const api = {
  health: () => request('/health'),
  stats: () => request('/stats'),
  listAlerts: (params) => request(`/alerts${buildQuery(params)}`),
  getAlert: (alertId) => request(`/alerts/${encodeURIComponent(alertId)}`),
  getTimeline: (alertId) => request(`/alerts/${encodeURIComponent(alertId)}/timeline`),
  listEvents: (params) => request(`/events${buildQuery(params)}`),
  uploadLogs: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('/logs/upload', { method: 'POST', body: form });
  },
  loadSample: () => request('/logs/sample', { method: 'POST' }),
};
