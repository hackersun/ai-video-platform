/** Cookie-first authenticated fetch with one-cycle legacy Bearer compatibility. */

import { clearLegacySession, fetchWithSession } from './auth-session';

const PUBLIC_PATHS = ['/', '/login', '/register', '/forgot-password', '/reset-password', '/verify-email'];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(path => pathname === path || pathname.startsWith(`${path}/`));
}

function redirectAfterUnauthorized(): void {
  if (typeof window === 'undefined') return;
  clearLegacySession();
  if (!isPublicPath(window.location.pathname)) window.location.href = '/login';
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const response = await fetchWithSession(url, options);
  if (response.status === 401) redirectAfterUnauthorized();
  return response;
}

export async function fetchJsonWithAuth<T = unknown>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetchWithAuth(url, options);
  if (!response.ok) {
    const fallback = `请求失败（${response.status}）`;
    const payload = await response.json().catch(() => null) as { detail?: string; message?: string } | null;
    throw new Error(payload?.detail || payload?.message || fallback);
  }
  return response.json();
}
