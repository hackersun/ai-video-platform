'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Settings,
  Key,
  Plus,
  Trash2,
  TestTube,
  CheckCircle,
  XCircle,
  Loader2,
  Sparkles,
  Video,
  Music,
  Image as ImageIcon,
  MessageSquare,
  ChevronRight,
  Copy,
  RefreshCw,
  ExternalLink,
  AlertCircle,
  Globe,
  Network,
  KeyRound,
  Edit2,
  ShieldCheck,
  ClipboardList
} from 'lucide-react';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import {
  MODEL_CAPABILITY_LABELS,
  getConfigsByCapability,
  getDefaultConfigForCapability,
  getModelCapabilities,
  getModelCapability,
  isInternalProviderConfig, isInternalTestModelConfig,
  modelStatusClass,
  modelStatusLabel,
  type ModelCapability,
} from '@/lib/model-configs';

// 模型分类
const MODEL_CATEGORIES = {
  text: { name: '文本生成', icon: MessageSquare, color: 'text-blue-400' },
  image: { name: '图像生成', icon: ImageIcon, color: 'text-purple-400' },
  video: { name: '视频生成', icon: Video, color: 'text-pink-400' },
  audio: { name: '音频生成', icon: Music, color: 'text-green-400' },
};

// API配置
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface Provider {
  id: string;
  name: string;
  name_cn: string;
  base_url: string;
  description?: string;
}

interface Model {
  id: string;
  provider_id: string;
  model_id: string;
  model_name: string;
  model_name_cn?: string;
  model_type: string;
  capabilities?: string[];
  context_window: number;
  max_tokens: number;
  input_cost_per_1k: number;
  output_cost_per_1k: number;
  base_url?: string | null;
  is_recommended?: boolean;
  description?: string;
  user_config_id?: string;
  user_config_name?: string;
  user_configured?: boolean;
  user_config_count?: number;
  user_is_default?: boolean;
  user_test_status?: string | null;
  user_test_message?: string | null;
  user_key_available?: boolean;
}

interface SavedConfig {
  id: string;
  model_id: string;
  config_model_id?: string;
  api_model_id?: string;
  model_type?: string;
  model_capabilities?: string[];
  provider_id: string;
  model_name: string;
  provider_name: string;
  name: string;
  temperature: number;
  top_p: number;
  max_tokens?: number;
  is_default: boolean;
  test_status?: string;
  test_message?: string;
  key_available?: boolean;
  usage_count: number;
  api_key?: string;
}

const PRODUCTION_TASK_REQUIREMENTS: Array<{
  name: string;
  description: string;
  capabilities: ModelCapability[];
}> = [
  {
    name: '小说/章节/剧本生成',
    description: '长文本、角色关系、剧情承接和结构化输出',
    capabilities: ['text'],
  },
  {
    name: '角色/实体/参考图分析',
    description: '识别图片参考、外观一致性和视觉提示词辅助',
    capabilities: ['vision', 'text'],
  },
  {
    name: '封面/头像/场景参考图',
    description: '真正输出图片资产，不能只用视觉理解模型',
    capabilities: ['image'],
  },
  {
    name: '镜头视频/动漫短剧',
    description: '文生视频、图生视频和镜头一致性生产',
    capabilities: ['video', 'image', 'text'],
  },
  {
    name: '角色配音/旁白',
    description: 'TTS、音色试听和声音克隆相关能力',
    capabilities: ['audio'],
  },
  {
    name: '素材检索/知识库',
    description: '资产、实体、剧情记忆的向量检索',
    capabilities: ['embedding'],
  },
];

const ANIME_MODEL_PRESETS: Array<{
  name: string;
  description: string;
  target: string;
  capabilities: ModelCapability[];
}> = [
  {
    name: '快速预览',
    description: '适合先跑几秒草片，确认角色、画风、镜头节奏和声音方向。',
    target: '建议准备文本、图像、视频、语音默认模型',
    capabilities: ['text', 'image', 'video', 'audio'],
  },
  {
    name: '高质量成片',
    description: '适合草片确认后重生关键镜头，更关注画面稳定和多集一致性。',
    target: '建议默认模型全部已验证，并优先选择推荐视频模型',
    capabilities: ['text', 'vision', 'image', 'video', 'audio'],
  },
  {
    name: '低成本试错',
    description: '适合大量试镜头、长章节拆解和提示词探索，先保留可替换空间。',
    target: '至少保证文本、图像、视频模型可用；语音可后补',
    capabilities: ['text', 'image', 'video'],
  },
];

