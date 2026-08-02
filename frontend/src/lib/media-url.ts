const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1')
  .replace(/\/api\/v1\/?$/, '');

export function toMediaUrl(url?: string | null) {
  const value = url?.trim();
  if (!value) return '';
  if (/^(?:https?:|blob:|data:)/i.test(value)) return value;
  return `${API_ORIGIN}${value.startsWith('/') ? value : `/${value}`}`;
}
