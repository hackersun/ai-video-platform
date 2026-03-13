'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';

interface Provider {
  id: string;
  name: string;
  logo: string;
  description: string;
  type: string;
  models: string[];
  required_params: string[];
}

interface APIKey {
  id: string;
  provider_id: string;
  provider_name: string;
  name: string;
  masked_credentials: Record<string, string>;
  is_active: boolean;
  is_default: boolean;
  models: string[];
  created_at: string;
}

export default function APIKeysPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [apiKeys, setAPIKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  
  // 表单状态
  const [formData, setFormData] = useState({
    name: '',
    api_key: '',
    secret_key: '',
    server_id: '',
    channel_id: '',
  });

  useEffect(() => {
    loadProviders();
    loadAPIKeys();
  }, []);

  const loadProviders = async () => {
    try {
      const res = await fetch('/api/v1/api-keys/providers');
      const data = await res.json();
      setProviders(data.items || []);
    } catch (error) {
      console.error('加载提供商失败:', error);
    }
  };

  const loadAPIKeys = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/api-keys');
      const data = await res.json();
      setAPIKeys(data.items || []);
    } catch (error) {
      console.error('加载API密钥失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedProvider || !formData.api_key) return;

    try {
      const res = await fetch('/api/v1/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider_id: selectedProvider.id,
          name: formData.name || selectedProvider.name,
          api_key: formData.api_key,
          secret_key: formData.secret_key || undefined,
          server_id: formData.server_id || undefined,
          channel_id: formData.channel_id || undefined,
        }),
      });

      if (res.ok) {
        setAddDialogOpen(false);
        setFormData({ name: '', api_key: '', secret_key: '', server_id: '', channel_id: '' });
        loadAPIKeys();
      }
    } catch (error) {
      console.error('保存失败:', error);
    }
  };

  const handleDelete = async (keyId: string) => {
    if (!confirm('确定删除此API密钥?')) return;
    
    try {
      await fetch(`/api/v1/api-keys/${keyId}`, { method: 'DELETE' });
      loadAPIKeys();
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  const handleToggle = async (keyId: string, active: boolean) => {
    try {
      await fetch(`/api/v1/api-keys/${keyId}/toggle?active=${active}`, { 
        method: 'POST' 
      });
      loadAPIKeys();
    } catch (error) {
      console.error('切换状态失败:', error);
    }
  };

  const handleSetDefault = async (keyId: string) => {
    try {
      await fetch(`/api/v1/api-keys/${keyId}/default`, { method: 'POST' });
      loadAPIKeys();
    } catch (error) {
      console.error('设置默认失败:', error);
    }
  };

  const providerLogos: Record<string, string> = {
    openai: '🤖',
    anthropic: '🧠',
    volcengine: '🌋',
    doubao: '🫛',
    kimi: '🌙',
    midjourney: '🎨',
    runway: '🎬',
    pika: '🎥',
    suno: '🎵',
    elevenlabs: '🔊',
  };

  const typeNames: Record<string, string> = {
    text_generation: '文本生成',
    image_generation: '图像生成',
    video_generation: '视频生成',
    voice_synthesis: '语音合成',
    music_generation: '音乐生成',
    multi: '多类型',
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', padding: '2rem' }}>
      <div style={{ maxWidth: '80rem', margin: '0 auto' }}>
        {/* 页面标题 */}
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white' }}>
            🔑 API密钥配置
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.6)', marginTop: '0.5rem' }}>
            配置您的AI服务API密钥，连接各种大模型服务
          </p>
        </div>

        {/* 已配置的API密钥 */}
        <Card style={{ backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', marginBottom: '2rem' }}>
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <CardTitle style={{ color: 'white' }}>已配置的密钥</CardTitle>
              <Button onClick={() => setAddDialogOpen(true)} style={{ backgroundColor: '#7c3aed' }}>
                + 添加API密钥
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'rgba(255,255,255,0.4)' }}>加载中...</div>
            ) : apiKeys.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'rgba(255,255,255,0.4)' }}>
                暂无配置的API密钥，请点击上方按钮添加
              </div>
            ) : (
              <div style={{ display: 'grid', gap: '1rem' }}>
                {apiKeys.map((key) => (
                  <div 
                    key={key.id}
                    style={{ 
                      padding: '1rem', 
                      borderRadius: '0.5rem', 
                      backgroundColor: key.is_active ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      opacity: key.is_active ? 1 : 0.5,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <span style={{ fontSize: '1.5rem' }}>
                          {providerLogos[key.provider_id] || '🔑'}
                        </span>
                        <div>
                          <div style={{ color: 'white', fontWeight: 500 }}>
                            {key.name}
                            {key.is_default && <Badge style={{ marginLeft: '0.5rem', backgroundColor: '#7c3aed' }}>默认</Badge>}
                          </div>
                          <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.875rem' }}>
                            {Object.values(key.masked_credentials).join(' | ')}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleToggle(key.id, !key.is_active)}
                        >
                          {key.is_active ? '禁用' : '启用'}
                        </Button>
                        {!key.is_default && (
                          <Button 
                            variant="outline" 
                            size="sm"
                            onClick={() => handleSetDefault(key.id)}
                          >
                            设为默认
                          </Button>
                        )}
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleDelete(key.id)}
                          style={{ color: '#ef4444' }}
                        >
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

        {/* 可用提供商 */}
        <div>
          <h2 style={{ color: 'white', fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>
            可用AI服务提供商
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(250px,1fr))', gap: '1rem' }}>
            {providers.map((provider) => (
              <Card 
                key={provider.id}
                style={{ 
                  backgroundColor: 'rgba(255,255,255,0.05)', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  cursor: 'pointer',
                }}
                onClick={() => {
                  setSelectedProvider(provider);
                  setAddDialogOpen(true);
                }}
              >
                <CardContent style={{ padding: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '1.5rem' }}>{providerLogos[provider.id] || '🔑'}</span>
                    <div>
                      <div style={{ color: 'white', fontWeight: 500 }}>{provider.name}</div>
                      <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem' }}>
                        {typeNames[provider.type] || provider.type}
                      </div>
                    </div>
                  </div>
                  <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.875rem' }}>
                    {provider.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* 添加对话框 */}
        <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
          <DialogContent style={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', maxWidth: '500px' }}>
            <DialogHeader>
              <DialogTitle style={{ color: 'white' }}>
                添加API密钥 - {selectedProvider?.name}
              </DialogTitle>
            </DialogHeader>
            <div style={{ display: 'grid', gap: '1rem', marginTop: '1rem' }}>
              <div>
                <label style={{ display: 'block', color: 'rgba(255,255,255,0.8)', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                  密钥名称（可选）
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  placeholder={selectedProvider?.name || 'API密钥名称'}
                  style={{ backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}
                />
              </div>
              
              <div>
                <label style={{ display: 'block', color: 'rgba(255,255,255,0.8)', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                  API Key <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <Input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) => setFormData({...formData, api_key: e.target.value})}
                  placeholder="请输入API Key"
                  style={{ backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}
                />
              </div>

              {selectedProvider?.required_params.includes('secret_key') && (
                <div>
                  <label style={{ display: 'block', color: 'rgba(255,255,255,0.8)', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                    Secret Key
                  </label>
                  <Input
                    type="password"
                    value={formData.secret_key}
                    onChange={(e) => setFormData({...formData, secret_key: e.target.value})}
                    placeholder="请输入Secret Key"
                    style={{ backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}
                  />
                </div>
              )}

              {selectedProvider?.required_params.includes('server_id') && (
                <>
                  <div>
                    <label style={{ display: 'block', color: 'rgba(255,255,255,0.8)', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                      Server ID
                    </label>
                    <Input
                      value={formData.server_id}
                      onChange={(e) => setFormData({...formData, server_id: e.target.value})}
                      placeholder="Discord Server ID"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', color: 'rgba(255,255,255,0.8)', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                      Channel ID
                    </label>
                    <Input
                      value={formData.channel_id}
                      onChange={(e) => setFormData({...formData, channel_id: e.target.value})}
                      placeholder="Discord Channel ID"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}
                    />
                  </div>
                </>
              )}

              <Button 
                onClick={handleSubmit}
                disabled={!formData.api_key}
                style={{ backgroundColor: '#7c3aed', marginTop: '1rem' }}
              >
                保存配置
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}