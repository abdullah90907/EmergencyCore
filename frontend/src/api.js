const API_BASE = ''; // Same-origin server proxy keeps credentials out of the browser.

export async function api(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${API_BASE}/api/v1${path}`, { ...options, headers, signal: options.signal || AbortSignal.timeout(60000) });
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('API returned a non-JSON response. Contact the administrator to check the server proxy');
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status})`);
  return data;
}
