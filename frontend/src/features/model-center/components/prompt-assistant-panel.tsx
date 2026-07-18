'use client';

import { Eye, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import {
  getPromptSkillVariableGuide,
  listPromptSkillOptimizationModelConfigs,
} from '@/lib/prompt-skills-api';
import {
  getConfigsByCapability,
  getDefaultConfigForCapability,
  modelStatusLabel,
  type SavedModelConfig,
} from '@/lib/model-configs';

import { modelCenterApi } from '../api';
import type {
  PromptOptimizationResult,
  PromptPreviewResult,
  PromptProfileVersionDetail,
} from '../types';

const LOCAL_RULES_MODEL_ID = '__local_rules__';

export function PromptAssistantPanel({
  profileId,
  task,
  version,
  taskTemplate,
  onApply,
}: {
  profileId: string;
  task: string;
  version: PromptProfileVersionDetail;
  taskTemplate: string;
  onApply: (content: string) => void;
}) {
  const [optimization, setOptimization] = useState<PromptOptimizationResult | null>(null);
  const [preview, setPreview] = useState<PromptPreviewResult | null>(null);
  const [pending, setPending] = useState<'optimize' | 'preview' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [modelConfigId, setModelConfigId] = useState(LOCAL_RULES_MODEL_ID);
  const [guideNames, setGuideNames] = useState<string[]>([]);
  const textModels = useMemo(() => getConfigsByCapability(modelConfigs, 'text'), [modelConfigs]);
  const selectedModel = textModels.find((model) => model.id === modelConfigId) || null;
  const selectedModelBlocked = Boolean(selectedModel && (
    selectedModel.test_status !== 'success' || selectedModel.key_available === false
  ));
  const variables = useMemo(
    () => Array.from(new Set(Array.from(taskTemplate.matchAll(/\{([^}]+)\}/g)).map((match) => match[1].trim()))).filter(Boolean),
    [taskTemplate],
  );
  useEffect(() => {
    void listPromptSkillOptimizationModelConfigs().then((configs) => {
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      setModelConfigId(getDefaultConfigForCapability(list, 'text')?.id || LOCAL_RULES_MODEL_ID);
    }).catch(() => setModelConfigs([]));
    void getPromptSkillVariableGuide(task).then((guide) => {
      setGuideNames(guide.items.map((item) => item.name));
    }).catch(() => setGuideNames([]));
  }, [task]);
  const optimize = async () => {
    try {
      setPending('optimize'); setError(null);
      setOptimization(await modelCenterApi.optimizePromptProfile(profileId, {
        version_id: version.id, mode: 'productionize', model_config_id: modelConfigId,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'AI 优化失败');
    } finally { setPending(null); }
  };
  const runPreview = async () => {
    try {
      setPending('preview'); setError(null);
      setPreview(await modelCenterApi.previewPromptProfile(profileId, {
        version_id: version.id, task_template: taskTemplate, context: {},
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Prompt 预览失败');
    } finally { setPending(null); }
  };
  return <section className="rounded-lg border border-violet-400/20 bg-violet-500/[0.06] p-4"><h3 className="text-sm font-semibold text-white">AI 辅助优化与预览</h3><p className="mt-1 text-xs text-slate-400">AI 结果先进入建议区，只有点击“应用优化结果”才会写入当前草稿。</p><label className="mt-3 block text-xs text-slate-400">优化模型<select aria-label="优化模型" value={modelConfigId} onChange={(event) => setModelConfigId(event.target.value)} className="model-center-input mt-1 w-full"><option value={LOCAL_RULES_MODEL_ID}>仅本地规则（不调用模型）</option>{textModels.map((model) => <option key={model.id} value={model.id}>{model.name} · {modelStatusLabel(model.test_status)}</option>)}</select></label>{selectedModelBlocked && <p className="mt-2 text-xs text-amber-200">当前模型未验证或 Key 不可用，请切换模型或<Link href="/llm-config?section=connections" className="ml-1 underline">修复连接</Link>。</p>}<div className="mt-3 rounded-md border border-white/10 bg-black/10 p-2 text-xs text-slate-400"><span className="font-medium text-slate-300">变量指导：</span>{variables.length ? variables.map((name) => <span key={name} className={`ml-2 ${guideNames.includes(name) ? 'text-emerald-200' : 'text-amber-200'}`}>{`{${name}}`}{guideNames.includes(name) ? ' 已识别' : ' 待补充说明'}</span>) : <span className="ml-2">当前正文没有变量占位符</span>}</div><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => void optimize()} disabled={pending !== null || selectedModelBlocked} className="model-center-primary"><Sparkles className="h-3.5 w-3.5" />{pending === 'optimize' ? '优化中' : 'AI 优化'}</button><button type="button" onClick={() => void runPreview()} disabled={pending !== null} className="model-center-quiet"><Eye className="h-3.5 w-3.5" />{pending === 'preview' ? '预览中' : '预览 Prompt'}</button></div>{optimization && <div className="mt-3 rounded-md border border-violet-300/20 bg-black/15 p-3"><p className="text-xs font-medium text-violet-100">优化建议 · {optimization.source === 'ai_model' ? '已配置文本模型' : '本地规则'}</p><pre className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-300">{optimization.optimized_content}</pre>{optimization.warnings.map((warning) => <p key={warning} className="mt-1 text-xs text-amber-200">{warning}</p>)}<button type="button" onClick={() => onApply(optimization.optimized_content)} className="model-center-quiet mt-3">应用优化结果</button></div>}{preview && <div className="mt-3 rounded-md border border-cyan-300/20 bg-black/15 p-3"><p className="text-xs font-medium text-cyan-100">预览结果</p><pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">{preview.prompt}</pre></div>}{error && <p className="mt-3 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{error}</p>}</section>;
}