export default function LLMConfigPage() {
  const configFormRef = useRef<HTMLDivElement | null>(null);
  const configNameInputRef = useRef<HTMLInputElement | null>(null);
  const [activeTab, setActiveTab] = useState('volcano');
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [savedConfigs, setSavedConfigs] = useState<SavedConfig[]>([]);
  const [editingConfig, setEditingConfig] = useState<SavedConfig | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isTestingDefaults, setIsTestingDefaults] = useState(false);
  const [testResult, setTestResult] = useState<{success: boolean; message: string; response?: string} | null>(null);
  const [lastPassedFormTest, setLastPassedFormTest] = useState<{
    providerId: string;
    modelId: string;
    apiKey: string;
  } | null>(null);

  // 配置表单状态
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [configName, setConfigName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [temperature, setTemperature] = useState(0.7);
  const [topP, setTopP] = useState(0.9);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [isDefault, setIsDefault] = useState(false);
  const [selectedCapabilityFilter, setSelectedCapabilityFilter] = useState<ModelCapability | 'all'>('all');
  const [showAdvancedModels, setShowAdvancedModels] = useState(false);

  const currentProvider = providers.find(p => p.id === selectedProvider);
  const providerTabs = providers.filter((provider) => provider.id !== 'external');
  const activeProvider = providers.find((provider) => provider.id === activeTab);
  const providerModels = models.filter(m => m.provider_id === selectedProvider);
  const isAdvancedModel = (model: Model) => {
    const capabilities = getModelCapabilities(model);
    return (
      isInternalTestModelConfig(model)
      || (
        selectedCapabilityFilter === 'all'
        && capabilities.includes('audio')
        && !model.user_configured
        && !model.is_recommended
      )
    );
  };
  const visibleProviderModels = providerModels.filter((model) => showAdvancedModels || !isAdvancedModel(model));
  const hiddenModelCount = providerModels.length - visibleProviderModels.length;
  const filteredModels = visibleProviderModels.filter((model) => (
    selectedCapabilityFilter === 'all' || getModelCapabilities(model).includes(selectedCapabilityFilter)
  ));
  const selectedModelInfo = models.find(m => m.id === selectedModel);
  const selectedModelExistingConfig = selectedModelInfo?.user_config_id
    ? savedConfigs.find(config => config.id === selectedModelInfo.user_config_id)
    : undefined;
  const productionSavedConfigs = savedConfigs.filter((config) => !isInternalTestModelConfig(config));
  const visibleSavedConfigs = showAdvancedModels ? savedConfigs : productionSavedConfigs;
  const targetConfig = editingConfig || selectedModelExistingConfig;
  const targetConfigModelId = targetConfig?.config_model_id || targetConfig?.model_id;
  const hasSavedUsableKey = Boolean(targetConfig?.key_available && targetConfigModelId === selectedModel);
  const apiKeyInput = apiKey.trim();
  const requiresApiKey = !hasSavedUsableKey;
  const canTestCurrentForm = Boolean(selectedModel && (apiKeyInput || hasSavedUsableKey));
  const canSaveCurrentForm = Boolean(configName && selectedModel && (!requiresApiKey || apiKeyInput));
  const formTestMatchesCurrentInput = Boolean(
    lastPassedFormTest
    && apiKeyInput
    && lastPassedFormTest.providerId === selectedProvider
    && lastPassedFormTest.modelId === selectedModel
    && lastPassedFormTest.apiKey === apiKeyInput
  );
  const agentPlanSelected = selectedProvider === 'volcano_agent_plan';
  const capabilityOrder: ModelCapability[] = ['text', 'image', 'vision', 'audio', 'video', 'embedding'];
  const capabilityFilterOptions: Array<{ value: ModelCapability | 'all'; label: string; count: number }> = [
    { value: 'all', label: '全部', count: visibleProviderModels.length },
    ...capabilityOrder.map((capability) => ({
      value: capability,
      label: MODEL_CAPABILITY_LABELS[capability],
      count: visibleProviderModels.filter((model) => getModelCapabilities(model).includes(capability)).length,
    })),
  ];
  const selectedCapability = selectedModelInfo ? getModelCapability(selectedModelInfo) : null;
  const selectedCapabilities = selectedModelInfo ? getModelCapabilities(selectedModelInfo) : [];
  const selectedModelIsVisionOnly = selectedCapabilities.includes('vision') && !selectedCapabilities.includes('image');
  const activeDefaultConfigs = capabilityOrder
    .map((capability) => ({ capability, config: getDefaultConfigForCapability(productionSavedConfigs, capability) }))
    .filter((item): item is { capability: ModelCapability; config: SavedConfig } => Boolean(item.config));
  const missingDefaultCapabilities = capabilityOrder.filter((capability) => !getDefaultConfigForCapability(productionSavedConfigs, capability));
  const unverifiedDefaultConfigs = activeDefaultConfigs.filter((item) => item.config.test_status !== 'success');
  const failedConfigs = productionSavedConfigs.filter((config) => config.test_status === 'failed');
  const duplicateConfigGroups = productionSavedConfigs.reduce<Record<string, SavedConfig[]>>((groups, config) => {
    const key = config.config_model_id || config.model_id || config.api_model_id || config.model_name;
    if (!key) return groups;
    groups[key] = [...(groups[key] || []), config];
    return groups;
  }, {});
  const duplicateConfigCount = Object.values(duplicateConfigGroups).filter((group) => group.length > 1).length;
  const healthIssues = [
    ...missingDefaultCapabilities.map((capability) => ({
      key: `missing-${capability}`,
      level: 'warning' as const,
      text: `缺少${MODEL_CAPABILITY_LABELS[capability]}默认配置`,
    })),
    ...unverifiedDefaultConfigs.map(({ capability, config }) => ({
      key: `unverified-${capability}-${config.id}`,
      level: 'warning' as const,
      text: `${MODEL_CAPABILITY_LABELS[capability]}默认模型未验证：${config.name}`,
    })),
    ...failedConfigs.map((config) => ({
      key: `failed-${config.id}`,
      level: 'danger' as const,
      text: `${config.name}：${config.test_message || '配置验证失败'}`,
    })),
    ...(duplicateConfigCount > 0 ? [{
      key: 'duplicates',
      level: 'warning' as const,
      text: `存在 ${duplicateConfigCount} 类重复模型配置，建议保留一个默认配置`,
    }] : []),
  ];
  const healthScore = healthIssues.length === 0
    ? 100
    : Math.max(0, 100 - missingDefaultCapabilities.length * 12 - unverifiedDefaultConfigs.length * 8 - failedConfigs.length * 15 - duplicateConfigCount * 6);
  const healthLabel = healthScore >= 90 ? '健康' : healthScore >= 70 ? '可用但需整理' : '需要配置';
  const modelSelectOptions = filteredModels.map(m => {
    const markers = [
      m.user_is_default ? '默认' : null,
      m.user_configured ? '已配置' : null,
      m.user_configured ? modelStatusLabel(m.user_test_status) : null,
    ].filter(Boolean);
    const suffix = markers.length > 0 ? `（${markers.join(' / ')}）` : '';
    return {
      value: m.id,
      label: `${m.model_name_cn || m.model_name}${suffix}`,
    };
  });

  // 获取提供商列表
  const fetchProviders = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/llm/providers`);
      if (res.ok) {
        const visibleProviders = (await res.json()).filter((provider: Provider) => !isInternalProviderConfig(provider));
        setProviders(visibleProviders);
        if (visibleProviders.length > 0 && !selectedProvider) {
          setSelectedProvider(visibleProviders[0].id);
        }
      }
    } catch (error) {
      console.error('获取提供商失败:', error);
      // 使用默认提供商
      setProviders([
        { id: 'volcano', name: 'volcano', name_cn: '火山引擎', base_url: 'https://ark.cn-beijing.volces.com/api/v3', description: '字节跳动豆包大模型' },
        { id: 'volcano_agent_plan', name: 'volcano_agent_plan', name_cn: '火山方舟 Agent Plan', base_url: 'https://ark.cn-beijing.volces.com/api/plan/v3', description: '火山方舟订阅式 Agent Plan' },
        { id: 'qianlian', name: 'qianlian', name_cn: '阿里百炼', base_url: 'https://coding.dashscope.aliyuncs.com/apps/anthropic', description: '阿里云百炼平台' },
        { id: 'dashscope', name: 'dashscope', name_cn: '阿里千问', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', description: '阿里云千问DashScope' },
      ]);
    }
  };

  // 获取模型列表
  const fetchModels = async (providerId?: string) => {
    try {
      const url = providerId
        ? `${API_BASE_URL}/llm/models?provider=${providerId}`
        : `${API_BASE_URL}/llm/models`;
      const res = await fetchWithAuth(url);
      if (res.ok) {
        const data = await res.json();
        setModels(data);
        if (selectedProvider) {
          const selectedStillExists = data.some((item: Model) => item.id === selectedModel);
          if (!selectedStillExists) {
            const configured = data.find((item: Model) => item.user_is_default || item.user_configured);
            if (configured) {
              setSelectedModel(configured.id);
            }
          }
        }
      }
    } catch (error) {
      console.error('获取模型失败:', error);
      // 使用默认模型
      setModels([
        { id: 'doubao-seed-1-8', provider_id: 'volcano', model_id: 'doubao-seed-1-8-251228', model_name: 'Doubao-Seed-1.8', model_name_cn: '豆包Seed-1.8', model_type: 'chat', context_window: 4096, max_tokens: 2048, input_cost_per_1k: 0.5, output_cost_per_1k: 1.0, is_recommended: true },
        { id: 'vplan-ark-code-latest', provider_id: 'volcano_agent_plan', model_id: 'ark-code-latest', model_name: 'ark-code-latest', model_name_cn: 'Ark Code Latest', model_type: 'chat', context_window: 256000, max_tokens: 4096, input_cost_per_1k: 2.5, output_cost_per_1k: 2.5, is_recommended: true },
        { id: 'vplan-seedream-5-0-lite', provider_id: 'volcano_agent_plan', model_id: 'doubao-seedream-5.0-lite', model_name: 'doubao-seedream-5.0-lite', model_name_cn: '豆包 Seedream 5.0 Lite', model_type: 'image-generation', context_window: 0, max_tokens: 0, input_cost_per_1k: 0, output_cost_per_1k: 0, is_recommended: true },
        { id: 'vplan-seedance-2-0-fast', provider_id: 'volcano_agent_plan', model_id: 'doubao-seedance-2.0-fast', model_name: 'doubao-seedance-2.0-fast', model_name_cn: '豆包 Seedance 2.0 Fast', model_type: 'video-generation', context_window: 0, max_tokens: 0, input_cost_per_1k: 0, output_cost_per_1k: 0, is_recommended: true },
        { id: 'qwen-turbo', provider_id: 'dashscope', model_id: 'qwen-turbo', model_name: 'qwen-turbo', model_name_cn: '千问Turbo', model_type: 'chat', context_window: 8192, max_tokens: 2048, input_cost_per_1k: 0.5, output_cost_per_1k: 1.0 },
      ]);
    }
  };

  // 获取已保存的配置
  const fetchConfigs = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/llm/configs`);
      if (res.ok) {
        const data = await res.json();
        setSavedConfigs(data);
      }
    } catch (error) {
      console.error('获取配置失败:', error);
    }
  };

  useEffect(() => {
    fetchProviders();
    fetchModels();
    fetchConfigs();
  }, []);

  // 切换Tab时更新provider
  useEffect(() => {
    const nextProvider = activeTab === 'external' ? '' : activeTab;
    setSelectedProvider(nextProvider);
    setSelectedModel('');
    setLastPassedFormTest(null);
    fetchModels(nextProvider);
  }, [activeTab]);

  // 测试连接
  const handleTest = async () => {
    if (!selectedModel) {
      setTestResult({ success: false, message: '请先选择一个模型' });
      return;
    }

    if (!apiKeyInput && hasSavedUsableKey && targetConfig) {
      await handleTestConfig(targetConfig);
      return;
    }

    if (!apiKeyInput) {
      setTestResult({ success: false, message: '请输入API Key；已有配置如需沿用原 Key，请直接点击更新配置或测试已保存配置' });
      return;
    }

    setIsTesting(true);
    setTestResult(null);
    setLastPassedFormTest(null);

    try {
      const model = models.find(m => m.id === selectedModel);
      const provider = providers.find(p => p.id === selectedProvider);

      const testRes = await fetchWithAuth(`${API_BASE_URL}/llm/configs/test`, {
        method: 'POST',
        body: JSON.stringify({
          api_key: apiKeyInput,
          provider_id: selectedProvider,
          model_id: selectedModel,
          message: '你好，请介绍一下自己'
        })
      });

      if (testRes.ok) {
        const result = await testRes.json();
        setTestResult({
          success: result.success,
          message: result.message || (result.success ? `${provider?.name_cn || '模型'} API Key 验证通过` : '连接测试失败'),
          response: result.response
        });
        if (result.success) {
          setLastPassedFormTest({
            providerId: selectedProvider,
            modelId: selectedModel,
            apiKey: apiKeyInput,
          });
        }
      } else {
        const error = await testRes.json().catch(() => ({}));
        setTestResult({
          success: false,
          message: error.detail || error.message || `连接测试失败：HTTP ${testRes.status}`,
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '连接测试失败';
      setTestResult({ success: false, message });
    }

    setIsTesting(false);
  };

  // 直接测试API连接
  const testApiConnection = async (provider?: Provider, model?: Model, key?: string): Promise<{success: boolean; message: string; response?: string}> => {
    if (!provider || !model || !key) {
      return { success: false, message: '参数不完整，请确保已选择服务商和模型' };
    }

    // 火山引擎测试
    if (provider.id === 'volcano') {
      try {
        const res = await fetch(`${provider.base_url}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${key}`
          },
          body: JSON.stringify({
            model: model.model_id,
            messages: [{ role: 'user', content: '你好' }],
            max_tokens: 100
          })
        });

        if (res.ok) {
          const data = await res.json();
          return {
            success: true,
            message: '✅ 火山引擎 API 连接成功！',
            response: data.choices?.[0]?.message?.content || '响应成功'
          };
        } else if (res.status === 401 || res.status === 403) {
          const error = await res.json().catch(() => ({}));
          return { success: false, message: '🔑 API Key无效或已过期，请检查Key是否正确' };
        } else if (res.status === 429) {
          return { success: false, message: '⏱️ 请求过于频繁，请稍后再试（配额可能已用完）' };
        } else if (res.status >= 500) {
          return { success: false, message: '🖥️ 服务端错误，请检查火山引擎服务状态' };
        } else {
          const error = await res.json().catch(() => ({}));
          return { success: false, message: `❌ API错误: ${error.error?.message || res.statusText}` };
        }
      } catch (e: any) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
          return { success: false, message: '🌐 网络连接失败，请检查网络或API地址是否正确' };
        }
        return { success: false, message: `❌ 连接失败: ${e.message}` };
      }
    }

    // 千问测试
    if (provider.id === 'qwen') {
      try {
        const res = await fetch(`${provider.base_url}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${key}`
          },
          body: JSON.stringify({
            model: model.model_id,
            input: { messages: [{ role: 'user', content: '你好' }] },
            parameters: { max_tokens: 100 }
          })
        });

        if (res.ok) {
          const data = await res.json();
          return {
            success: true,
            message: '✅ 阿里千问 API 连接成功！',
            response: data.output?.text || data.choices?.[0]?.message?.content || '响应成功'
          };
        } else if (res.status === 401 || res.status === 403) {
          return { success: false, message: '🔑 API Key无效或已过期，请检查Key是否正确' };
        } else if (res.status === 429) {
          return { success: false, message: '⏱️ 请求过于频繁，请稍后再试（配额可能已用完）' };
        } else if (res.status >= 500) {
          return { success: false, message: '🖥️ 服务端错误，请检查阿里云服务状态' };
        } else {
          const error = await res.json().catch(() => ({}));
          return { success: false, message: `❌ API错误: ${error.error?.message || res.statusText}` };
        }
      } catch (e: any) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
          return { success: false, message: '🌐 网络连接失败，请检查网络或API地址是否正确' };
        }
        return { success: false, message: `❌ 连接失败: ${e.message}` };
      }
    }

    // 百度文心测试
    if (provider.id === 'baidu') {
      try {
        const res = await fetch(`${provider.base_url}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${key}`
          },
          body: JSON.stringify({
            model: model.model_id,
            messages: [{ role: 'user', content: '你好' }],
            max_tokens: 100
          })
        });

        if (res.ok) {
          const data = await res.json();
          return {
            success: true,
            message: '✅ 百度文心一言 API 连接成功！',
            response: data.choices?.[0]?.message?.content || '响应成功'
          };
        } else if (res.status === 401 || res.status === 403) {
          return { success: false, message: '🔑 API Key无效或已过期，请检查Key是否正确' };
        } else if (res.status === 429) {
          return { success: false, message: '⏱️ 请求过于频繁，请稍后再试（配额可能已用完）' };
        } else if (res.status >= 500) {
          return { success: false, message: '🖥️ 服务端错误，请检查百度千帆服务状态' };
        } else {
          const error = await res.json().catch(() => ({}));
          return { success: false, message: `❌ API错误: ${error.error?.message || res.statusText}` };
        }
      } catch (e: any) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
          return { success: false, message: '🌐 网络连接失败，请检查网络或API地址是否正确' };
        }
        return { success: false, message: `❌ 连接失败: ${e.message}` };
      }
    }

    // 阿里百炼测试
    if (provider.id === 'qianlian') {
      try {
        const res = await fetch(`${provider.base_url}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${key}`
          },
          body: JSON.stringify({
            model: model.model_id,
            input: { messages: [{ role: 'user', content: '你好' }] },
            parameters: { max_tokens: 100 }
          })
        });

        if (res.ok) {
          const data = await res.json();
          return {
            success: true,
            message: '✅ 阿里百炼 API 连接成功！',
            response: data.output?.text || data.choices?.[0]?.message?.content || '响应成功'
          };
        } else if (res.status === 401 || res.status === 403) {
          return { success: false, message: '🔑 API Key无效或已过期，请检查Key是否正确' };
        } else if (res.status === 429) {
          return { success: false, message: '⏱️ 请求过于频繁，请稍后再试（配额可能已用完）' };
        } else if (res.status >= 500) {
          return { success: false, message: '🖥️ 服务端错误，请检查阿里百炼服务状态' };
        } else {
          const error = await res.json().catch(() => ({}));
          return { success: false, message: `❌ API错误: ${error.error?.message || res.statusText}` };
        }
      } catch (e: any) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
          return { success: false, message: '🌐 网络连接失败，请检查网络或API地址是否正确' };
        }
        return { success: false, message: `❌ 连接失败: ${e.message}` };
      }
    }

    // MiniMax测试
    if (provider.id === 'minimax') {
      try {
        const baseUrl = 'https://api.minimaxi.com/v1';
        const endpoint = model.model_id === 'MiniMax-M3'
          ? '/text/chatcompletion_v2'
          : '/chat/completions';
        const res = await fetch(`${baseUrl}${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${key}`
          },
          body: JSON.stringify({
            model: model.model_id,
            messages: [{ role: 'user', content: '你好' }],
            max_tokens: 100
          })
        });

        if (res.ok) {
          const data = await res.json();
          return {
            success: true,
            message: '✅ MiniMax API 连接成功！',
            response: data.choices?.[0]?.message?.content || '响应成功'
          };
        } else if (res.status === 401 || res.status === 403) {
          return { success: false, message: '🔑 API Key无效或已过期，请检查Key是否正确' };
        } else if (res.status === 429) {
          return { success: false, message: '⏱️ 请求过于频繁，请稍后再试（配额可能已用完）' };
        } else if (res.status >= 500) {
          return { success: false, message: '🖥️ 服务端错误，请检查MiniMax服务状态' };
        } else {
          const error = await res.json().catch(() => ({}));
          return { success: false, message: `❌ API错误: ${error.error?.message || res.statusText}` };
        }
      } catch (e: any) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
          return { success: false, message: '🌐 网络连接失败，请检查网络或API地址是否正确' };
        }
        return { success: false, message: `❌ 连接失败: ${e.message}` };
      }
    }

    // OpenAI测试
    if (provider.id === 'openai') {
      try {
        const res = await fetch(`${provider.base_url}/chat/completions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${key}`
          },
          body: JSON.stringify({
            model: model.model_id,
            messages: [{ role: 'user', content: '你好' }],
            max_tokens: 100
          })
        });

        if (res.ok) {
          const data = await res.json();
          return {
            success: true,
            message: '✅ OpenAI API 连接成功！',
            response: data.choices?.[0]?.message?.content || '响应成功'
          };
        } else if (res.status === 401 || res.status === 403) {
          return { success: false, message: '🔑 API Key无效或已过期，请检查Key是否正确' };
        } else if (res.status === 429) {
          return { success: false, message: '⏱️ 请求过于频繁，请稍后再试（配额可能已用完）' };
        } else if (res.status >= 500) {
          return { success: false, message: '🖥️ 服务端错误，请检查OpenAI服务状态' };
        } else {
          const error = await res.json().catch(() => ({}));
          return { success: false, message: `❌ API错误: ${error.error?.message || res.statusText}` };
        }
      } catch (e: any) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
          return { success: false, message: '🌐 网络连接失败，请检查网络或API地址是否正确' };
        }
        return { success: false, message: `❌ 连接失败: ${e.message}` };
      }
    }

    return { success: false, message: '❌ 不支持的提供商' };
  };

  // 保存配置
  const handleSave = async () => {
    if (!configName) {
      setTestResult({ success: false, message: '请输入配置名称' });
      return;
    }
    if (requiresApiKey && !apiKeyInput) {
      setTestResult({ success: false, message: '请输入API Key' });
      return;
    }
    if (!selectedModel) {
      setTestResult({ success: false, message: '请选择模型' });
      return;
    }

    setIsLoading(true);
    try {
      const updatingExisting = !editingConfig && selectedModelExistingConfig;
      const existingConfigId = editingConfig?.id || selectedModelExistingConfig?.id;
      const isUpdatingConfig = Boolean(editingConfig || updatingExisting);
      const requestBody = {
        model_id: selectedModel,
        name: configName,
        ...(apiKeyInput ? { api_key: apiKeyInput } : {}),
        api_secret: apiSecret,
        temperature,
        top_p: topP,
        max_tokens: maxTokens,
        extra_params: agentPlanSelected ? { base_url: currentProvider?.base_url } : undefined,
        is_default: isDefault
      };
      const url = isUpdatingConfig && existingConfigId
        ? `${API_BASE_URL}/llm/configs/${existingConfigId}`
          : `${API_BASE_URL}/llm/configs`;
      const res = await fetchWithAuth(url, {
        method: isUpdatingConfig ? 'PUT' : 'POST',
        body: JSON.stringify(requestBody)
      });

      if (res.ok) {
        const saved = await res.json();
        let saveMessage = isUpdatingConfig ? '配置已更新。' : '配置已保存成功。';
        if (formTestMatchesCurrentInput) {
          const verifyRes = await fetchWithAuth(`${API_BASE_URL}/llm/configs/${saved.id}/test`, {
            method: 'POST',
            body: JSON.stringify({ message: '你好，请介绍一下自己' })
          });
          const verifyData = await verifyRes.json().catch(() => ({}));
          saveMessage = verifyData.success
            ? `${saveMessage} 已同步验证状态。`
            : `${saveMessage} 但同步验证失败：${verifyData.message || '请稍后重新测试'}`;
          setTestResult({
            success: Boolean(verifyData.success),
            message: saveMessage,
            response: verifyData.response
          });
        } else {
          setTestResult({ success: true, message: saveMessage });
        }
        await fetchConfigs();
        await fetchModels(selectedProvider || undefined);
        setSelectedModel(saved.config_model_id || selectedModel);
        setEditingConfig(null);
        setLastPassedFormTest(null);
        // 重置表单
        setConfigName('');
        setApiKey('');
        setApiSecret('');
      } else {
        const error = await res.json().catch(() => ({}));
        setTestResult({ success: false, message: `保存失败: ${error.detail || '未知错误'}` });
      }
    } catch (error: any) {
      const msg = error?.message || String(error) || '未知错误';
      setTestResult({ success: false, message: `保存失败: ${msg}` });
    }
    setIsLoading(false);
  };

  // 删除配置
  const handleDelete = async (configId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/llm/configs/${configId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setSavedConfigs(prev => prev.filter(c => c.id !== configId));
        setTestResult({ success: true, message: '配置已删除' });
      }
    } catch (error) {
      setTestResult({ success: false, message: '删除失败' });
    }
  };

  // 设置默认配置
  const handleSetDefault = async (configId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/llm/configs/${configId}/set-default`, {
        method: 'POST'
      });
      if (res.ok) {
        await fetchConfigs();
        await fetchModels(selectedProvider || undefined);
        setTestResult({ success: true, message: '已设为默认配置' });
      }
    } catch (error) {
      setTestResult({ success: false, message: '设置失败' });
    }
  };

  // 编辑配置
  const handleEdit = (config: SavedConfig) => {
    setEditingConfig(config);
    setLastPassedFormTest(null);
    setTestResult(null);
    setConfigName(config.name);
    setSelectedModel(config.config_model_id || config.model_id);
    // 查找对应的provider
    const model = models.find(m => m.id === (config.config_model_id || config.model_id) || m.model_id === config.api_model_id || m.model_id === config.model_id);
    if (model) {
      setSelectedProvider(model.provider_id);
      setActiveTab(model.provider_id);
    } else if (config.provider_id) {
      setSelectedProvider(config.provider_id);
      setActiveTab(config.provider_id);
    }
    // 注意：出于安全考虑，不回填API Key
    setApiKey('');
    setApiSecret('');
    setTemperature(config.temperature);
    setTopP(config.top_p);
    setMaxTokens(config.max_tokens || 2048);
    setIsDefault(config.is_default);
    requestAnimationFrame(() => {
      configFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      configNameInputRef.current?.focus({ preventScroll: true });
    });
  };

  // 测试指定配置
  const handleTestConfig = async (config: SavedConfig) => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/llm/configs/${config.id}/test`, {
        method: 'POST',
        body: JSON.stringify({ message: '你好，请介绍一下自己' })
      });

      const data = await res.json();
      setTestResult({
        success: data.success,
        message: data.message || (data.success ? '测试成功' : '测试失败'),
        response: data.response
      });

      // 更新配置状态
      setSavedConfigs(prev => prev.map(c =>
        c.id === config.id
          ? { ...c, test_status: data.success ? 'success' : 'failed', test_message: data.message }
          : c
      ));
      await fetchConfigs();
      await fetchModels(config.provider_id || selectedProvider || undefined);
    } catch (error) {
      setTestResult({ success: false, message: '测试请求失败' });
      setSavedConfigs(prev => prev.map(c =>
        c.id === config.id
          ? { ...c, test_status: 'failed', test_message: '测试请求失败' }
          : c
      ));
    }

    setIsTesting(false);
  };

  const handleTestDefaultConfigs = async () => {
    const uniqueConfigs = Array.from(
      new Map(activeDefaultConfigs.map(({ config }) => [config.id, config])).values()
    );
    if (uniqueConfigs.length === 0) {
      setTestResult({ success: false, message: '还没有默认模型配置，请先至少配置文本、图像、视频或语音模型。' });
      return;
    }

    setIsTestingDefaults(true);
    setTestResult(null);

    let successCount = 0;
    let failedCount = 0;
    const updatedConfigs: SavedConfig[] = [];

    for (const config of uniqueConfigs) {
      try {
        const res = await fetchWithAuth(`${API_BASE_URL}/llm/configs/${config.id}/test`, {
          method: 'POST',
          body: JSON.stringify({ message: '你好，请用一句话说明当前模型可用。' })
        });
        const data = await res.json();
        const nextConfig = {
          ...config,
          test_status: data.success ? 'success' : 'failed',
          test_message: data.message || (data.success ? '测试成功' : '测试失败'),
        };
        updatedConfigs.push(nextConfig);
        if (data.success) {
          successCount += 1;
        } else {
          failedCount += 1;
        }
      } catch {
        failedCount += 1;
        updatedConfigs.push({
          ...config,
          test_status: 'failed',
          test_message: '测试请求失败',
        });
      }
    }

    setSavedConfigs(prev => prev.map(config => {
      const updated = updatedConfigs.find(item => item.id === config.id);
      return updated || config;
    }));
    await fetchConfigs();
    await fetchModels(selectedProvider || undefined);
    setTestResult({
      success: failedCount === 0,
      message: `默认模型验证完成：${successCount} 个通过，${failedCount} 个失败。`,
    });
    setIsTestingDefaults(false);
  };

  const focusCapabilitySetup = (capability: ModelCapability) => {
    const defaultConfig = getDefaultConfigForCapability(productionSavedConfigs, capability);
    setLastPassedFormTest(null);
    setTestResult(null);
    setSelectedCapabilityFilter(capability);

    if (defaultConfig) {
      setSelectedProvider(defaultConfig.provider_id);
      setActiveTab(defaultConfig.provider_id);
      const matchedModel = models.find((model) => (
        model.id === (defaultConfig.config_model_id || defaultConfig.model_id)
        || model.model_id === defaultConfig.api_model_id
        || model.model_id === defaultConfig.model_id
      ));
      if (matchedModel) {
        setSelectedModel(matchedModel.id);
      }
    } else {
      const candidate = visibleProviderModels.find((model) => getModelCapabilities(model).includes(capability) && model.is_recommended)
        || models.find((model) => getModelCapabilities(model).includes(capability) && model.is_recommended)
        || visibleProviderModels.find((model) => getModelCapabilities(model).includes(capability))
        || models.find((model) => getModelCapabilities(model).includes(capability));
      if (candidate) {
        setSelectedProvider(candidate.provider_id);
        setActiveTab(candidate.provider_id);
        setSelectedModel(candidate.id);
      }
    }

    requestAnimationFrame(() => {
      configFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Settings className="w-6 h-6" />
            大模型配置
          </h1>
          <p className="text-white/60 mt-1">配置和管理AI模型服务，支持火山引擎、火山方舟 Agent Plan、阿里千问等</p>
        </div>

        {/* 主要内容区域 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：模型列表 */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-300" />
                  生产配置总览
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="text-xs text-white/45">健康度</div>
                    <div className="mt-1 text-2xl font-semibold text-white">{healthScore}</div>
                    <div className="mt-1 text-xs text-white/55">{healthLabel}</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="text-xs text-white/45">默认能力</div>
                    <div className="mt-1 text-2xl font-semibold text-white">{activeDefaultConfigs.length}/{capabilityOrder.length}</div>
                    <div className="mt-1 text-xs text-white/55">已配置能力默认</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="text-xs text-white/45">未验证默认</div>
                    <div className="mt-1 text-2xl font-semibold text-white">{unverifiedDefaultConfigs.length}</div>
                    <div className="mt-1 text-xs text-white/55">建议生成前验证</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="text-xs text-white/45">重复配置</div>
                    <div className="mt-1 text-2xl font-semibold text-white">{duplicateConfigCount}</div>
                    <div className="mt-1 text-xs text-white/55">同模型多条配置</div>
                  </div>
                </div>

                <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="text-sm font-medium text-white">默认模型一键验证</div>
                    <p className="mt-1 text-xs leading-5 text-white/50">
                      只验证当前每类能力会被生产流程优先使用的配置，避免重复消耗额度。
                    </p>
                  </div>
                  <Button
                    type="button"
                    onClick={handleTestDefaultConfigs}
                    disabled={isTestingDefaults || activeDefaultConfigs.length === 0}
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    {isTestingDefaults ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <TestTube className="w-4 h-4 mr-2" />
                    )}
                    验证默认模型
                  </Button>
                </div>

                {healthIssues.length > 0 ? (
                  <div className="grid gap-2 md:grid-cols-2">
                    {healthIssues.slice(0, 6).map((issue) => (
                      <div
                        key={issue.key}
                        className={`rounded border px-3 py-2 text-xs ${
                          issue.level === 'danger'
                            ? 'border-red-400/20 bg-red-500/10 text-red-100'
                            : 'border-amber-400/20 bg-amber-500/10 text-amber-100'
                        }`}
                      >
                        {issue.text}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
                    当前默认模型配置完整且已验证，适合进入小说到动漫视频的生产流程。
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-violet-300" />
                  动漫模型预设
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-3">
                  {ANIME_MODEL_PRESETS.map((preset) => {
                    const missingCapabilities = preset.capabilities.filter((capability) => {
                      const config = getDefaultConfigForCapability(productionSavedConfigs, capability);
                      return config?.test_status !== 'success';
                    });
                    const ready = missingCapabilities.length === 0;
                    const nextCapability = missingCapabilities[0] || preset.capabilities[0];
                    return (
                      <div key={preset.name} className="rounded-lg border border-white/10 bg-black/20 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-white">{preset.name}</div>
                            <div className="mt-1 text-xs leading-5 text-white/45">{preset.description}</div>
                          </div>
                          <span className={`shrink-0 rounded border px-2 py-0.5 text-xs ${
                            ready
                              ? 'border-emerald-400/20 bg-emerald-500/15 text-emerald-100'
                              : 'border-yellow-400/20 bg-yellow-500/15 text-yellow-100'
                          }`}>
                            {ready ? '可用' : `缺 ${missingCapabilities.length} 项`}
                          </span>
                        </div>
                        <div className="mt-3 text-xs leading-5 text-white/50">{preset.target}</div>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {preset.capabilities.map((capability) => {
                            const config = getDefaultConfigForCapability(productionSavedConfigs, capability);
                            const verified = config?.test_status === 'success';
                            return (
                              <span
                                key={`${preset.name}-${capability}`}
                                className={`rounded px-2 py-1 text-xs ${
                                  verified
                                    ? 'bg-emerald-500/15 text-emerald-100'
                                    : config
                                      ? 'bg-yellow-500/15 text-yellow-100'
                                      : 'bg-white/10 text-white/45'
                                }`}
                              >
                                {MODEL_CAPABILITY_LABELS[capability]}
                              </span>
                            );
                          })}
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => focusCapabilitySetup(nextCapability)}
                          className="mt-3 h-8 w-full border border-white/10 text-white/70 hover:bg-white/10 hover:text-white"
                        >
                          {ready ? '查看默认模型' : `补齐${MODEL_CAPABILITY_LABELS[nextCapability]}`}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <ClipboardList className="w-5 h-5 text-cyan-300" />
                  动漫制作任务推荐
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2">
                  {PRODUCTION_TASK_REQUIREMENTS.map((task) => {
                    const ready = task.capabilities.every((capability) => getDefaultConfigForCapability(productionSavedConfigs, capability)?.test_status === 'success');
                    return (
                      <div key={task.name} className="rounded-lg border border-white/10 bg-black/20 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-white">{task.name}</div>
                            <div className="mt-1 text-xs leading-5 text-white/45">{task.description}</div>
                          </div>
                          <span className={`shrink-0 rounded border px-2 py-0.5 text-xs ${
                            ready
                              ? 'border-emerald-400/20 bg-emerald-500/15 text-emerald-100'
                              : 'border-yellow-400/20 bg-yellow-500/15 text-yellow-100'
                          }`}>
                            {ready ? '就绪' : '待完善'}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {task.capabilities.map((capability) => {
                            const config = getDefaultConfigForCapability(productionSavedConfigs, capability);
                            const verified = config?.test_status === 'success';
                            return (
                              <button
                                key={`${task.name}-${capability}`}
                                type="button"
	                        onClick={() => focusCapabilitySetup(capability)}
                                className={`rounded px-2 py-1 text-xs ${
                                  verified
                                    ? 'bg-emerald-500/15 text-emerald-100'
                                    : config
                                      ? 'bg-yellow-500/15 text-yellow-100'
                                      : 'bg-white/10 text-white/45'
                                }`}
                              >
                                {MODEL_CAPABILITY_LABELS[capability]}
                                {verified ? ' 已验证' : config ? ' 未验证' : ' 未配置'}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card ref={configFormRef} className="scroll-mt-6 bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-violet-400" />
                  选择模型
                </CardTitle>
              </CardHeader>
              <CardContent>
                {/* 标签切换 */}
                <div className="flex flex-wrap gap-2 mb-4">
                  {providerTabs.map((provider) => (
                    <Button
                      key={provider.id}
                      variant={activeTab === provider.id ? 'default' : 'outline'}
                      onClick={() => setActiveTab(provider.id)}
                      className={activeTab === provider.id ? 'bg-violet-600' : 'border-white/10'}
                    >
                      {provider.name_cn || provider.name}
                    </Button>
                  ))}
                </div>

                {activeProvider?.description && (
                  <div className="mb-4 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-white/60">
                    <div className="font-medium text-white/80">{activeProvider.name_cn || activeProvider.name}</div>
                    <div className="mt-1">{activeProvider.description}</div>
                    {activeProvider.id === 'volcano_agent_plan' && (
                      <div className="mt-2 text-amber-200/80">
                        Agent Plan 需使用专属 API Key 和包含 /api/plan/v3 的专属 Base URL，请不要和普通火山方舟 Key 混用。
                      </div>
                    )}
                  </div>
                )}

                {/* 服务商模型 */}
                {activeTab !== 'external' && (
                  <div className="space-y-3">
                    <div className="rounded-lg border border-cyan-400/20 bg-cyan-500/10 p-3">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <div className="text-sm font-medium text-cyan-50">新手模式：只显示推荐和常用模型</div>
                          <p className="mt-1 text-xs leading-5 text-cyan-100/70">
                            内部测试模型会默认隐藏；未配置的 TTS/声音模型默认收起，切到“语音/声音”或打开高级模型后再选择。
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setShowAdvancedModels((value) => !value)}
                          className={`shrink-0 rounded-md border px-3 py-2 text-xs transition-colors ${
                            showAdvancedModels
                              ? 'border-cyan-300/50 bg-cyan-500/20 text-cyan-50'
                              : 'border-white/10 bg-white/5 text-white/65 hover:bg-white/10 hover:text-white'
                          }`}
                        >
                          {showAdvancedModels ? '隐藏测试/高级模型' : `显示测试/高级模型${hiddenModelCount > 0 ? `（${hiddenModelCount}）` : ''}`}
                        </button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 rounded-lg border border-white/10 bg-black/20 p-2">
                      {capabilityFilterOptions
                        .filter((option) => option.value === 'all' || option.count > 0 || selectedCapabilityFilter === option.value)
                        .map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => setSelectedCapabilityFilter(option.value)}
                            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors ${
                              selectedCapabilityFilter === option.value
                                ? 'bg-violet-600 text-white'
                                : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white'
                            }`}
                          >
                            <span>{option.label}</span>
                            <span className="rounded bg-black/20 px-1.5 py-0.5 text-[11px] text-white/60">
                              {option.count}
                            </span>
                          </button>
                        ))}
                    </div>
                    {filteredModels.length > 0 ? filteredModels.map((model) => {
                      const capabilities = getModelCapabilities(model);
                      const primaryCapability = getModelCapability(model);
                      const isVisionOnly = capabilities.includes('vision') && !capabilities.includes('image');
                      return (
                      <div
                        key={model.id}
                        onClick={() => setSelectedModel(model.id)}
                        className={`p-4 rounded-lg border cursor-pointer transition-all ${
                          selectedModel === model.id
                            ? 'border-violet-500 bg-violet-500/10'
                            : 'border-white/10 hover:border-violet-500/50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium flex items-center gap-2">
                              {model.model_type === 'chat' && <MessageSquare className="w-4 h-4 text-blue-400" />}
                              {model.model_type === 'vision' && <ImageIcon className="w-4 h-4 text-purple-400" />}
                              {model.model_type === 'video' && <Video className="w-4 h-4 text-pink-400" />}
                              {model.model_type === 'image-generation' && <ImageIcon className="w-4 h-4 text-orange-400" />}
                              {model.model_type === 'video-generation' && <Video className="w-4 h-4 text-red-400" />}
                              {model.model_type === 'image' && <ImageIcon className="w-4 h-4 text-orange-400" />}
                              {model.model_type === 'tts' && <Music className="w-4 h-4 text-green-400" />}
                              {model.model_type === 'embedding' && <Network className="w-4 h-4 text-cyan-400" />}
                              {model.model_name_cn || model.model_name}
                              {model.is_recommended && (
                                <span className="px-2 py-0.5 text-xs bg-violet-500/20 text-violet-400 rounded">
                                  推荐
                                </span>
                              )}
                              {capabilities.map((capability) => (
                                <span
                                  key={capability}
                                  className={`px-2 py-0.5 text-xs rounded ${
                                    capability === primaryCapability
                                      ? 'bg-white/15 text-white/70'
                                      : 'bg-white/10 text-white/45'
                                  }`}
                                >
                                  {MODEL_CAPABILITY_LABELS[capability]}
                                </span>
                              ))}
                              {model.user_configured && (
                                <span className="px-2 py-0.5 text-xs bg-cyan-500/15 text-cyan-100 rounded">
                                  已配置
                                </span>
                              )}
                              {model.user_is_default && (
                                <span className="px-2 py-0.5 text-xs bg-violet-500/20 text-violet-100 rounded">
                                  默认
                                </span>
                              )}
                              {model.user_configured && (
                                <span className={`px-2 py-0.5 text-xs rounded border ${modelStatusClass(model.user_test_status)}`}>
                                  {modelStatusLabel(model.user_test_status)}
                                </span>
                              )}
                            </div>
                            <div className="text-white/60 text-sm mt-1">
                              {model.model_type === 'image-generation' && '图像生成'}
                              {model.model_type === 'video-generation' && '视频生成'}
                              {model.model_type === 'image' && '图像生成'}
                              {model.model_type === 'tts' && '语音合成'}
                              {model.model_type === 'embedding' && `向量化 • 上下文${model.context_window}`}
                              {model.model_type === 'chat' && `上下文${model.context_window}`}
                              {!['image-generation', 'video-generation', 'chat', 'image', 'tts', 'embedding'].includes(model.model_type) && `上下文${model.context_window}`}
                              {model.model_type !== 'image-generation' && model.model_type !== 'video-generation' && model.model_type !== 'tts' && ` • 输入¥${model.input_cost_per_1k}/千token`}
                            </div>
                            {model.description && (
                              <div className="text-white/40 text-xs mt-1">{model.description}</div>
                            )}
                            {model.user_configured && (
                              <div className="mt-2 rounded border border-cyan-400/20 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-100">
                                当前用户已保存配置：{model.user_config_name || '未命名配置'}
                                {model.user_config_count && model.user_config_count > 1 ? `，共 ${model.user_config_count} 条` : ''}
                                。再次保存会更新已有配置，避免重复配置。
                              </div>
                            )}
                            {model.user_configured && model.user_test_status === 'failed' && model.user_test_message && (
                              <div className="mt-2 rounded border border-red-400/20 bg-red-500/10 px-2 py-1 text-xs text-red-100">
                                {model.user_test_message}
                              </div>
                            )}
                            {isVisionOnly && (
                              <div className="mt-2 rounded border border-amber-400/20 bg-amber-500/10 px-2 py-1 text-xs text-amber-100/90">
                                该模型用于图片理解、多模态分析和提示词辅助，不直接生成小说封面、角色头像或场景参考图。
                              </div>
                            )}
                          </div>
                          {selectedModel === model.id && (
                            <CheckCircle className="w-5 h-5 text-violet-400" />
                          )}
                        </div>
                      </div>
                      );
                    }) : (
                      <div className="text-center py-8 text-white/40">
                        <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>{hiddenModelCount > 0 ? '当前筛选下常用模型为空，可显示测试/高级模型查看更多。' : '暂无可用模型，请检查网络连接'}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* 外部API */}
                {activeTab === 'external' && (
                  <div className="space-y-3">
                    <div className="p-4 rounded-lg bg-white/5 border border-white/10">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-white/70 text-sm">
                          <Network className="w-4 h-4 inline mr-2" />
                          Sora、Veo、ComfyUI、FFmpeg 云渲染和口型适配已迁移到生产适配管理。
                        </div>
                        <a
                          href="/production-adapters"
                          className="inline-flex h-9 items-center justify-center rounded-md bg-violet-600 px-3 text-sm font-medium text-white hover:bg-violet-700"
                        >
                          <ExternalLink className="w-4 h-4 mr-2" />
                          打开生产适配
                        </a>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* 右侧：配置面板 */}
          <div className="space-y-4">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-cyan-300" />
                  能力默认模型
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {capabilityOrder.map((capability) => {
                  const configs = getConfigsByCapability(productionSavedConfigs, capability);
                  const defaultConfig = getDefaultConfigForCapability(productionSavedConfigs, capability);
                  return (
                    <div key={capability} className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-white">{MODEL_CAPABILITY_LABELS[capability]}</div>
                        <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-white/50">{configs.length} 个配置</span>
                      </div>
                      {defaultConfig ? (
                        <div className="mt-2 space-y-1 text-xs">
                          <div className="text-white/75">{defaultConfig.name}</div>
                          <div className="text-white/45">{defaultConfig.provider_name || defaultConfig.provider_id} / {defaultConfig.model_name}</div>
                          <div className="flex flex-wrap gap-1.5">
                            <span className="rounded bg-violet-500/15 px-2 py-0.5 text-violet-100">
                              {defaultConfig.is_default ? '默认' : '优先可用'}
                            </span>
                            <span className={`rounded border px-2 py-0.5 ${modelStatusClass(defaultConfig.test_status)}`}>
                              {modelStatusLabel(defaultConfig.test_status)}
                            </span>
                          </div>
                          {defaultConfig.test_status === 'failed' && defaultConfig.test_message && (
                            <div className="rounded border border-red-400/20 bg-red-500/10 px-2 py-1 text-red-100">
                              {defaultConfig.test_message}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="mt-2 text-xs text-yellow-100/70">
                          未配置，使用该能力时会提示先到本页新增并测试。
                        </div>
                      )}
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => focusCapabilitySetup(capability)}
                        className="mt-3 h-8 w-full border border-white/10 text-white/70 hover:bg-white/10 hover:text-white"
                      >
                        {defaultConfig ? '查看/调整' : '配置该能力'}
                      </Button>
                    </div>
                  );
                })}
                <p className="text-xs leading-5 text-white/40">
                  默认配置按能力类别独立生效，视频、语音、文本互不覆盖。视觉多模态用于图片理解和参考分析，不替代真正的图像生成模型。
                </p>
              </CardContent>
            </Card>

            {/* API Key配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Key className="w-5 h-5" />
                  API Key 配置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 配置名称 */}
                <div>
                  <label className="block text-sm text-white/80 mb-2">配置名称</label>
                  <Input
                    ref={configNameInputRef}
                    placeholder="例如：我的豆包配置"
                    value={configName}
                    onChange={(e) => setConfigName(e.target.value)}
                    className="bg-white/5 border-white/10"
                  />
                </div>

                {/* 提供商 */}
                <div>
                  <label htmlFor="model-provider" className="block text-sm text-white/80 mb-2">服务商</label>
                  <Select id="model-provider"
                    value={selectedProvider}
	                    onChange={(e) => {
	                      setSelectedProvider(e.target.value);
	                      setActiveTab(e.target.value);
	                      setSelectedModel('');
	                      setLastPassedFormTest(null);
	                      setTestResult(null);
	                    }}
                    options={
                      providers.map(p => ({ value: p.id, label: p.name_cn || p.name }))
                    }
                    placeholder="选择服务商"
                  />
                  {/* 显示API地址信息 */}
                  {selectedProvider && providers.find(p => p.id === selectedProvider) && (
                    <div className="mt-2 p-2 rounded bg-white/5 border border-white/10">
                      <div className="flex items-center gap-2 text-xs text-white/60 mb-1">
                        <Globe className="w-3 h-3" />
                        <span>API地址（默认）</span>
                      </div>
                      <code className="text-xs text-violet-400 break-all">
                        {providers.find(p => p.id === selectedProvider)?.base_url}
                      </code>
                      {/* 各模型类型的实际端点 */}
                      {selectedProvider === 'volcano' && (
                        <div className="mt-1 text-xs text-white/40">
                          文本→/chat/completions | 图像→/images/generations | 视频→/contents/generations/tasks
                        </div>
                      )}
                      {selectedProvider === 'volcano_agent_plan' && (
                        <div className="mt-1 text-xs text-white/40">
                          Agent Plan 专属端点：文本→/chat/completions | 图像→/images/generations | 视频→/contents/generations/tasks
                          <br />需使用 Agent Plan 专属 API Key；Small 套餐不支持视频生成。
                        </div>
                      )}
                      {selectedProvider === 'minimax' && (
                        <div className="mt-1 text-xs text-white/40">
                          M3文本/多模态→api.minimaxi.com/v1/text/chatcompletion_v2 | 旧文本→/v1/chat/completions | 图像→/v1/image_generation | TTS→/v1/t2a_v2
                          <br/>国内/Agent Plan 常见 key 默认走 api.minimaxi.com；如使用海外账号，可在配置高级参数里覆盖 base_url。
                        </div>
                      )}
                      {selectedProvider === 'qianlian' && (
                        <div className="mt-1 text-xs text-white/40">
                          端点: /apps/anthropic/v1/messages
                        </div>
                      )}
                      {selectedProvider === 'dashscope' && (
                        <div className="mt-1 text-xs text-white/40">
                          端点: /chat/completions
                        </div>
                      )}
                      {selectedProvider === 'openai' && (
                        <div className="mt-1 text-xs text-white/40">
                          文本→/chat/completions | 图像→/images/generations | 视频→/videos/generations
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 模型 */}
                <div>
                  <label className="block text-sm text-white/80 mb-2">模型</label>
                  <Select
                    value={selectedModel}
                    onChange={(e) => {
                      setSelectedModel(e.target.value);
                      setLastPassedFormTest(null);
                    }}
                    options={
                      modelSelectOptions
                    }
                    placeholder="选择模型"
                  />
                  {filteredModels.length === 0 && (
                    <p className="text-white/40 text-xs mt-1">请先选择服务商</p>
                  )}
                  {selectedModelInfo && (
                    <div className="mt-1 space-y-1 text-xs">
                      <p className="text-white/45">API 模型 ID：{selectedModelInfo.model_id}</p>
                      {selectedCapabilities.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 text-white/45">
                          <span>能力类型：</span>
                          {selectedCapabilities.map((capability) => (
                            <span
                              key={capability}
                              className={`rounded px-2 py-0.5 ${
                                capability === selectedCapability
                                  ? 'bg-white/15 text-white/70'
                                  : 'bg-white/10 text-white/45'
                              }`}
                            >
                              {MODEL_CAPABILITY_LABELS[capability]}
                            </span>
                          ))}
                        </div>
                      )}
                      {selectedModelInfo.base_url && (
                        <p className="break-all text-white/45">模型专属 Base URL：{selectedModelInfo.base_url}</p>
                      )}
                      {selectedModelIsVisionOnly && (
                        <p className="rounded border border-amber-400/20 bg-amber-500/10 px-2 py-1 text-amber-100/90">
                          视觉多模态模型可用于图片理解、角色参考分析和图像提示词辅助；封面、头像、场景图生成仍请选择图像生成模型。
                        </p>
                      )}
                      {selectedModelInfo.user_configured && (
                        <p className="text-cyan-100/80">
                          当前用户已配置：{selectedModelInfo.user_config_name || '未命名配置'}，
                          状态：{modelStatusLabel(selectedModelInfo.user_test_status)}。
                          保存时将更新已有配置。
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* API Key */}
                <div>
	                  <label className="block text-sm text-white/80 mb-2">
	                    API Key {requiresApiKey ? <span className="text-red-400">*</span> : <span className="text-white/40">(留空沿用原 Key)</span>}
	                  </label>
	                  <Input
	                    type="password"
	                    placeholder={requiresApiKey ? (agentPlanSelected ? '请输入 Agent Plan 专属 API Key' : '请输入API Key') : '不修改 Key 可留空；输入新 Key 后请先测试'}
	                    value={apiKey}
	                    onChange={(e) => {
	                      setApiKey(e.target.value);
	                      setLastPassedFormTest(null);
	                    }}
	                    className="bg-white/5 border-white/10"
	                  />
	                  {!requiresApiKey && (
	                    <p className="mt-1 text-xs text-cyan-100/70">
	                      当前配置已有可用密钥。直接更新会保留原验证状态；如输入新 Key，测试通过并更新后会自动同步验证状态。
	                    </p>
	                  )}
                  {agentPlanSelected && (
                    <p className="mt-1 text-xs text-amber-200/80">
                      PDF 文档说明 Agent Plan API Key 与普通火山方舟 API Key 不能混用，Base URL 必须包含 /api/plan/v3。图像/视频模型测试只验证端点，不提交生成任务。
                    </p>
                  )}
                </div>

                {/* API Secret (可选) */}
                <div>
                  <label className="block text-sm text-white/80 mb-2">API Secret (可选)</label>
                  <Input
                    type="password"
                    placeholder="部分服务商需要"
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                    className="bg-white/5 border-white/10"
                  />
                </div>

                {/* 高级参数 */}
                <details className="group">
                  <summary className="text-sm text-white/60 cursor-pointer hover:text-white/80 flex items-center gap-1">
                    <ChevronRight className="w-4 h-4 transition-transform group-open:rotate-90" />
                    高级参数
                  </summary>
                  <div className="mt-3 space-y-3 pl-5">
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-sm text-white/60">Temperature</label>
                        <span className="text-sm text-white">{temperature}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="2"
                        step="0.1"
                        value={temperature}
                        onChange={(e) => setTemperature(parseFloat(e.target.value))}
                        className="w-full"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between mb-1">
                        <label className="text-sm text-white/60">Top P</label>
                        <span className="text-sm text-white">{topP}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={topP}
                        onChange={(e) => setTopP(parseFloat(e.target.value))}
                        className="w-full"
                      />
                    </div>
                    <div>
                      <label className="text-sm text-white/60">Max Tokens</label>
                      <Input
                        type="number"
                        value={maxTokens}
                        onChange={(e) => setMaxTokens(parseInt(e.target.value) || 2048)}
                        className="bg-white/5 border-white/10 mt-1"
                      />
                    </div>
                  </div>
                </details>

                {/* 设为默认 */}
                <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isDefault}
                    onChange={(e) => setIsDefault(e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-white/5"
                  />
                  设为默认配置
                </label>

                {/* 测试结果 */}
                {testResult && (
                  <div className={`p-3 rounded-lg flex items-start gap-2 ${
                    testResult.success
                      ? 'bg-green-500/10 border border-green-500/20'
                      : 'bg-red-500/10 border border-red-500/20'
                  }`}>
                    {testResult.success ? (
                      <CheckCircle className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                    )}
                    <div className="flex-1">
                      <p className={testResult.success ? 'text-green-400' : 'text-red-400'}>
                        {testResult.message}
                      </p>
                      {testResult.response && (
                        <p className="text-white/60 text-xs mt-1 truncate">{testResult.response}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* 按钮 */}
                <div className="flex gap-2">
                  <Button
                    onClick={handleTest}
                    disabled={isTesting || !canTestCurrentForm}
                    variant="outline"
                    className="flex-1"
                  >
                    {isTesting ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        测试中
                      </>
                    ) : (
                      <>
                        <TestTube className="w-4 h-4 mr-2" />
                        测试连接
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={isLoading || !canSaveCurrentForm}
                    className="flex-1 bg-violet-600 hover:bg-violet-700"
                  >
                    {isLoading ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <CheckCircle className="w-4 h-4 mr-2" />
                    )}
                    {editingConfig || selectedModelExistingConfig ? '更新配置' : '保存配置'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* 已保存配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  已保存配置
                  <span className="text-xs text-white/40 ml-auto">
                    {visibleSavedConfigs.length}个{!showAdvancedModels && savedConfigs.length > visibleSavedConfigs.length ? `，已隐藏 ${savedConfigs.length - visibleSavedConfigs.length} 个测试/高级配置` : ''}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {visibleSavedConfigs.length > 0 ? (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {visibleSavedConfigs.map((config) => (
                      <div
                        key={config.id}
                        className="p-3 rounded-lg bg-white/5 border border-white/10"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium flex items-center gap-1">
                              {config.name}
                              {config.is_default && (
                                <span className="px-1.5 py-0.5 text-xs bg-violet-500/20 text-violet-400 rounded">
                                  {MODEL_CAPABILITY_LABELS[getModelCapability(config)]}默认
                                </span>
                              )}
                            </div>
                            <div className="text-white/60 text-xs mt-0.5">
                              {config.provider_name} / {config.model_name} • 使用{config.usage_count}次
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleTestConfig(config)}
                              title="测试"
                              className="text-blue-400 hover:text-blue-300"
                            >
                              <TestTube className="w-3 h-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleSetDefault(config.id)}
                              title="设为默认"
                            >
                              <CheckCircle className="w-3 h-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleEdit(config)}
                              title="编辑"
                              className="text-white/60 hover:text-white"
                            >
                              <Edit2 className="w-3 h-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDelete(config.id)}
                              title="删除"
                              className="text-red-400 hover:text-red-300"
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          </div>
                        </div>
                        {config.test_status && (
                          <div className="flex items-center gap-1 mt-1">
                            {config.test_status === 'success' ? (
                              <CheckCircle className="w-3 h-3 text-green-400" />
                            ) : (
                              <XCircle className="w-3 h-3 text-red-400" />
                            )}
                            <span className={`text-xs ${
                              config.test_status === 'success' ? 'text-green-400' : config.test_status === 'failed' ? 'text-red-400' : 'text-yellow-300'
                            }`}>
                              {modelStatusLabel(config.test_status)}
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-white/40">
                    <Key className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无已保存的配置</p>
                    <p className="text-sm">在上方输入API Key并保存</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 帮助信息 */}
            <Card className="bg-blue-600/10 border-blue-500/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-blue-300 mb-2 flex items-center gap-2">
                  <ExternalLink className="w-4 h-4" />
                  如何获取API Key?
                </h4>
                <ul className="text-sm text-white/60 space-y-1">
                  <li>• <strong className="text-white/80">火山引擎:</strong> <a href="https://www.volcengine.com" target="_blank" className="text-violet-400 hover:underline">volcengine.com</a></li>
                  <li>• <strong className="text-white/80">火山方舟 Agent Plan:</strong> <a href="https://console.volcengine.com/ark" target="_blank" className="text-violet-400 hover:underline">Agent Plan 控制台</a></li>
                  <li>• <strong className="text-white/80">阿里百炼:</strong> <a href="https://bailian.console.aliyun.com" target="_blank" className="text-violet-400 hover:underline">阿里云百炼</a></li>
                  <li>• <strong className="text-white/80">阿里千问:</strong> <a href="https://dashscope.console.aliyun.com" target="_blank" className="text-violet-400 hover:underline">阿里云DashScope</a></li>
                </ul>
              </CardContent>
            </Card>

            {/* 错误码说明 */}
            <Card className="bg-amber-600/10 border-amber-500/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-amber-300 mb-2 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  常见错误说明
                </h4>
                <ul className="text-xs text-white/60 space-y-1">
                  <li>🔑 <strong className="text-white/80">Key无效:</strong> API Key格式或值错误</li>
                  <li>🌐 <strong className="text-white/80">网络失败:</strong> 网络不通或API地址错误</li>
                  <li>⏱️ <strong className="text-white/80">配额用完:</strong> 当月用量已达上限</li>
                  <li>🖥️ <strong className="text-white/80">服务端错误:</strong> 服务商服务器异常</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
