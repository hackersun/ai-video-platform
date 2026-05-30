'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { apiClient } from '@/lib/api-client';
import {
  AlertCircle,
  CheckCircle,
  Cloud,
  Edit2,
  Film,
  KeyRound,
  Layers,
  Loader2,
  PlugZap,
  RefreshCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  TestTube,
  Trash2,
  Users,
  Workflow,
  XCircle,
} from 'lucide-react';

type ExternalProvider = {
  id: string;
  name: string;
  name_cn?: string;
  api_type: string;
  base_url?: string;
  auth_type?: string;
  capabilities?: string[];
  supported_models?: Array<{ id: string; name?: string; capabilities?: string[] }>;
};

type ExternalConfig = {
  id: string;
  provider_id: string;
  provider_name: string;
  provider_key: string;
  api_type: string;
  name: string;
  custom_base_url?: string;
  timeout: number;
  retry_count: number;
  is_default: boolean;
  is_active: boolean;
  test_status?: string;
  test_message?: string;
  extra_config?: Record<string, any>;
};

const TYPE_LABELS: Record<string, string> = {
  audio_video: '音视频直生',
  workflow: '工作流',
  render: '渲染',
  lip_sync: '口型',
  storage: '对象存储/CDN',
  video: '视频',
  text: '文本',
};

const TYPE_ICONS: Record<string, any> = {
  audio_video: Film,
  workflow: Workflow,
  render: Cloud,
  lip_sync: Users,
  storage: Cloud,
  video: Film,
  text: SlidersHorizontal,
};

const STATUS_LABELS: Record<string, string> = {
  success: '可用',
  configured: '已配置',
  pending: '待测试',
  failed: '失败',
};

const OPTIONAL_CAPABILITIES = [
  'Sora/Veo 音视频',
  'ComfyUI 工作流',
  'FFmpeg 云渲染',
  '资产版本锁',
  '关键帧',
  '多视图角色参考',
  '公网参考图/CDN',
  '口型/唇形',
  '多人审核',
];

const USAGE_STEPS = [
  {
    title: '公网参考图交付',
    path: '/production-adapters',
    detail: '配置对象存储/CDN后，本地角色头像、镜头参考图和资产参考图会被映射为公网 URL，云端图生视频可以真正读取这些参考图。',
    badge: '消费 /video/generate',
  },
  {
    title: '单镜头直生音视频',
    path: '/video-generation',
    detail: '在视频生成页切换到“直生音视频”，选择外部适配配置后，会提交小说、章节、分镜、镜头、对白字幕、资产锁、关键帧、多视图和口型参数。',
    badge: '消费 /media/generate',
  },
  {
    title: '镜头生产上下文',
    path: '/shots',
    detail: '在镜头管理中维护资产版本锁、关键帧、多视图角色参考、口型设置和审核状态；这些上下文会被直生音视频任务读取。',
    badge: '消费 /shots/{id}/production-context',
  },
  {
    title: '首集批量生成',
    path: '/workflow',
    detail: '在 workflow 的视频步骤使用“批量直生音视频”，按分镜镜头批量创建音视频草稿和字幕轨，继续进入连续成片和导出。',
    badge: '消费 /workflow/{id}/generate-media-batch',
  },
  {
    title: '云渲染/字幕烧录',
    path: '/workflow',
    detail: '在 workflow 合成/导出阶段选择 FFmpeg 云渲染配置，渲染器会消费 render manifest、timeline、SRT 和字幕烧录设置。',
    badge: '消费 /workflow/{id}/render',
  },
];

const emptyForm = {
  providerId: '',
  name: '',
  apiKey: '',
  apiSecret: '',
  baseUrl: '',
  timeout: 60,
  retryCount: 3,
  submitPath: '',
  healthPath: '',
  description: '',
  isDefault: false,
  extraJson: '{}',
};

