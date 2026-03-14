'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ModelSelector, CategoryInfo, ProviderInfo } from '@/components/ai-model/ModelSelector';
import { ProviderCard } from '@/components/ai-model/ProviderCard';

interface AIModel {
  id: string;
  name: string;
  display_name: string;
  description: string;
  provider: string;
  category: string;
  model_id: string;
  status: string;
  is_default: boolean;
  input_price: number;
  output_price: number;
  max_tokens: number;
  rate_limit_rpm: number;
  icon_url: string;
}

export default function AIModelsPage() {
  const [models, setModels] = useState<AIModel[]>([]);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [loading, setLoading] = useState(true);
  const [testResult, setTestResult] = useState<{ show: boolean; success: boolean; message: string }>({ show: false, success: false, message: '' });

  useEffect(() => {
    loadData();
  }, [selectedCategory]);

  const loadData = async () => {
    try {
      const { aiModelApi } = await import('@/lib/api');
      const [modelsRes, categoriesRes] = await Promise.all([
        aiModelApi.getList({ category: selectedCategory || undefined, page_size: 100 }),
        aiModelApi.getCategories()
      ]);
      setModels(modelsRes.data.items || []);
      setCategories(categoriesRes.data.categories || []);
      setProviders(categoriesRes.data.providers || []);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async (modelId: string) => {
    try {
      const { aiModelApi } = await import('@/lib/api');
      const response = await aiModelApi.testConnection(modelId);
      setTestResult({
        show: true,
        success: response.data.success,
        message: response.data.message || (response.data.success ? '连接成功' : '连接失败')
      });
      setTimeout(() => setTestResult({ show: false, success: false, message: '' }), 3000);
    } catch (error) {
      setTestResult({ show: true, success: false, message: '测试失败' });
      setTimeout(() => setTestResult({ show: false, success: false, message: '' }), 3000);
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 48, height: 48, borderRadius: '50%', border: '3px solid #8b5cf6', borderTopColor: 'transparent', animation: 'spin 1s linear infinite' }}></div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
      
      <header style={{ position: 'sticky', top: 0, zIndex: 50, borderBottom: '1px solid rgba(255,255,255,0.05)', backgroundColor: 'rgba(15,23,42,0.8)', backdropFilter: 'blur(8px)' }}>
        <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '0 1rem', height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link href="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ width: 40, height: 40, borderRadius: 12, background: 'linear-gradient(to bottom right, #7c3aed, #4f46e5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ color: 'white', fontSize: 20 }}>✨</span>
            </div>
            <span style={{ fontSize: '1.25rem', fontWeight: 'bold', color: 'white' }}>AI视频平台</span>
          </Link>
          <nav style={{ display: 'flex', gap: '1rem' }}>
            <Link href="/dashboard" style={{ color: 'rgba(255,255,255,0.6)' }}>控制台</Link>
            <Link href="/novels" style={{ color: 'rgba(255,255,255,0.6)' }}>作品</Link>
            <Link href="/ai-models" style={{ color: 'white' }}>AI模型</Link>
            <Link href="/tts" style={{ color: 'rgba(255,255,255,0.6)' }}>语音合成</Link>
            <Link href="/templates/market" style={{ color: 'rgba(255,255,255,0.6)' }}>模板</Link>
          </nav>
        </div>
      </header>

      <main style={{ maxWidth: '80rem', margin: '0 auto', padding: '2rem 1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
          <div>
            <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white', marginBottom: '0.5rem' }}>
              AI模型配置
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.6)' }}>管理您的AI模型提供商和API配置</p>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '2rem' }}>
          <div style={{ position: 'sticky', top: '6rem', height: 'fit-content' }}>
            <ModelSelector
              categories={categories}
              providers={providers}
              selectedCategory={selectedCategory}
              onCategoryChange={setSelectedCategory}
            />
          </div>

          <div>
            <h2 style={{ color: 'white', fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>
              {selectedCategory ? categories.find(c => c.id === selectedCategory)?.name : '所有模型'}
            </h2>
            
            {providers.map(provider => {
              const providerModels = models.filter(m => m.provider === provider.id);
              if (providerModels.length === 0) return null;
              return (
                <ProviderCard
                  key={provider.id}
                  provider={provider}
                  models={providerModels}
                  selectedCategory={selectedCategory}
                  onModelSelect={() => {}}
                  onTestConnection={handleTestConnection}
                />
              );
            })}
          </div>
        </div>

        {testResult.show && (
          <div style={{
            position: 'fixed',
            bottom: '2rem',
            right: '2rem',
            padding: '1rem 1.5rem',
            borderRadius: '0.75rem',
            background: testResult.success ? '#10b981' : '#ef4444',
            color: 'white',
            fontWeight: '500',
            boxShadow: '0 10px 15px -3px rgba(0,0,0,0.3)',
            zIndex: 100
          }}>
            {testResult.message}
          </div>
        )}
      </main>
    </div>
  );
}