'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AudioLines, BookText, CheckCircle2, ChevronDown, Clapperboard, ImageIcon, KeyRound, Loader2, PlugZap, Settings2, Sparkles, XCircle } from 'lucide-react';

import {
  apiClient,
  type SimpleCapability,
  type SimpleModelCard,
  type SimpleModelSetupState,
  type SimpleModelSetupTestResult,
} from '@/lib/api-client';
import { BillingSpendCard } from '@/features/model-settings/billing-spend-card';
import { friendlyModelName, friendlyProviderName } from '@/lib/model-configs';

/** 真实 Key 检测通过后默认开启真实调用时使用的上限（元）。 */
export const DEFAULT_PIPELINE_CAP_RMB = '50';
export const DEFAULT_USER_CAP_RMB = '200';

export const SIMPLE_CAPABILITIES: SimpleCapability[] = ['text', 'image', 'video', 'tts'];
const ICONS = { text: BookText, image: ImageIcon, video: Clapperboard, tts: AudioLines } as const;
const HINTS: Record<SimpleCapability, string> = {
  text: '写剧本、拆分镜',
  image: '生成角色与画面',
  video: '把画面变成镜头',
  tts: '旁白与角色配音',
};

type Draft = { model_id: string; api_key: string; voice: string; app_id: string };

export function statusOf(card?: SimpleModelCard | null) {
  if (!card || !card.config_id) return { tone: 'empty', text: '未配置' } as const;
  if (card.test_status === 'success') return { tone: 'ok', text: card.fresh ? '连接正常' : '已验证（生成前自动复测）' } as const;
  if (card.test_status === 'failed') return { tone: 'bad', text: '连接失败' } as const;
  if (!card.has_key) return { tone: 'warn', text: '缺少 API Key' } as const;
  return { tone: 'warn', text: '待测试' } as const;
}

const toneClass = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warn: 'border-amber-200 bg-amber-50 text-amber-700',
  bad: 'border-rose-200 bg-rose-50 text-rose-700',
  empty: 'border-slate-200 bg-slate-50 text-slate-500',
} as const;

function errorText(error: unknown) {
  const e = error as { detail?: { message?: string }; message?: string };
  return e?.detail?.message || e?.message || '操作失败，请稍后重试';
}