export default function ProductionAdaptersPage() {
  const configFormRef = useRef<HTMLDivElement | null>(null);
  const configNameInputRef = useRef<HTMLInputElement | null>(null);
  const [providers, setProviders] = useState<ExternalProvider[]>([]);
  const [configs, setConfigs] = useState<ExternalConfig[]>([]);
  const [capabilityStatus, setCapabilityStatus] = useState<any>(null);
  const [form, setForm] = useState(emptyForm);
  const [editingConfigId, setEditingConfigId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ExternalConfig | null>(null);
  const [deletingConfig, setDeletingConfig] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [providerList, configList, status] = await Promise.all([
        apiClient.getExternalProviders(),
        apiClient.getExternalConfigs(),
        apiClient.getExternalCapabilityStatus(),
      ]);
      setProviders(providerList);
      setConfigs(configList);
      setCapabilityStatus(status);
      if (!form.providerId && providerList[0]) {
        setForm((prev) => ({
          ...prev,
          providerId: providerList[0].id,
          baseUrl: providerList[0].base_url || '',
        }));
      }
    } catch (err: any) {
      setError(err.message || '生产适配配置加载失败');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedProvider = providers.find((provider) => provider.id === form.providerId);

  const groupedProviders = useMemo(() => {
    return providers.reduce<Record<string, ExternalProvider[]>>((groups, provider) => {
      groups[provider.api_type] = groups[provider.api_type] || [];
      groups[provider.api_type].push(provider);
      return groups;
    }, {});
  }, [providers]);

  const readinessItems = useMemo(() => {
    const readiness = capabilityStatus?.readiness || {};
    return ['storage', 'audio_video', 'workflow', 'render', 'lip_sync'].map((type) => ({
      type,
      label: TYPE_LABELS[type] || type,
      ready: readiness[type]?.ready_count || 0,
      configured: readiness[type]?.configured_count || 0,
      providers: readiness[type]?.provider_count || 0,
    }));
  }, [capabilityStatus]);

  const resetForm = () => {
    const firstProvider = providers[0];
    setEditingConfigId(null);
    setForm({
      ...emptyForm,
      providerId: firstProvider?.id || '',
      baseUrl: firstProvider?.base_url || '',
    });
  };

  const updateForm = (key: keyof typeof emptyForm, value: string | number | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleProviderChange = (providerId: string) => {
    const provider = providers.find((item) => item.id === providerId);
    setForm((prev) => ({
      ...prev,
      providerId,
      baseUrl: provider?.base_url || '',
      submitPath:
        provider?.name === 'comfyui'
          ? '/prompt'
          : provider?.name === 'ffmpeg_cloud'
            ? '/render'
            : provider?.name === 'object_storage'
              ? ''
              : prev.submitPath,
      healthPath:
        provider?.name === 'comfyui'
          ? '/system_stats'
          : provider?.api_type === 'render'
            ? '/health'
            : provider?.name === 'object_storage'
              ? ''
              : prev.healthPath,
      extraJson:
        provider?.name === 'object_storage'
          ? JSON.stringify(
              {
                public_base_url: 'https://cdn.example.com',
                local_static_prefix: '/static/',
                public_static_prefix: '/static/',
              },
              null,
              2
            )
          : prev.extraJson,
    }));
  };

  const handleEdit = (config: ExternalConfig) => {
    const extra = config.extra_config || {};
    setEditingConfigId(config.id);
    setForm({
      providerId: config.provider_id,
      name: config.name,
      apiKey: '',
      apiSecret: '',
      baseUrl: config.custom_base_url || '',
      timeout: config.timeout || 60,
      retryCount: config.retry_count || 3,
      submitPath: extra.submit_path || '',
      healthPath: extra.health_path || '',
      description: '',
      isDefault: config.is_default,
      extraJson: JSON.stringify(
        Object.fromEntries(Object.entries(extra).filter(([key]) => !['submit_path', 'health_path'].includes(key))),
        null,
        2
      ),
    });
    requestAnimationFrame(() => {
      configFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      configNameInputRef.current?.focus({ preventScroll: true });
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      let extraConfig: Record<string, any> = {};
      if (form.extraJson.trim()) {
        extraConfig = JSON.parse(form.extraJson);
      }
      if (form.submitPath.trim()) extraConfig.submit_path = form.submitPath.trim();
      if (form.healthPath.trim()) extraConfig.health_path = form.healthPath.trim();

      const payload = {
        provider_id: form.providerId,
        name: form.name.trim(),
        api_key: form.apiKey || undefined,
        api_secret: form.apiSecret || undefined,
        custom_base_url: form.baseUrl.trim() || undefined,
        timeout: Number(form.timeout),
        retry_count: Number(form.retryCount),
        description: form.description.trim() || undefined,
        extra_config: extraConfig,
        is_default: form.isDefault,
      };

      if (editingConfigId) {
        await apiClient.updateExternalConfig(editingConfigId, payload);
        setMessage('配置已更新');
      } else {
        await apiClient.createExternalConfig(payload);
        setMessage('配置已保存');
      }
      resetForm();
      await loadData();
    } catch (err: any) {
      setError(err.message || '保存失败；检查 JSON 和必填项');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async (configId: string) => {
    setTestingId(configId);
    setError(null);
    setMessage(null);
    try {
      const result = await apiClient.testExternalConfig(configId);
      setMessage(result.message || '测试完成');
      await loadData();
    } catch (err: any) {
      setError(err.message || '测试失败');
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (configId: string) => {
    setDeletingConfig(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.deleteExternalConfig(configId);
      setMessage('配置已删除');
      await loadData();
    } catch (err: any) {
      setError(err.message || '删除失败');
    } finally {
      setDeletingConfig(false);
    }
  };

  return (
    <MainLayout>
      <div className="p-6 space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
              <PlugZap className="w-6 h-6 text-cyan-300" />
              生产适配
            </h1>
            <div className="mt-3 flex flex-wrap gap-2">
              {OPTIONAL_CAPABILITIES.map((item) => (
                <span key={item} className="rounded border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-white/70">
                  {item}
                </span>
              ))}
            </div>
          </div>
          <Button variant="outline" className="border-white/20" onClick={loadData} disabled={isLoading}>
            {isLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            刷新
          </Button>
        </div>

        {(message || error) && (
          <div className={`rounded-lg border p-3 text-sm ${error ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'}`}>
            {error || message}
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          {readinessItems.map((item) => {
            const Icon = TYPE_ICONS[item.type] || PlugZap;
            return (
              <Card key={item.type} className="bg-white/5 border-white/10">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <Icon className="h-5 w-5 text-cyan-300" />
                    {item.ready > 0 ? (
                      <CheckCircle className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-yellow-300" />
                    )}
                  </div>
                  <div className="mt-3 text-sm text-white/60">{item.label}</div>
                  <div className="mt-1 text-2xl font-semibold text-white">{item.ready}/{item.providers}</div>
                  <div className="mt-1 text-xs text-white/40">已配置 {item.configured}</div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <Card className="bg-cyan-500/10 border-cyan-500/25">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Workflow className="w-5 h-5 text-cyan-200" />
              应用位置
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 lg:grid-cols-4">
            {USAGE_STEPS.map((step) => (
              <div key={step.title} className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="font-medium text-white">{step.title}</div>
                  <span className="rounded bg-cyan-500/15 px-2 py-0.5 text-[11px] text-cyan-100">
                    {step.badge}
                  </span>
                </div>
                <div className="mt-2 text-xs leading-5 text-white/55">{step.detail}</div>
                <a href={step.path} className="mt-3 inline-flex text-xs text-cyan-100 underline">
                  打开入口
                </a>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <Card ref={configFormRef} className="scroll-mt-6 bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-300" />
                已接入配置
              </CardTitle>
            </CardHeader>
            <CardContent>
              {configs.length === 0 ? (
                <div className="rounded-lg border border-dashed border-white/10 p-8 text-center text-white/40">
                  暂无生产适配配置
                </div>
              ) : (
                <div className="space-y-3">
                  {configs.map((config) => (
                    <div key={config.id} className="rounded-lg border border-white/10 bg-black/20 p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-white">{config.name}</span>
                            <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-white/70">
                              {config.provider_name}
                            </span>
                            {config.is_default && (
                              <span className="rounded bg-cyan-500/15 px-2 py-0.5 text-xs text-cyan-100">默认</span>
                            )}
                            <span className={`rounded px-2 py-0.5 text-xs ${
                              config.test_status === 'failed'
                                ? 'bg-red-500/15 text-red-100'
                                : config.test_status === 'success'
                                  ? 'bg-emerald-500/15 text-emerald-100'
                                  : 'bg-yellow-500/15 text-yellow-100'
                            }`}>
                              {STATUS_LABELS[config.test_status || 'pending'] || config.test_status || '待测试'}
                            </span>
                          </div>
                          <div className="mt-2 text-sm text-white/50">
                            {TYPE_LABELS[config.api_type] || config.api_type}
                            {config.custom_base_url ? ` · ${config.custom_base_url}` : ''}
                          </div>
                          {config.test_message && (
                            <div className="mt-2 text-xs text-white/40">{config.test_message}</div>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" className="border-white/20" onClick={() => handleEdit(config)}>
                            <Edit2 className="h-4 w-4 mr-2" />
                            编辑
                          </Button>
                          <Button size="sm" variant="outline" className="border-white/20" onClick={() => handleTest(config.id)} disabled={testingId === config.id}>
                            {testingId === config.id ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <TestTube className="h-4 w-4 mr-2" />}
                            测试
                          </Button>
                          <Button size="sm" variant="outline" className="border-red-400/30 text-red-100 hover:bg-red-500/10" onClick={() => setDeleteTarget(config)}>
                            <Trash2 className="h-4 w-4 mr-2" />
                            删除
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-cyan-300" />
                {editingConfigId ? '编辑配置' : '新增配置'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="mb-2 block text-sm text-white/70">供应商</label>
                <Select
                  value={form.providerId}
                  onChange={(event) => handleProviderChange(event.target.value)}
                  options={providers.map((provider) => ({
                    value: provider.id,
                    label: provider.name_cn || provider.name,
                  }))}
                  placeholder="选择供应商"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm text-white/70">配置名称</label>
                <Input
                  ref={configNameInputRef}
                  value={form.name}
                  onChange={(event) => updateForm('name', event.target.value)}
                  placeholder="例如：Sora 生产配置"
                  className="bg-white/5 border-white/10 text-white"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm text-white/70">基础地址</label>
                <Input
                  value={form.baseUrl}
                  onChange={(event) => updateForm('baseUrl', event.target.value)}
                  placeholder={selectedProvider?.name === 'object_storage' ? 'https://cdn.example.com' : selectedProvider?.base_url || 'https://...'}
                  className="bg-white/5 border-white/10 text-white"
                />
                {selectedProvider?.name === 'object_storage' && (
                  <div className="mt-2 text-xs leading-5 text-white/45">
                    填写云端可访问的 CDN/对象存储公开域名。平台会把 `/static/...` 参考图映射到该域名下，供视频模型读取。
                  </div>
                )}
              </div>
              {selectedProvider?.name !== 'object_storage' && (
                <>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-sm text-white/70">API Key</label>
                      <Input
                        type="password"
                        value={form.apiKey}
                        onChange={(event) => updateForm('apiKey', event.target.value)}
                        placeholder={editingConfigId ? '留空则不更新' : '可选'}
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm text-white/70">API Secret</label>
                      <Input
                        type="password"
                        value={form.apiSecret}
                        onChange={(event) => updateForm('apiSecret', event.target.value)}
                        placeholder="可选"
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-sm text-white/70">提交路径</label>
                      <Input
                        value={form.submitPath}
                        onChange={(event) => updateForm('submitPath', event.target.value)}
                        placeholder="/render 或 /prompt"
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm text-white/70">健康检查</label>
                      <Input
                        value={form.healthPath}
                        onChange={(event) => updateForm('healthPath', event.target.value)}
                        placeholder="/health"
                        className="bg-white/5 border-white/10 text-white"
                      />
                    </div>
                  </div>
                </>
              )}
              {selectedProvider?.name === 'object_storage' && (
                <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 p-3 text-xs leading-5 text-cyan-50/80">
                  当前版本支持公开静态媒体出口：例如把 `/static/generated/images/a.png` 映射为 `https://cdn.example.com/static/generated/images/a.png`。请确保 CDN/对象存储已同步这些静态文件或反向代理到后端静态目录。
                </div>
              )}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm text-white/70">超时秒数</label>
                  <Input
                    type="number"
                    min={5}
                    max={600}
                    value={form.timeout}
                    onChange={(event) => updateForm('timeout', Number(event.target.value))}
                    className="bg-white/5 border-white/10 text-white"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm text-white/70">重试次数</label>
                  <Input
                    type="number"
                    min={0}
                    max={10}
                    value={form.retryCount}
                    onChange={(event) => updateForm('retryCount', Number(event.target.value))}
                    className="bg-white/5 border-white/10 text-white"
                  />
                </div>
              </div>
              <div>
                <label className="mb-2 block text-sm text-white/70">适配参数 JSON</label>
                <textarea
                  value={form.extraJson}
                  onChange={(event) => updateForm('extraJson', event.target.value)}
                  rows={5}
                  className="w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input
                  type="checkbox"
                  checked={form.isDefault}
                  onChange={(event) => updateForm('isDefault', event.target.checked)}
                  className="accent-cyan-500"
                />
                设为默认
              </label>
              <div className="flex flex-wrap gap-2">
                <Button onClick={handleSave} disabled={isSaving || !form.providerId || !form.name.trim()} className="bg-cyan-600 hover:bg-cyan-700">
                  {isSaving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                  保存配置
                </Button>
                {editingConfigId && (
                  <Button variant="outline" className="border-white/20" onClick={resetForm}>
                    取消编辑
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-yellow-300" />
              能力矩阵
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {Object.entries(groupedProviders).map(([type, items]) => {
                const Icon = TYPE_ICONS[type] || PlugZap;
                return (
                  <div key={type} className="rounded-lg border border-white/10 bg-black/20 p-4">
                    <div className="mb-3 flex items-center gap-2 text-white">
                      <Icon className="h-5 w-5 text-cyan-300" />
                      {TYPE_LABELS[type] || type}
                    </div>
                    <div className="space-y-3">
                      {items.map((provider) => (
                        <div key={provider.id} className="rounded border border-white/10 bg-white/5 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="font-medium text-white">{provider.name_cn || provider.name}</div>
                            {configs.some((config) => config.provider_id === provider.id) ? (
                              <CheckCircle className="h-4 w-4 text-emerald-400" />
                            ) : (
                              <XCircle className="h-4 w-4 text-white/30" />
                            )}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {(provider.capabilities || []).slice(0, 8).map((capability) => (
                              <span key={capability} className="rounded bg-white/10 px-2 py-0.5 text-xs text-white/60">
                                {capability}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="删除生产适配配置"
        description={`确认删除${deleteTarget ? `「${deleteTarget.name}」` : '该配置'}？删除后相关生产入口将无法继续使用这组适配参数。`}
        confirmText="删除配置"
        destructive
        loading={deletingConfig}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={async () => {
          if (!deleteTarget) return;
          await handleDelete(deleteTarget.id);
          setDeleteTarget(null);
        }}
      />
    </MainLayout>
  );
}
