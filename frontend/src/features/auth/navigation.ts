export function loginPathFor(pathname: string, search = ''): string {
  const target = `${pathname || '/'}${search || ''}`;
  return `/login?next=${encodeURIComponent(target)}`;
}

export function safeLoginDestination(search: string): string {
  const requested = new URLSearchParams(search).get('next');
  if (!requested || !requested.startsWith('/')) {
    return '/dashboard';
  }

  const localOrigin = 'https://local.invalid';
  const destination = new URL(requested, localOrigin);
  if (destination.origin !== localOrigin) return '/dashboard';
  return `${destination.pathname}${destination.search}${destination.hash}`;
}
