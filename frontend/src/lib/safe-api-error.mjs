const HASH = /^[0-9a-f]{64}$/;

export function formatSafeApiErrorDetail(detail, fallback) {
  if (!detail || typeof detail !== 'object') return fallback;
  const code = typeof detail.code === 'string' ? detail.code : '';
  const message = typeof detail.message === 'string' ? detail.message : '';
  const fields = Array.isArray(detail.conflict_fields) ? detail.conflict_fields.flatMap((item) => {
    if (!item || typeof item.category !== 'string' || typeof item.field !== 'string' ||
        !Array.isArray(item.value_hashes) || !item.value_hashes.length ||
        !item.value_hashes.every((value) => typeof value === 'string' && HASH.test(value))) return [];
    return [`${item.category}/${item.field}=${item.value_hashes.join(',')}`];
  }) : [];
  return [code, message, ...fields].filter(Boolean).join(' · ') || fallback;
}
