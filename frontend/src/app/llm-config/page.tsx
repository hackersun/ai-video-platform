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
  Edit2
} from 'lucide-react';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import {
  MODEL_CAPABILITY_LABELS,
  getConfigsByCapability,
  getDefaultConfigForCapability,
  getModelCapability,
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
  context_window: number;
  max_tokens: number;
  input_cost_per_1k: number;
  output_cost_per_1k: number;
  is_recommended?: boolean;
  description?: string;
  user_config_id?: string;
  user_config_name?: string;
  user_configured?: boolean;
  user_config_count?: number;
  user_is_default?: boolean;
  user_test_status?: string | null;
  user_test_message?: string | null;
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
  usage_count: number;
  api_key?: string;
}

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
  const [testResult, setTestResult] = useState<{success: boolean; message: string; response?: string} | null>(null);

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

  const currentProvider = providers.find(p => p.id === selectedProvider);
  const providerTabs = providers.filter((provider) => provider.id !== 'external');
  const activeProvider = providers.find((provider) => provider.id === activeTab);
  const filteredModels = models.filter(m => m.provider_id === selectedProvider);
  const selectedModelInfo = models.find(m => m.id === selectedModel);
  const selectedModelExistingConfig = selectedModelInfo?.user_config_id
    ? savedConfigs.find(config => config.id === selectedModelInfo.user_config_id)
    : undefined;
  const agentPlanSelected = selectedProvider === 'volcano_agent_plan';
  const capabilityOrder: ModelCapability[] = ['text', 'image', 'audio', 'video', 'embedding'];
  const selectedCapability = selectedModelInfo ? getModelCapability(selectedModelInfo) : null;
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
        const data = await res.json();
        setProviders(data);
        if (data.length > 0 && !selectedProvider) {
          setSelectedProvider(data[0].id);
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
    fetchModels(nextProvider);
  }, [activeTab]);

  // 测试连接
  const handleTest = async () => {
    if (!apiKey) {
      setTestResult({ success: false, message: '请输入API Key' });
      return;
    }

    if (!selectedModel) {
      setTestResult({ success: false, message: '请先选择一个模型' });
      return;
    }

    setIsTesting(true);
    setTestResult(null);

    try {
      const model = models.find(m => m.id === selectedModel);
      const provider = providers.find(p => p.id === selectedProvider);

      const testRes = await fetchWithAuth(`${API_BASE_URL}/llm/configs/test`, {
        method: 'POST',
        body: JSON.stringify({
          api_key: apiKey,
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
        // MiniMax: 自动根据key前缀判断端点
        const baseUrl = key.startsWith('sk-cp-')
          ? 'https://api.minimax.io/v1'
          : 'https://api.minimaxi.com/v1';
        const res = await fetch(`${baseUrl}/chat/completions`, {
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
    if (!apiKey) {
      setTestResult({ success: false, message: '请输入API Key' });
      return;
    }
    if (!selectedModel) {
      setTestResult({ success: false, message: '请选择模型' });
      return;
    }

    setIsLoading(true);
    try {
      const updatingExisting = !editingConfig && selectedModelInfo?.user_config_id;
      const url = editingConfig
        ? `${API_BASE_URL}/llm/configs/${editingConfig.id}`
        : updatingExisting
          ? `${API_BASE_URL}/llm/configs/${selectedModelInfo.user_config_id}`
          : `${API_BASE_URL}/llm/configs`;
      const res = await fetchWithAuth(url, {
        method: editingConfig || updatingExisting ? 'PUT' : 'POST',
        body: JSON.stringify({
          model_id: selectedModel,
          name: configName,
          api_key: apiKey,
          api_secret: apiSecret,
          temperature,
          top_p: topP,
          max_tokens: maxTokens,
          extra_params: agentPlanSelected ? { base_url: currentProvider?.base_url } : undefined,
          is_default: isDefault
        })
      });

      if (res.ok) {
        const saved = await res.json();
        setTestResult({ success: true, message: editingConfig || updatingExisting ? '已有配置已更新，不会重复创建。' : '配置已保存成功！' });
        await fetchConfigs();
        await fetchModels(selectedProvider || undefined);
        setSelectedModel(saved.config_model_id || selectedModel);
        setEditingConfig(null);
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
        setSavedConfigs(prev => prev.map(c => ({
          ...c,
          is_default: c.id === configId
        })));
        setTestResult({ success: true, message: '已设为默认配置' });
      }
    } catch (error) {
      setTestResult({ success: false, message: '设置失败' });
    }
  };

  // 编辑配置
  const handleEdit = (config: SavedConfig) => {
    setEditingConfig(config);
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
      if (data.success) {
        setSavedConfigs(prev => prev.map(c =>
          c.id === config.id
            ? { ...c, test_status: 'success', test_message: data.message }
            : c
        ));
      }
    } catch (error) {
      setTestResult({ success: false, message: '测试请求失败' });
    }

    setIsTesting(false);
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
                    {filteredModels.length > 0 ? filteredModels.map((model) => {
                      const capability = getModelCapability(model);
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
                              <span className="px-2 py-0.5 text-xs bg-white/10 text-white/55 rounded">
                                {MODEL_CAPABILITY_LABELS[capability]}
                              </span>
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
                        <p>暂无可用模型，请检查网络连接</p>
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
                  const configs = getConfigsByCapability(savedConfigs, capability);
                  const defaultConfig = getDefaultConfigForCapability(savedConfigs, capability);
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
                        </div>
                      ) : (
                        <div className="mt-2 text-xs text-yellow-100/70">
                          未配置，使用该能力时会提示先到本页新增并测试。
                        </div>
                      )}
                    </div>
                  );
                })}
                <p className="text-xs text-white/40">
                  默认配置按能力类别独立生效，设置视频默认不会覆盖文本默认。
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
                  <label className="block text-sm text-white/80 mb-2">服务商</label>
                  <Select
                    value={selectedProvider}
                    onChange={(e) => {
                      setSelectedProvider(e.target.value);
                      setActiveTab(e.target.value);
                      setSelectedModel('');
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
                          文本→/v1/chat/completions | 图像→/v1/image_generation | TTS→/v1/t2a_v2
                          <br/>sk-api-前缀→国内(api.minimaxi.com) | sk-cp-前缀→海外(api.minimax.io)
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
                    onChange={(e) => setSelectedModel(e.target.value)}
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
                      {selectedCapability && (
                        <p className="text-white/45">能力类型：{MODEL_CAPABILITY_LABELS[selectedCapability]}</p>
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
                    API Key <span className="text-red-400">*</span>
                  </label>
                  <Input
                    type="password"
                    placeholder={agentPlanSelected ? '请输入 Agent Plan 专属 API Key' : '请输入API Key'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="bg-white/5 border-white/10"
                  />
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
                    disabled={isTesting || !apiKey || !selectedModel}
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
                    disabled={isLoading || !configName || !apiKey || !selectedModel}
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
                  <span className="text-xs text-white/40 ml-auto">{savedConfigs.length}个</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {savedConfigs.length > 0 ? (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {savedConfigs.map((config) => (
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
