export async function api(path, options = {}) {
  const headers = { ...options.headers };
  const token = sessionStorage.getItem('ec-token');
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api/v1${path}`, { ...options, headers, signal: options.signal || AbortSignal.timeout(60000) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status})`);
  return data;
}
