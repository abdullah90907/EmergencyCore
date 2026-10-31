const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export async function api(path, options = {}) {
  if (import.meta.env.PROD && !API_BASE) throw new Error('Deployment configuration missing: set VITE_API_BASE_URL to the HTTPS backend origin and rebuild');
  const headers = { ...options.headers };
  const token = sessionStorage.getItem('ec-token');
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${API_BASE}/api/v1${path}`, { ...options, headers, signal: options.signal || AbortSignal.timeout(60000) });
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('API returned a non-JSON response. Check VITE_API_BASE_URL and backend availability');
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status})`);
  return data;
}
