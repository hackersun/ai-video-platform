'use client';

import { useState } from 'react';
import { ProviderInfo } from './ModelSelector';

interface ProviderCardProps {
  provider: ProviderInfo;
  models: any[];
  selectedCategory: string;
  onModelSelect: (modelId: string) => void;
  onTestConnection: (modelId: string) => void;
}

export function ProviderCard({ provider, models, selectedCategory, onModelSelect, onTestConnection }: ProviderCardProps) {
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);

  const providerModels = models.filter(m => m.provider === provider.id);

  const handleConnect = (modelId: string) => {
    setSelectedModelId(modelId);
    setShowKeyModal(true);
  };

  const handleSaveKey = async () => {
    if (!selectedModelId || !apiKey) return;
    try {
      const { aiModelApi } = await import('@/lib/api');
      await aiModelApi.updateApiKey(selectedModelId, apiKey);
      setShowKeyModal(false);
      setApiKey('');
    } catch (error) {
      console.error('Failed to save API key:', error);
    }
  };

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      borderRadius: '1rem',
      border: '1px solid rgba(255,255,255,0.08)',
      padding: '1.5rem',
      marginBottom: '1rem'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
        <div style={{
          width: 48,
          height: 48,
          borderRadius: '12px',
          background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '1.5rem',
          fontWeight: 'bold'
        }}>
          {provider.name.charAt(0)}
        </div>
        <div>
          <h3 style={{ color: 'white', fontSize: '1.25rem', fontWeight: '600' }}>{provider.name}</h3>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.875rem' }}>
            {provider.models_count} 个模型
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {providerModels.map(model => (
          <div
            key={model.id}
            style={{
              padding: '1rem',
              borderRadius: '0.75rem',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div style={{ color: 'white', fontWeight: '500' }}>{model.display_name || model.name}</div>
              <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.75rem' }}>
                {model.category} · {model.model_id}
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={() => onTestConnection(model.id)}
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '0.5rem',
                  border: '1px solid rgba(255,255,255,0.2)',
                  background: 'transparent',
                  color: 'rgba(255,255,255,0.8)',
                  fontSize: '0.875rem',
                  cursor: 'pointer'
                }}
              >
                测试
              </button>
              <button
                onClick={() => handleConnect(model.id)}
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '0.5rem',
                  border: 'none',
                  background: '#7c3aed',
                  color: 'white',
                  fontSize: '0.875rem',
                  cursor: 'pointer'
                }}
              >
                配置
              </button>
            </div>
          </div>
        ))}
      </div>

      {showKeyModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100
        }}>
          <div style={{
            background: '#1e293b',
            borderRadius: '1rem',
            padding: '2rem',
            maxWidth: '400px',
            width: '90%'
          }}>
            <h3 style={{ color: 'white', fontSize: '1.25rem', fontWeight: '600', marginBottom: '1rem' }}>
              配置 API Key
            </h3>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="输入 API Key"
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: '0.5rem',
                border: '1px solid rgba(255,255,255,0.2)',
                background: 'rgba(255,255,255,0.05)',
                color: 'white',
                marginBottom: '1rem'
              }}
            />
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowKeyModal(false)}
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '0.5rem',
                  border: '1px solid rgba(255,255,255,0.2)',
                  background: 'transparent',
                  color: 'rgba(255,255,255,0.8)',
                  cursor: 'pointer'
                }}
              >
                取消
              </button>
              <button
                onClick={handleSaveKey}
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '0.5rem',
                  border: 'none',
                  background: '#7c3aed',
                  color: 'white',
                  cursor: 'pointer'
                }}
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}