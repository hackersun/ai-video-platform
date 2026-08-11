const LEGACY_TOKEN_KEY = 'auth_token';
const LEGACY_USER_KEY = 'user';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

function parseJwtPayload(token: string): { exp?: number } | null {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const padded = payload.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - payload.length % 4) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function getLegacyAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  const token = localStorage.getItem(LEGACY_TOKEN_KEY);
  if (!token) return null;
  const payload = parseJwtPayload(token);
  if (payload?.exp && Date.now() / 1000 >= payload.exp) {
    clearLegacySession();
    return null;
  }
  return token;
}

export function clearLegacySession(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(LEGACY_USER_KEY);
}

export function readCsrfToken(): string | null {
  if (typeof document === 'undefined') return null;
  const item = document.cookie.split('; ').find(value => value.startsWith('csrf_token='));
  return item ? decodeURIComponent(item.slice('csrf_token='.length)) : null;
}

export function buildSessionRequest(options: RequestInit = {}): RequestInit {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  const legacyToken = getLegacyAccessToken();
  if (legacyToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${legacyToken}`);
  }
  const csrfToken = readCsrfToken();
  if (!SAFE_METHODS.has(method) && csrfToken && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', csrfToken);
  }
  return { ...options, credentials: 'include', headers };
}

async function refreshCookieSession(): Promise<boolean> {
  const response = await fetch(`${API_BASE}/auth/refresh`, buildSessionRequest({ method: 'POST' }));
  return response.ok;
}

export async function fetchWithSession(
  url: string,
  options: RequestInit = {},
  retryAfterRefresh = true,
): Promise<Response> {
  let response = await fetch(url, buildSessionRequest(options));
  const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/refresh');
  if (response.status === 401 && retryAfterRefresh && !isAuthEndpoint && await refreshCookieSession()) {
    response = await fetch(url, buildSessionRequest(options));
  }
  return response;
}

export const authApiBase = API_BASE;
