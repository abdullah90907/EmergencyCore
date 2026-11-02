// Server-only environment variables. Never prefix these with VITE_.
export default { async fetch(request) {
  const fail = (status, message) => Response.json({ error: { message } }, { status, headers: { 'Cache-Control': 'no-store' } });
  const base = process.env.BACKEND_API_URL;
  const token = process.env.API_TOKEN;
  if (!base || !token) return fail(503, 'Service connection is not configured. Contact the administrator.');
  const incoming = new URL(request.url);
  const route = incoming.searchParams.get('route') || '';
  if (!/^[a-zA-Z0-9_/-]+$/.test(route) || route.split('/').some(p => p === '..')) return fail(400, 'Invalid API path');
  if (!['GET', 'HEAD', 'POST', 'PATCH'].includes(request.method)) return fail(405, 'Method not allowed');
  // Browser callers must originate from this application. Non-browser access is public.
  if (request.headers.get('sec-fetch-site') === 'cross-site') return fail(403, 'Cross-site request rejected');
  const origin = request.headers.get('origin');
  if (origin && origin !== incoming.origin) return fail(403, 'Cross-site request rejected');
  try {
    const backend = new URL(base);
    if (backend.protocol !== 'https:' || backend.username || backend.password) return fail(503, 'Invalid service configuration');
    const target = new URL('/api/v1/' + route, backend.origin);
    incoming.searchParams.delete('route');
    target.search = incoming.searchParams.toString();
    const headers = new Headers({ Authorization: `Bearer ${token}` });
    for (const name of ['content-type', 'last-event-id']) {
      if (request.headers.has(name)) headers.set(name, request.headers.get(name));
    }
    const response = await fetch(target, {
      method: request.method, headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer(),
      redirect: 'error', signal: AbortSignal.timeout(55000),
    });
    return new Response(response.body, { status: response.status, headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
      'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    } });
  } catch { return fail(502, 'Backend temporarily unavailable. Please retry shortly.'); }
} };
