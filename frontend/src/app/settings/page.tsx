"""
前端配置页面 V2 - 完善编辑功能
"""
"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toaster";
import { 
  Key, 
  Plus, 
  Trash2, 
  Edit2, 
  Check, 
  X,
  Server,
  Brain,
  Eye,
  EyeOff,
  RefreshCw,
  Loader2,
  BarChart3,
  Calendar
} from "lucide-react";
import { cn } from "@/lib/utils";

// 类型定义
interface Provider {
  id: number;
  code: string;
  name: string;
  description: string;
  base_url: string;
  is_active: boolean;
}

interface APIKey {
  id: number;
  provider_id: number;
  key_name: string;
  is_default: boolean;
  is_active: boolean;
  usage_count: number;
  last_used_at: string | null;
  created_at: string;
}

interface AIModel {
  id: number;
  provider_id: number;
  model_code: string;
  model_name: string;
  model_type: string;
  description: string;
  max_tokens: number;
  temperature: number;
  top_p: number;
  context_window: number;
  is_active: boolean;
  is_default: boolean;
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"providers" | "keys" | "models" | "stats">("providers");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [models, setModels] = useState<AIModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [timeRange, setTimeRange] = useState<"today" | "week" | "month">("today");
  
  // 编辑状态
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [editingModel, setEditingModel] = useState<AIModel | null>(null);
  const [editingKey, setEditingKey] = useState<APIKey | null>(null);
  
  // 添加密钥表单
  const [newKey, setNewKey] = useState({
    provider_id: 0,
    key_name: "",
    key_value: "",
    is_default: false
  });
  const [showKeyValue, setShowKeyValue] = useState(false);

  // 加载数据
  const loadData = async () => {
    setLoading(true);
    try {
      const [providersRes, keysRes, modelsRes] = await Promise.all([
        fetch("/api/v1/config/providers").then(r => r.json()),
        fetch("/api/v1/config/keys").then(r => r.json()),
        fetch("/api/v1/config/models").then(r => r.json())
      ]);
      setProviders(providersRes);
      setApiKeys(keysRes);
      setModels(modelsRes);
    } catch (error) {
      toast({ title: "加载数据失败", variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // ============ 服务商编辑 ============
  const handleUpdateProvider = async (provider: Provider) => {
    try {
      const response = await fetch(`/api/v1/config/providers/${provider.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(provider)
      });
      
      if (response.ok) {
        toast({ title: "更新成功", variant: "success" });
        setEditingProvider(null);
        loadData();
      } else {
        toast({ title: "更新失败", variant: "error" });
      }
    } catch (error) {
      toast({ title: "更新失败", variant: "error" });
    }
  };

  // ============ 模型编辑 ============
  const handleUpdateModel = async (model: AIModel) => {
    try {
      const response = await fetch(`/api/v1/config/models/${model.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_tokens: model.max_tokens,
          temperature: model.temperature,
          top_p: model.top_p,
          context_window: model.context_window,
          is_default: model.is_default
        })
      });
      
      if (response.ok) {
        toast({ title: "更新成功", variant: "success" });
        setEditingModel(null);
        loadData();
      } else {
        toast({ title: "更新失败", variant: "error" });
      }
    } catch (error) {
      toast({ title: "更新失败", variant: "error" });
    }
  };

  // ============ 密钥管理 ============
  const handleAddKey = async () => {
    if (!newKey.provider_id || !newKey.key_name || !newKey.key_value) {
      toast({ title: "请填写完整信息", variant: "error" });
      return;
    }
    
    try {
      const response = await fetch("/api/v1/config/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newKey)
      });
      
      if (response.ok) {
        toast({ title: "添加成功", variant: "success" });
        setNewKey({ provider_id: 0, key_name: "", key_value: "", is_default: false });
        loadData();
      } else {
        toast({ title: "添加失败", variant: "error" });
      }
    } catch (error) {
      toast({ title: "添加失败", variant: "error" });
    }
  };

  const handleUpdateKey = async (key: APIKey) => {
    try {
      const response = await fetch(`/api/v1/config/keys/${key.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key_name: key.key_name,
          is_default: key.is_default
        })
      });
      
      if (response.ok) {
        toast({ title: "更新成功", variant: "success" });
        setEditingKey(null);
        loadData();
      } else {
        toast({ title: "更新失败", variant: "error" });
      }
    } catch (error) {
      toast({ title: "更新失败", variant: "error" });
    }
  };

  const handleDeleteKey = async (keyId: number) => {
    if (!confirm("确定要删除这个密钥吗？")) return;
    
    try {
      const response = await fetch(`/api/v1/config/keys/${keyId}`, { method: "DELETE" });
      if (response.ok) {
        toast({ title: "删除成功", variant: "success" });
        loadData();
      }
    } catch (error) {
      toast({ title: "删除失败", variant: "error" });
    }
  };

  const handleTestKey = async (keyId: number) => {
    try {
      const response = await fetch(`/api/v1/config/test-key/${keyId}`, { method: "POST" });
      const result = await response.json();
      
      if (response.ok) {
        toast({ title: "测试成功", description: result.message, variant: "success" });
      } else {
        toast({ title: "测试失败", description: result.detail, variant: "error" });
      }
    } catch (error) {
      toast({ title: "测试失败", variant: "error" });
    }
  };

  // 获取服务商名称
  const getProviderName = (providerId: number) => {
    const provider = providers.find(p => p.id === providerId);
    return provider?.name || "未知";
  };

  // 统计计算
  const getStats = () => {
    const totalKeys = apiKeys.length;
    const activeKeys = apiKeys.filter(k => k.is_active).length;
    const totalUsage = apiKeys.reduce((sum, k) => sum + (k.usage_count || 0), 0);
    const totalModels = models.length;
    
    return { totalKeys, activeKeys, totalUsage, totalModels };
  };

  const stats = getStats();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">系统配置</h1>
          
          {/* 统计概览 */}
          <div className="flex gap-4">
            <div className="px-4 py-2 rounded-lg bg-white/5">
              <span className="text-sm text-white/60">服务商</span>
              <span className="ml-2 font-sem