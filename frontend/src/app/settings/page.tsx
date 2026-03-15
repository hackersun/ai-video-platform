"""
前端配置页面 - 系统设置页面
实现服务商管理、API密钥配置、模型配置
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
  Edit, 
  Check, 
  X,
  Server,
  Brain,
  Settings,
  Eye,
  EyeOff,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";

// 服务商类型
interface Provider {
  id: number;
  code: string;
  name: string;
  description: string;
  base_url: string;
  is_active: boolean;
}

// API密钥类型
interface APIKey {
  id: number;
  provider_id: number;
  key_name: string;
  is_default: boolean;
  is_active: boolean;
  usage_count: number;
}

// AI模型类型
interface AIModel {
  id: number;
  provider_id: number;
  model_code: string;
  model_name: string;
  model_type: string;
  max_tokens: number;
  temperature: number;
  top_p: number;
  context_window: number;
  is_active: boolean;
  is_default: boolean;
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"providers" | "keys" | "models">("providers");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [models, setModels] = useState<AIModel[]>([]);
  const [loading, setLoading] = useState(false);
  
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
      console.error("加载数据失败", error);
      toast({ title: "加载数据失败", variant: "error" });
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    loadData();
  }, []);
  
  // 添加API密钥
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
        const error = await response.json();
        toast({ title: "添加失败", description: error.detail || "未知错误", variant: "error" });
      }
    } catch (error) {
      toast({ title: "添加失败", variant: "error" });
    }
  };
  
  // 删除API密钥
  const handleDeleteKey = async (keyId: number) => {
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
  
  // 测试API密钥
  const handleTestKey = async (keyId: number) => {
    try {
      const response = await fetch(`/api/v1/config/test-key/${keyId}`, { method: "POST" });
      const result = await response.json();
      
      if (response.ok) {
        toast({ title: "测试成功", description: result.message, variant: "success" });
      } else {
        toast({ title: "测试失败", description: result.detail || "未知错误", variant: "error" });
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

  return (
    <div className="min-h-screen bg-[#0a0a0f] p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">系统配置</h1>
        
        {/* 标签页 */}
        <div className="flex gap-2 mb-6">
          <Button 
            variant={activeTab === "providers" ? "primary" : "outline"}
            onClick={() => setActiveTab("providers")}
          >
            <Server className="w-4 h-4 mr-2" />
            服务商
          </Button>
          <Button 
            variant={activeTab === "keys" ? "primary" : "outline"}
            onClick={() => setActiveTab("keys")}
          >
            <Key className="w-4 h-4 mr-2" />
            API密钥
          </Button>
          <Button 
            variant={activeTab === "models" ? "primary" : "outline"}
            onClick={() => setActiveTab("models")}
          >
            <Brain className="w-4 h-4 mr-2" />
            AI模型
          </Button>
        </div>
        
        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
          </div>
        )}
        
        {/* 服务商管理 */}
        {activeTab === "providers" && !loading && (
          <Card>
            <CardHeader>
              <CardTitle>服务商管理</CardTitle>
              <CardDescription>管理AI服务提供商</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {providers.map(provider => (
                  <div 
                    key={provider.id}
                    className="p-4 rounded-lg bg-white/5 border border-white/10"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold">{provider.name}</h3>
                      {provider.is_active ? (
                        <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded">
                          启用
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs bg-red-500/20 text-red-400 rounded">
                          禁用
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-white/60 mb-2">{provider.description}</p>
                    <p className="text-xs text-white/40">代码: {provider.code}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
        
        {/* API密钥管理 */}
        {activeTab === "keys" && !loading && (
          <div className="space-y-6">
            {/* 添加密钥表单 */}
            <Card>
              <CardHeader>
                <CardTitle>添加API密钥</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-1.5">
                      选择服务商
                    </label>
                    <select 
                      className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white"
                      value={newKey.provider_id}
                      onChange={(e) => setNewKey({...newKey, provider_id: Number(e.target.value)})}
                    >
                      <option value={0}>选择服务商</option>
                      {providers.map(p => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                  
                  <Input
                    label="密钥名称"
                    placeholder="如：生产环境密钥"
                    value={newKey.key_name}
                    onChange={(e) => setNewKey({...newKey, key_name: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-1.5">
                    API密钥
                  </label>
                  <div className="relative">
                    <Input
                      type={showKeyValue ? "text" : "password"}
                      placeholder="输入API密钥"
                      value={newKey.key_value}
                      onChange={(e) => setNewKey({...newKey, key_value: e.target.value})}
                    />
                    <button
                      type="button"
                      onClick={() => setShowKeyValue(!showKeyValue)}
                      className="absolute right-3 top-[38px] text-white/40 hover:text-white"
                    >
                      {showKeyValue ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_default"
                    checked={newKey.is_default}
                    onChange={(e) => setNewKey({...newKey, is_default: e.target.checked})}
                    className="w-4 h-4 rounded border-white/20 bg-white/5"
                  />
                  <label htmlFor="is_default" className="text-sm text-white/80">
                    设为默认密钥
                  </label>
                </div>
                
                <Button onClick={handleAddKey}>
                  <Plus className="w-4 h-4 mr-2" />
                  添加密钥
                </Button>
              </CardContent>
            </Card>
            
            {/* 密钥列表 */}
            <Card>
              <CardHeader>
                <CardTitle>已配置的密钥</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {apiKeys.map(key => (
                    <div 
                      key={key.id}
                      className="flex items-center justify-between p-4 rounded-lg bg-white/5"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{key.key_name}</span>
                          {key.is_default && (
                            <span className="px-2 py-0.5 text-xs bg-violet-500/20 text-violet-400 rounded">
                              默认
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-white/40">
                          服务商: {getProviderName(key.provider_id)}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleTestKey(key.id)}
                        >
                          <RefreshCw className="w-4 h-4 mr-1" />
                          测试
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          className="text-red-400 hover:text-red-300"
                          onClick={() => handleDeleteKey(key.id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  
                  {apiKeys.length === 0 && (
                    <p className="text-center text-white/40 py-8">
                      暂无配置的密钥
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
        
        {/* AI模型配置 */}
        {activeTab === "models" && !loading && (
          <Card>
            <CardHeader>
              <CardTitle>AI模型配置</CardTitle>
              <CardDescription>配置模型参数和默认值</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {models.map(model => (
                  <div 
                    key={model.id}
                    className="p-4 rounded-lg bg-white/5 border border-white/10"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h3 className="font-medium">{model.model_name}</h3>
                        <p className="text-xs text-white/40">{model.model_code}</p>
                      </div>
                      <div className="flex gap-1">
                        {model.is_default && (
                          <span className="px-2 py-0.5 text-xs bg-violet-500/20 text-violet-400 rounded">
                            默认
                          </span>
                        )}
                        <span className={cn(
                          "px-2 py-0.5 text-xs rounded",
                          model.model_type === "llm" ? "bg-blue-500/20 text-blue-400" :
                          model.model_type === "image" ? "bg-pink-500/20 text-pink-400" :
                          "bg-green-500/20 text-green-400"
                        )}>
                          {model.model_type}
                        </span>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-xs text-white/60 mt-3">
                      <div>
                        <span className="text-white/40">Max Tokens:</span> {model.max_tokens}
                      </div>
                      <div>
                        <span className="text-white/40">Temperature:</span> {model.temperature}
                      </div>
                      <div>
                        <span className="text-white/40">Top P:</span> {model.top_p}
                      </div>
                      <div>
                        <span className="text-white/40">Context:</span> {model.context_window}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}