'use client';

import { X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { modelCenterApi } from '../api';
import type {
  ModelBindingInput,
  ModelBindingView,
  ModelCapability,
  ModelCatalogView,
  ModelConnectionView,
} from '../types';

const tasks: Array<{ key: string; label: string; capability: ModelCapability }> = [
  { key: 'script_generation', label: '小说理解与分镜', capability: 'text_generation' },
  { key: 'shot_vision', label: '镜头视觉分析', capability: 'vision_analysis' },
  { key: 'shot_image', label: '参考资产', capability: 'image_generation' },
  { key: 'shot_video', label: '镜头视频', capability: 'video_generation' },
  { key: 'shot_speech', label: '独立配音', capability: 'speech_generation' },
  { key: 'shot_subtitle', label: '字幕', capability: 'subtitle_generation' },
  { key: 'workflow_render', label: '成片合成', capability: 'media_render' },
  { key: 'workflow_storage', label: '交付存储', capability: 'object_storage' },
];

type BindingEditorProps = {
  binding?: ModelBindingView;
  onClose: () => void;
  onSave: (input: ModelBindingInput) => Promise<void>;
};

export function BindingEditor({ binding, onClose, onSave }: BindingEditorProps) {
  const initialTask = tasks.find((item) => item.key === binding?.task) || tasks[3];
  const [task, setTask] = useState(binding?.task || initialTask.key);
  const [capability, setCapability] = useState<ModelCapability>(binding?.capability || initialTask.capability);
  const [models, setModels] = useState<ModelCatalogView[]>([]);
  const [connections, setConnections] = useState<ModelConnectionView[]>([]);
  const [profileId, setProfileId] = useState(binding?.profile_version_id || '');
  const [connectionId, setConnectionId] = useState(binding?.connection_id || '');
  const [priority, setPriority] = useState(binding?.priority ?? 100);
  const [routePolicy, setRoutePolicy] = useState(binding?.route_policy || 'single');
  const [fallbackProfileId, setFallbackProfileId] = useState(binding?.fallback_profile_version_ids[0] || '');
  const [active, setActive] = useState(binding?.is_active ?? true);
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([
      modelCenterApi.listCatalog(1, 100, { capability }),
      modelCenterApi.listConnections(1, 100),
    ]).then(([catalog, connectionPage]) => {
      const candidates = catalog.items.filter((item) => item.profile_version_id);
      setModels(candidates);
      setConnections(connectionPage.items);
      setProfileId((current) => candidates.some((item) => item.profile_version_id === current)
        ? current : candidates[0]?.profile_version_id || '');
    }).catch((failure) => setError(failure instanceof Error ? failure.message : '无法读取兼容模型'));
  }, [capability]);

  const selectedModel = models.find((model) => model.profile_version_id === profileId);
  const matchingConnections = useMemo(() => connections.filter(
    (connection) => connection.enabled && connection.provider_id === selectedModel?.provider_id,
  ), [connections, selectedModel?.provider_id]);
  const fallbackModels = models.filter((model) => model.profile_version_id !== profileId);

  useEffect(() => {
    setConnectionId((current) => matchingConnections.some((item) => item.id === current)
      ? current : matchingConnections[0]?.id || '');
  }, [matchingConnections]);
  useEffect(() => {
    if (routePolicy !== 'pre_submit_fallback') setFallbackProfileId('');
  }, [routePolicy]);

  const changeTask = (value: string) => {
    const selected = tasks.find((item) => item.key === value);
    setTask(value);
    if (selected) setCapability(selected.capability);
  };
  const save = async () => {
    try {
      setPending(true);
      setError(null);
      await onSave({
        scope_type: 'user', scope_id: binding?.scope_id || '', task, capability,
        profile_version_id: profileId, connection_id: connectionId, priority,
        route_policy: routePolicy,
        fallback_profile_version_ids: fallbackProfileId ? [fallbackProfileId] : [],
        is_active: active, reason,
      });
      onClose();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '能力绑定保存失败');
    } finally {
      setPending(false);
    }
  };
  const fallbackMissing = routePolicy === 'pre_submit_fallback' && !fallbackProfileId;

  return <div role="dialog" aria-modal="true" aria-label={binding ? '编辑能力绑定' : '新建能力绑定'} className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8">
    <div className="mx-auto max-w-2xl rounded-xl border border-white/15 bg-slate-900 p-5">
      <header className="flex items-start justify-between">
        <div><h2 className="text-xl font-semibold text-white">{binding ? '编辑能力绑定' : '新建能力绑定'}</h2><p className="mt-1 text-sm text-slate-400">只显示能力匹配的已发布模型，以及同提供方的已认证连接。</p></div>
        <button type="button" aria-label="关闭绑定编辑器" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button>
      </header>
      {binding && <p className="mt-4 rounded-lg border border-amber-300/20 bg-amber-500/[0.08] px-3 py-2 text-xs text-amber-100">保存后将影响 {binding.affected_recipes} 个生产方案；系统将使用修订号防止覆盖他人修改。</p>}
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-400">业务任务<select aria-label="业务任务" value={task} onChange={(event) => changeTask(event.target.value)} className="model-center-input mt-1 w-full">{tasks.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <label className="text-xs text-slate-400">任务能力<select aria-label="任务能力" value={capability} onChange={(event) => setCapability(event.target.value as ModelCapability)} className="model-center-input mt-1 w-full">{tasks.map((item) => <option key={item.capability} value={item.capability}>{item.capability}</option>)}</select></label>
        <label className="text-xs text-slate-400">模型版本<select aria-label="模型版本" value={profileId} onChange={(event) => setProfileId(event.target.value)} className="model-center-input mt-1 w-full">{models.map((model) => <option key={model.profile_version_id} value={model.profile_version_id || ''}>{model.model_name} · {model.api_model_id}</option>)}</select></label>
        <label className="text-xs text-slate-400">模型连接<select aria-label="模型连接" value={connectionId} onChange={(event) => setConnectionId(event.target.value)} className="model-center-input mt-1 w-full">{matchingConnections.map((connection) => <option key={connection.id} value={connection.id}>{connection.name} · {connection.provider_name}</option>)}</select></label>
        <label className="text-xs text-slate-400">优先级<input aria-label="优先级" type="number" min={0} max={10000} value={priority} onChange={(event) => setPriority(Number(event.target.value))} className="model-center-input mt-1 w-full" /></label>
        <label className="text-xs text-slate-400">路由策略<select aria-label="路由策略" value={routePolicy} onChange={(event) => setRoutePolicy(event.target.value)} className="model-center-input mt-1 w-full"><option value="single">单模型，不自动重试</option><option value="pre_submit_fallback">仅提交前失败时降级</option><option value="status_poll_only">提交后只轮询状态</option></select></label>
        {routePolicy === 'pre_submit_fallback' && <label className="text-xs text-slate-400 sm:col-span-2">备用模型<select aria-label="备用模型" value={fallbackProfileId} onChange={(event) => setFallbackProfileId(event.target.value)} className="model-center-input mt-1 w-full"><option value="">请选择同能力的备用模型</option>{fallbackModels.map((model) => <option key={model.profile_version_id} value={model.profile_version_id || ''}>{model.model_name} · {model.api_model_id}</option>)}</select></label>}
        <label className="flex items-center gap-2 text-sm text-slate-200 sm:col-span-2"><input aria-label="启用此绑定" type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />启用此绑定</label>
      </div>
      <input aria-label="操作原因" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="说明为何建立或调整此路由" className="model-center-input mt-3 w-full" />
      {!matchingConnections.length && <p className="mt-3 text-xs text-amber-200">没有同提供方的已认证连接，请先到“模型连接”完成测试。</p>}
      {error && <p className="mt-3 text-xs text-rose-200">{error}</p>}
      <div className="mt-5 flex justify-end"><button type="button" disabled={pending || !profileId || !connectionId || fallbackMissing || reason.trim().length < 2} onClick={() => void save()} className="model-center-primary">{binding ? '保存绑定修改' : '保存能力绑定'}</button></div>
    </div>
  </div>;
}
