// Persistent access is explicitly opt-in and scoped to this backend.
const key = `ec-token:${(import.meta.env.VITE_API_BASE_URL || 'local').replace(/\/+$/, '')}`;
export function getToken() {
  return localStorage.getItem(key) || sessionStorage.getItem(key) || sessionStorage.getItem('ec-token') || '';
}
export function isRemembered() { return Boolean(localStorage.getItem(key)); }
export function forgetToken() {
  localStorage.removeItem(key);
  sessionStorage.removeItem(key);
  sessionStorage.removeItem('ec-token');
}
export function saveToken(value, remember) {
  forgetToken();
  const token = value.trim();
  if (token) (remember ? localStorage : sessionStorage).setItem(key, token);
}