export function SimpleModelSetup() {
  const router = useRouter();
  const welcome = useSearchParams()?.get('welcome') === '1';
  const [path, setPath] = useState<'trial' | 'key' | null>(null);
  const [showModels, setShowModels] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [billingVersion, setBillingVersion] = useState(0);
  const [state, setState] = useState<SimpleModelSetupState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [providerId, setProviderId] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [drafts, setDrafts] = useState<Record<SimpleCapability, Draft>>({
    text: { model_id: '', api_key: '', voice: '', app_id: '' }, image: { model_id: '', api_key: '', voice: '', app_id: '' },
    video: { model_id: '', api_key: '', voice: '', app_id: '' }, tts: { model_id: '', api_key: '', voice: '', app_id: '' },
  });
  const [results, setResults] = useState<SimpleModelSetupTestResult['results']>({});

  const hydrate = useCallback((raw: SimpleModelSetupState) => {
    // Tolerate partial/malformed payloads (old backend, proxies) instead of crashing the page.
    const value = (raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}) as Partial<SimpleModelSetupState>;
    const next = {
      ...value,
      providers: Array.isArray(value.providers) ? value.providers : [],
      capabilities: value.capabilities && typeof value.capabilities === 'object' ? value.capabilities : {},
    } as SimpleModelSetupState;
    setState(next);
    const primary = next.primary_provider_id || next.providers[0]?.id || '';
    setProviderId((current) => current || primary);
    setDrafts((current) => {
      const out = { ...current };
      for (const cap of SIMPLE_CAPABILITIES) {
        const card = next.capabilities[cap];
        const preset = next.providers.find((p) => p.id === primary)?.presets?.[cap] || '';
        out[cap] = {
          model_id: card?.model_id || current[cap].model_id || preset,
          api_key: '',
          voice: card?.extra_params?.default_voice_id || current[cap].voice || '',
          app_id: card?.extra_params?.app_id || current[cap].app_id || '',
        };
      }
      return out;
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      hydrate(await apiClient.getSimpleModelSetup());
      setError('');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [hydrate]);

  useEffect(() => { load(); }, [load]);

  const provider = useMemo(() => state?.providers.find((p) => p.id === providerId), [state, providerId]);
  const providerHasKey = useMemo(
    () => Boolean(state && SIMPLE_CAPABILITIES.some((c) => state.capabilities[c]?.provider_id === providerId && state.capabilities[c]?.has_key)),
    [state, providerId],
  );

  const chooseProvider = (id: string) => {
    setProviderId(id);
    const next = state?.providers.find((p) => p.id === id);
    if (!next) return;
    setDrafts((current) => {
      const out = { ...current };
      for (const cap of SIMPLE_CAPABILITIES) {
        const preset = next.presets?.[cap];
        if (preset) out[cap] = { ...out[cap], model_id: preset };
      }
      return out;
    });
  };

  const save = async () => {
    if (!state) return;
    setSaving(true); setError(''); setNotice('');
    try {
      const capabilities: Record<string, { model_id: string; api_key?: string; extra_params?: Record<string, string> }> = {};
      for (const cap of SIMPLE_CAPABILITIES) {
        const d = drafts[cap];
        if (!d.model_id) continue;
        capabilities[cap] = { model_id: d.model_id };
        if (d.api_key.trim()) capabilities[cap].api_key = d.api_key.trim();
        if (cap === 'tts') {
          const extra: Record<string, string> = {};
          if (d.voice.trim()) extra.default_voice_id = d.voice.trim();
          if (d.app_id.trim()) extra.app_id = d.app_id.trim();
          capabilities[cap].extra_params = extra;
        }
      }
      const next = await apiClient.saveSimpleModelSetup({ provider_id: providerId || null, api_key: apiKey.trim() || null, capabilities });
      setApiKey('');
      hydrate(next);
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
      return;
    }
    setSaving(false);
    await testAll({ afterSave: true });
  };

  /** 真实 Key 全部检测通过后：默认开启真实调用，并使用默认上限（仅首次开启时写入上限）。 */
  const enableLiveCallsByDefault = async () => {
    try {
      const billing = await apiClient.getBillingSettings();
      if (billing.live_calls_opt_in) return '';
      await apiClient.updateBillingSettings({
        live_calls_opt_in: true,
        per_pipeline_cap_rmb: DEFAULT_PIPELINE_CAP_RMB,
        per_user_cap_rmb: DEFAULT_USER_CAP_RMB,
      });
      setBillingVersion((v) => v + 1);
      return `已开启真实调用：每次生成最多 ¥${DEFAULT_PIPELINE_CAP_RMB}，账户累计最多 ¥${DEFAULT_USER_CAP_RMB}（可在「费用上限」中修改或关闭）。`;
    } catch {
      return '真实调用尚未开启，请在「费用上限」中手动开启。';
    }
  };

  const enableSimulation = async () => {
    setSaving(true); setError(''); setNotice('');
    try {
      const next = await apiClient.saveSimpleModelSetup({ simulation: true, capabilities: {} });
      hydrate(next);
      setNotice('已切换为演示模式（不调用付费接口），不会扣费。');
      return true;
    } catch (e) {
      setError(errorText(e));
      return false;
    } finally {
      setSaving(false);
    }
  };

  /** 免费试用：切到演示模式 → 自动检测 → 直接去导入小说。 */
  const startTrial = async () => {
    setPath('trial');
    if (!(await enableSimulation())) return;
    const ok = await testAll();
    if (ok) router.push('/novels?start=paste');
  };

  const testAll = async (opts: { afterSave?: boolean } = {}) => {
    setTesting(true); setError(''); setNotice('');
    try {
      const out = await apiClient.testSimpleModelSetup();
      setResults(out.results || {});
      hydrate(out.state);
      const values = Object.values(out.results || {});
      const ok = values.filter((r) => r?.success).length;
      const allOk = values.length > 0 && ok === values.length;
      const prefix = opts.afterSave ? '已保存并检测' : '检测完成';
      let message = values.length ? `${prefix}：${ok}/${values.length} 项可用` : '还没有可检测的配置，请先填写 API Key';
      if (allOk && !out.state?.simulation_enabled) {
        const live = await enableLiveCallsByDefault();
        if (live) message += `。${live}`;
      }
      if (!allOk && values.length) setShowModels(true);
      setNotice(message);
      return allOk;
    } catch (e) {
      setError(errorText(e));
      return false;
    } finally {
      setTesting(false);
    }
  };

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash === '#billing-spend') setShowBilling(true);
  }, []);

  if (loading && !state) {
    return <div className="flex items-center gap-2 p-8 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />正在读取模型设置…</div>;
  }

  const busy = saving || testing;
  // 正式环境无演示模式：欢迎页只推「自带 Key」，不暗示免费试用/赠送额度。
  const showByokWelcome = Boolean(welcome && state && !state.configured && path === null && !state.simulation_available);
  const showChooser = Boolean(welcome && state && !state.configured && path === null && state.simulation_available);
  const summary = SIMPLE_CAPABILITIES.map((cap) => {
    const card = state?.capabilities[cap];
    const option = card?.options.find((o) => o.model_id === drafts[cap].model_id);
    const name = option ? friendlyModelName({ ...option, model_name: option.name }, cap) : friendlyModelName(card, cap);
    return `${card?.label || cap}：${name || '未选择'}`;
  }).join(' · ');

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-2" data-testid="simple-model-setup">
      <header className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">模型设置</h1>
          <p className="mt-1 text-sm text-slate-500">填一个 API Key，系统自动配好文本、图片、视频、配音并检测可用性。</p>
        </div>
        <Link href="/llm-config?section=overview" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-violet-600">
          <Settings2 className="h-4 w-4" />高级设置
        </Link>
      </header>

      {showByokWelcome ? (
        <section data-testid="onboarding-byok" className="rounded-2xl border-2 border-violet-300 bg-gradient-to-br from-violet-50 to-white p-8 shadow-sm">
          <div className="mx-auto max-w-xl space-y-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-violet-100 text-violet-700">
              <KeyRound className="h-6 w-6" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">填写 API Key 开始</h2>
            <p className="text-sm leading-6 text-slate-600">
              正式环境<strong>没有免费试用</strong>，也不赠送额度。请粘贴你自己的 API Key；
              检测通过后可开启真实生成（默认每次最多 ¥{DEFAULT_PIPELINE_CAP_RMB}，账户累计上限可在费用设置里调整）。
            </p>
            <button type="button" data-testid="onboarding-byok-start" onClick={() => setPath('key')} disabled={busy}
              className="inline-flex h-11 items-center justify-center rounded-xl bg-violet-600 px-6 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-60">
              开始填写 API Key
            </button>
            <div>
              <Link href="/novels" className="text-sm text-slate-500 underline">稍后再说，去作品列表 →</Link>
            </div>
          </div>
        </section>
      ) : showChooser ? (
        <section data-testid="onboarding-choice" className="grid gap-4 md:grid-cols-2">
          <button type="button" onClick={startTrial} disabled={busy}
            className="flex flex-col items-start gap-2 rounded-2xl border-2 border-violet-300 bg-violet-50 p-6 text-left hover:border-violet-500 disabled:opacity-60">
            <span className="flex items-center gap-2 text-lg font-semibold text-violet-800"><Sparkles className="h-5 w-5" />演示模式（测试环境）</span>
            <span className="text-sm text-violet-700">仅测试/演示环境可用：不需要 API Key、不扣费，用演示素材走完流程。正式环境需自带 Key，无赠送额度。</span>
          </button>
          <button type="button" onClick={() => setPath('key')} disabled={busy}
            className="flex flex-col items-start gap-2 rounded-2xl border-2 border-slate-200 bg-white p-6 text-left hover:border-violet-400 disabled:opacity-60">
            <span className="flex items-center gap-2 text-lg font-semibold text-slate-900"><KeyRound className="h-5 w-5" />我有 API Key</span>
            <span className="text-sm text-slate-600">粘贴一个 Key，自动检测并开启真实生成（默认每次最多 ¥{DEFAULT_PIPELINE_CAP_RMB}）。正式环境必须自带 Key。</span>
          </button>
          <Link href="/novels" className="text-sm text-slate-500 underline md:col-span-2">稍后再说，去作品列表 →</Link>
        </section>
      ) : (
        <>
          {state && (
            <div className={`rounded-xl border px-4 py-3 text-sm ${state.configured && state.verified ? toneClass.ok : toneClass.warn}`} role="status">
              {state.configured && state.verified
                ? '全部就绪：文本、图像、视频、语音均已连接，可以直接「一键生成视频」。'
                : state.configured ? '已填写，尚未全部检测通过。点击「保存并检测」重试。' : '尚未完成设置：请粘贴你自己的 API Key 后点击「保存并检测」（正式环境无免费试用、无赠送额度）。'}
            </div>
          )}

          {state?.configured && state.verified && (
            <div data-testid="model-setup-next-step" className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-800">
              <span>模型已就绪，下一步：粘贴小说，一键生成视频。</span>
              <Link href="/novels?start=paste" className="font-medium underline">下一步：导入小说 →</Link>
            </div>
          )}

          {state?.simulation_available && (
            <section data-testid="model-setup-simulation" className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-800">演示模式（仅测试环境）</div>
                  <p className="mt-0.5 text-slate-500">
                    {state.simulation_enabled
                      ? '当前使用演示模式：生成结果为演示素材，不扣费。正式环境需自带 API Key，无赠送额度。'
                      : '测试环境可用：不需要 API Key、不扣费。正式环境没有免费试用，请粘贴自己的 API Key。'}
                  </p>
                </div>
                <button type="button" onClick={startTrial} disabled={busy || state.simulation_enabled}
                  className="inline-flex h-9 items-center rounded-md border border-slate-300 bg-white px-3 font-medium text-slate-700 hover:border-violet-400 disabled:opacity-60">
                  {state.simulation_enabled ? '已在演示模式' : '进入演示模式'}
                </button>
              </div>
            </section>
          )}

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" id="model-settings-key">
            <div className="grid gap-4 sm:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-slate-700">服务商</span>
                <select aria-label="服务商" value={providerId} onChange={(e) => chooseProvider(e.target.value)}
                  className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900">
                  {state?.providers.map((p) => <option key={p.id} value={p.id}>{p.name}{p.recommended ? '（推荐）' : ''}</option>)}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 flex items-center gap-1 font-medium text-slate-700"><KeyRound className="h-3.5 w-3.5" />API Key</span>
                <input aria-label="API Key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                  placeholder={providerHasKey ? '已保存（出于安全不显示），留空则沿用' : `粘贴 ${provider?.name || '服务商'} 的 API Key`}
                  className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900" />
              </label>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span data-testid="model-setup-summary">已为你选好推荐模型：{summary}</span>
              <button type="button" onClick={() => setShowModels((v) => !v)} aria-expanded={showModels}
                className="inline-flex items-center gap-1 font-medium text-violet-600 hover:underline">
                {showModels ? '收起模型' : '修改模型'}<ChevronDown className={`h-3.5 w-3.5 transition ${showModels ? 'rotate-180' : ''}`} />
              </button>
            </div>
          </section>

          {showModels && (
            <div className="grid gap-4 md:grid-cols-2">
              {SIMPLE_CAPABILITIES.map((cap) => {
                const card = state?.capabilities[cap];
                const Icon = ICONS[cap];
                const status = statusOf(card);
                const result = results[cap];
                const draft = drafts[cap];
                const selected = card?.options.find((o) => o.model_id === draft.model_id);
                const otherProvider = selected && selected.provider_id !== providerId;
                const volcTts = cap === 'tts' && (selected?.provider_id || providerId).toLowerCase().includes('volc');
                const ttsFailed = (result && !result.success) || card?.test_status === 'failed';
                const needAppId = volcTts && (Boolean(draft.app_id) || ttsFailed);
                return (
                  <section key={cap} id={`model-settings-${cap}`} data-testid={`model-card-${cap}`} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="mb-3 flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="rounded-lg bg-violet-50 p-2 text-violet-600"><Icon className="h-4 w-4" /></span>
                        <div><h2 className="font-semibold text-slate-900">{card?.label || cap}</h2><p className="text-xs text-slate-500">{HINTS[cap]}</p></div>
                      </div>
                      <span className={`rounded-full border px-2 py-0.5 text-xs ${toneClass[status.tone]}`}>{status.text}</span>
                    </div>
                    <label className="block text-sm">
                      <span className="mb-1 block text-xs text-slate-500">模型</span>
                      <select aria-label={`${card?.label || cap}模型`} value={draft.model_id}
                        onChange={(e) => setDrafts((c) => ({ ...c, [cap]: { ...c[cap], model_id: e.target.value } }))}
                        className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900">
                        <option value="">不使用</option>
                        {card?.model_id && !card.options.some((o) => o.model_id === card.model_id) && <option value={card.model_id}>{friendlyModelName(card, cap)}{card.provider_name ? ` · ${friendlyProviderName(card)}` : ''}（当前）</option>}
                        {card?.options.map((o) => <option key={o.model_id} value={o.model_id}>{o.name} · {o.provider_name}</option>)}
                      </select>
                    </label>
                    {otherProvider && (
                      <input aria-label={`${card?.label}单独 API Key`} type="password" autoComplete="off" value={draft.api_key}
                        onChange={(e) => setDrafts((c) => ({ ...c, [cap]: { ...c[cap], api_key: e.target.value } }))}
                        placeholder={`${selected?.provider_name} 的 API Key（已保存则留空）`}
                        className="mt-2 h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" />
                    )}
                    {needAppId && (
                      <label className="mt-2 block text-xs text-amber-700">
                        <span className="mb-1 block">火山语音还需要 App ID：火山引擎控制台 → 豆包语音 → 应用管理，复制「APP ID」。</span>
                        <input aria-label="语音 App ID" value={draft.app_id}
                          onChange={(e) => setDrafts((c) => ({ ...c, tts: { ...c.tts, app_id: e.target.value } }))}
                          placeholder="粘贴语音 App ID"
                          className="h-9 w-full rounded-md border-2 border-amber-300 bg-white px-3 text-sm text-slate-900" />
                      </label>
                    )}
                    {cap === 'tts' && (
                      <input aria-label="默认音色" value={draft.voice}
                        onChange={(e) => setDrafts((c) => ({ ...c, tts: { ...c.tts, voice: e.target.value } }))}
                        placeholder="默认音色 ID（可选，留空自动选择）"
                        className="mt-2 h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" />
                    )}
                    {result ? (
                      <p className={`mt-3 flex items-center gap-1 text-xs ${result.success ? 'text-emerald-600' : 'text-rose-600'}`} data-testid={`model-test-${cap}`}>
                        {result.success ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                        {result.message}{result.response_time_ms ? ` · ${result.response_time_ms}ms` : ''}
                      </p>
                    ) : card?.test_message && card.test_status === 'failed' ? (
                      <p className="mt-3 text-xs text-rose-600">{card.test_message}</p>
                    ) : null}
                  </section>
                );
              })}
            </div>
          )}

          {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
          {notice && <div data-testid="model-setup-notice" className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">{notice}</div>}

          <div className="flex flex-wrap items-center gap-3">
            <button type="button" onClick={save} disabled={busy || !state}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-violet-600 px-5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlugZap className="h-4 w-4" />}{testing ? '正在检测…' : '保存并检测'}
            </button>
            <span className="text-xs text-slate-400">密钥加密保存，任何页面都不会回显。</span>
          </div>

          <div>
            <button type="button" onClick={() => setShowBilling((v) => !v)} aria-expanded={showBilling}
              className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-violet-600">
              费用上限（可选）<ChevronDown className={`h-4 w-4 transition ${showBilling ? 'rotate-180' : ''}`} />
            </button>
            {showBilling && <div className="mt-3"><BillingSpendCard refreshToken={billingVersion} /></div>}
          </div>
        </>
      )}
    </div>
  );
}
