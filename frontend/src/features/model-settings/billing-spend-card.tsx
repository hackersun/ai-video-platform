'use client';

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Wallet } from 'lucide-react';

import { apiClient, type BillingSettings } from '@/lib/api-client';

function errorText(error: unknown) {
  const e = error as { detail?: { message?: string }; message?: string };
  return e?.detail?.message || e?.message || '操作失败，请稍后重试';
}

/** 模型设置页：用量 / 上限 / 真实调用开关（R03）。 */
export function BillingSpendCard() {
  const [settings, setSettings] = useState<BillingSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [userCap, setUserCap] = useState('');
  const [pipeCap, setPipeCap] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = await apiClient.getBillingSettings();
      setSettings(next);
      setUserCap(next.per_user_cap_rmb);
      setPipeCap(next.per_pipeline_cap_rmb);
      setError('');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const save = async (patch: Partial<BillingSettings>) => {
    setSaving(true);
    try {
      const next = await apiClient.updateBillingSettings({
        live_calls_opt_in: patch.live_calls_opt_in,
        per_user_cap_rmb: patch.per_user_cap_rmb,
        per_pipeline_cap_rmb: patch.per_pipeline_cap_rmb,
      });
      setSettings(next);
      setUserCap(next.per_user_cap_rmb);
      setPipeCap(next.per_pipeline_cap_rmb);
      setError('');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const used = Number(settings?.used_rmb || 0);
  const cap = Number(settings?.per_user_cap_rmb || 0) || 1;
  const pct = Math.min(100, Math.round((used / cap) * 100));

  return (
    <section id="billing-spend" data-testid="billing-spend-card" className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded-lg bg-amber-50 p-2 text-amber-700"><Wallet className="h-4 w-4" /></span>
          <div>
            <h2 className="font-semibold text-slate-900">费用与真实调用</h2>
            <p className="text-xs text-slate-500">开启后才会向供应商发起付费调用；关闭时一键成片会提示先到这里处理。</p>
          </div>
        </div>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
      </div>

      {settings && (
        <>
          <div className="mb-3">
            <div className="mb-1 flex justify-between text-xs text-slate-600">
              <span>已用 ¥{settings.used_rmb}</span>
              <span>上限 ¥{settings.per_user_cap_rmb}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100" aria-label={`已用 ${pct}%`}>
              <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${pct}%` }} />
            </div>
            <p className="mt-1 text-xs text-slate-450 text-slate-500">单次流水线上限 ¥{settings.per_pipeline_cap_rmb} · 假数据不计入</p>
          </div>

          <label className="flex items-start gap-2 text-sm text-slate-800">
            <input
              type="checkbox"
              aria-label="开启真实模型调用"
              checked={Boolean(settings.live_calls_opt_in)}
              disabled={saving}
              onChange={(e) => {
                if (e.target.checked) {
                  if (!window.confirm('开启后将按供应商实际计费，并受本页费用上限约束。确认开启？')) {
                    e.target.checked = false;
                    return;
                  }
                }
                void save({ live_calls_opt_in: e.target.checked });
              }}
              className="mt-1"
            />
            <span>
              开启真实模型调用
              {settings.opted_in_at ? <span className="ml-2 text-xs text-slate-400">已于 {settings.opted_in_at} 开启</span> : null}
            </span>
          </label>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-slate-500">账户上限（元）</span>
              <input
                aria-label="账户费用上限"
                value={userCap}
                onChange={(e) => setUserCap(e.target.value)}
                onBlur={() => { if (userCap !== settings.per_user_cap_rmb) void save({ per_user_cap_rmb: userCap }); }}
                className="h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-slate-500">单次流水线上限（元）</span>
              <input
                aria-label="流水线费用上限"
                value={pipeCap}
                onChange={(e) => setPipeCap(e.target.value)}
                onBlur={() => { if (pipeCap !== settings.per_pipeline_cap_rmb) void save({ per_pipeline_cap_rmb: pipeCap }); }}
                className="h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
              />
            </label>
          </div>
        </>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-rose-600">{error}</p>}
    </section>
  );
}
