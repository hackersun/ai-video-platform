'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { Cpu, Loader2, Pencil } from 'lucide-react';

import { apiClient, type SimpleCapability, type SimpleModelSetupState } from '@/lib/api-client';
import { SIMPLE_CAPABILITIES, statusOf } from './simple-model-setup';

type Props = {
  novelId: string;
  /** 本小说各能力实际生效的配置 id（覆盖优先，否则继承全局默认）。 */
  onEffectiveChange?: (effective: Partial<Record<SimpleCapability, string | null>>) => void;
};

export function NovelModelOverrides({ novelId, onEffectiveChange }: Props) {
  const [state, setState] = useState<SimpleModelSetupState | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const apply = useCallback((next: SimpleModelSetupState) => {
    setState(next);
    const eff: Partial<Record<SimpleCapability, string | null>> = {};
    for (const cap of SIMPLE_CAPABILITIES) eff[cap] = next.novel_effective?.[cap]?.config_id ?? null;
    onEffectiveChange?.(eff);
  }, [onEffectiveChange]);

  useEffect(() => {
    let alive = true;
    apiClient.getSimpleModelSetup(novelId)
      .then((next) => { if (alive) apply(next); })
      .catch((e) => { if (alive) setError(e?.message || '读取模型设置失败'); });
    return () => { alive = false; };
  }, [novelId, apply]);

  const change = async (cap: SimpleCapability, configId: string) => {
    setSaving(true); setError('');
    try {
      apply(await apiClient.setNovelModelOverrides(novelId, { [cap]: configId || null }));
    } catch (e: any) {
      setError(e?.detail?.message || e?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (!state) {
    return <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500" data-testid="novel-model-line">
      {error || '正在读取模型设置…'}
    </div>;
  }

  const overridden = SIMPLE_CAPABILITIES.filter((c) => state.novel_overrides?.[c]);
  return (
    <section className="rounded-xl border border-slate-200 bg-white px-4 py-3" data-testid="novel-model-line">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <span className="inline-flex items-center gap-1.5 font-medium text-slate-700"><Cpu className="h-4 w-4 text-violet-600" />
          {overridden.length ? `本小说覆盖了 ${overridden.length} 项模型` : '使用全局模型设置'}
        </span>
        {SIMPLE_CAPABILITIES.map((cap) => {
          const card = state.novel_effective?.[cap];
          const st = statusOf(card);
          return <span key={cap} className="text-slate-500">
            {card?.label}：<span className={st.tone === 'ok' ? 'text-slate-800' : 'text-amber-600'}>{card?.model_name || '未配置'}</span>
            {state.novel_overrides?.[cap] ? <span className="ml-1 text-xs text-violet-600">(覆盖)</span> : null}
          </span>;
        })}
        <span className="ml-auto flex items-center gap-3">
          <button type="button" onClick={() => setEditing((v) => !v)} className="inline-flex items-center gap-1 text-violet-600 hover:underline">
            <Pencil className="h-3.5 w-3.5" />{editing ? '收起' : '本小说单独设置'}
          </button>
          <Link href="/llm-config" className="text-slate-500 hover:text-violet-600">模型设置</Link>
        </span>
      </div>
      {editing && (
        <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-2 lg:grid-cols-4">
          {SIMPLE_CAPABILITIES.map((cap) => (
            <label key={cap} className="block text-xs text-slate-500">
              {state.capabilities[cap]?.label}
              <select aria-label={`本小说${state.capabilities[cap]?.label}模型`} disabled={saving}
                value={state.novel_overrides?.[cap] || ''} onChange={(e) => change(cap, e.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-900">
                <option value="">跟随全局（{state.capabilities[cap]?.model_name || '未配置'}）</option>
                {state.novel_choices?.[cap]?.map((c) => <option key={c.config_id} value={c.config_id}>{c.model_name} · {c.name}</option>)}
              </select>
            </label>
          ))}
          {saving && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
        </div>
      )}
      {error && <p role="alert" className="mt-2 text-xs text-rose-600">{error}</p>}
    </section>
  );
}
