'use client';

import type { CertificationCandidate } from '../types';

export function ModelVersionPicker({
  candidates, value, loading, onChange,
}: {
  candidates: CertificationCandidate[];
  value: string;
  loading: boolean;
  onChange: (candidateId: string) => void;
}) {
  return <label className="text-xs text-slate-400">兼容模型与连接<select aria-label="兼容模型与连接" required value={value} onChange={(event) => onChange(event.target.value)} className="model-center-input mt-1 w-full"><option value="">{loading ? '正在读取兼容组合…' : candidates.length ? '选择服务端验证的兼容组合' : '没有可用的兼容组合'}</option>{candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.profile.name} · {candidate.profile.api_model_id} · {candidate.connection.name} · {candidate.profile.provider_name}</option>)}</select></label>;
}
