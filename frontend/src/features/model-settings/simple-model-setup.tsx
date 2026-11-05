'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AudioLines, BookText, CheckCircle2, Clapperboard, ImageIcon, KeyRound, Loader2, PlugZap, Settings2, XCircle } from 'lucide-react';

import {
  apiClient,
  type SimpleCapability,
  type SimpleModelCard,
  type SimpleModelSetupState,
  type SimpleModelSetupTestResult,
} from '@/lib/api-client';
import { BillingSpendCard } from '@/features/model-settings/billing-spend-card';

export const SIMPLE_CAPABILITIES: SimpleCapability[] = ['text', 'image', 'video', 'tts'];
const ICONS = { text: BookText, image: ImageIcon, video: Clapperboard, tts: AudioLines } as const;
const HINTS: Record<SimpleCapability, string> = {
  text: '写剧本、拆分镜',
  image: '生成角色与画面',
  video: '把画面变成镜头',
  tts: '旁白与角色配音',
};

type Draft = { model_id: string; api_key: string; voice: string };

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
  const welcome = useSearchParams()?.get('welcome') === '1';
  const [state, setState] = useState<SimpleModelSetupState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [providerId, setProviderId] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [drafts, setDrafts] = useState<Record<SimpleCapability, Draft>>({
    text: { model_id: '', api_key: '', voice: '' }, image: { model_id: '', api_key: '', voice: '' },
    video: { model_id: '', api_key: '', voice: '' }, tts: { model_id: '', api_key: '', voice: '' },
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
        if (cap === 'tts') capabilities[cap].extra_params = d.voice.trim() ? { default_voice_id: d.voice.trim() } : {};
      }
      const next = await apiClient.saveSimpleModelSetup({ provider_id: providerId || null, api_key: apiKey.trim() || null, capabilities });
      setApiKey('');
      hydrate(next);
      setNotice('已保存。建议点击「测试连接」确认可用。');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const testAll = async () => {
    setTesting(true); setError(''); setNotice('');
    try {
      const out = await apiClient.testSimpleModelSetup();
      setResults(out.results || {});
      hydrate(out.state);
      const values = Object.values(out.results || {});
      const ok = values.filter((r) => r?.success).length;
      setNotice(values.length ? `测试完成：${ok}/${values.length} 项可用` : '还没有可测试的配置，请先保存');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setTesting(false);
    }
  };

  if (loading && !state) {
    return <div className="flex items-center gap-2 p-8 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />正在读取模型设置…</div>;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-2" data-testid="simple-model-setup">
      {welcome && (
        <div data-testid="onboarding-model-nudge" className="rounded-lg border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-800">
          欢迎加入！开始创作前，请先在下方为「文本 / 图片 / 视频 / 配音」各配置一个模型并测试连接；真实计费默认关闭，可在花费卡片中开启并设置上限。
          <Link href="/novels" className="ml-2 font-medium underline">稍后再说，去作品列表 →</Link>
        </div>
      )}
      <header className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">模型设置</h1>
          <p className="mt-1 text-sm text-slate-500">选一个供应商、填一次 API Key，测试通过后所有小说默认使用这里的模型。单本小说可在详情页单独覆盖。</p>
        </div>
        <Link href="/llm-config?section=overview" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-violet-600">
          <Settings2 className="h-4 w-4" />高级设置
        </Link>
      </header>

      {state && (
        <div className={`rounded-xl border px-4 py-3 text-sm ${state.configured && state.verified ? toneClass.ok : toneClass.warn}`} role="status">
          {state.configured && state.verified
            ? '全部就绪：文本、图像、视频、语音均已连接，可以直接「一键生成视频」。'
            : state.configured ? '已填写，尚未全部测试通过。点击「测试连接」检查。' : '尚未完成设置：填写 API Key 并保存后即可开始生成。'}
        </div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" id="model-settings-key">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">供应商</span>
            <select aria-label="供应商" value={providerId} onChange={(e) => chooseProvider(e.target.value)}
              className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900">
              {state?.providers.map((p) => <option key={p.id} value={p.id}>{p.name}{p.recommended ? '（推荐）' : ''}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 flex items-center gap-1 font-medium text-slate-700"><KeyRound className="h-3.5 w-3.5" />API Key</span>
            <input aria-label="API Key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={providerHasKey ? '已保存（出于安全不显示），留空则沿用' : `粘贴 ${provider?.name || '供应商'} 的 API Key`}
              className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900" />
          </label>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        {SIMPLE_CAPABILITIES.map((cap) => {
          const card = state?.capabilities[cap];
          const Icon = ICONS[cap];
          const status = statusOf(card);
          const result = results[cap];
          const draft = drafts[cap];
          const selected = card?.options.find((o) => o.model_id === draft.model_id);
          const otherProvider = selected && selected.provider_id !== providerId;
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
                  {card?.model_id && !card.options.some((o) => o.model_id === card.model_id) && <option value={card.model_id}>{card.model_name || card.model_id}{card.provider_name ? ` · ${card.provider_name}` : ''}（当前）</option>}
                  {card?.options.map((o) => <option key={o.model_id} value={o.model_id}>{o.name} · {o.provider_name}</option>)}
                </select>
              </label>
              {otherProvider && (
                <input aria-label={`${card?.label}单独 API Key`} type="password" autoComplete="off" value={draft.api_key}
                  onChange={(e) => setDrafts((c) => ({ ...c, [cap]: { ...c[cap], api_key: e.target.value } }))}
                  placeholder={`${selected?.provider_name} 的 API Key（已保存则留空）`}
                  className="mt-2 h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" />
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

      <BillingSpendCard />

      {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
      {notice && <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">{notice}</div>}

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={save} disabled={saving || !state}
          className="inline-flex h-10 items-center gap-2 rounded-md bg-violet-600 px-5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50">
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}保存
        </button>
        <button type="button" onClick={testAll} disabled={testing || !state}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
          {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlugZap className="h-4 w-4" />}测试连接
        </button>
        <span className="text-xs text-slate-400">密钥加密保存，任何页面都不会回显。</span>
      </div>
    </div>
  );
}
