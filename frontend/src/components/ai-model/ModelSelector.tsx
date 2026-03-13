'use client';

import { useState, useEffect } from 'react';

export interface CategoryInfo {
  id: string;
  name: string;
  icon: string;
  description: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  logo?: string;
  models_count: number;
}

interface ModelSelectorProps {
  categories: CategoryInfo[];
  providers: ProviderInfo[];
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
}

export function ModelSelector({ categories, providers, selectedCategory, onCategoryChange }: ModelSelectorProps) {
  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ color: 'white', fontSize: '1rem', fontWeight: '600', marginBottom: '0.75rem' }}>
          模型分类
        </h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          <button
            onClick={() => onCategoryChange('')}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '0.5rem',
              border: 'none',
              background: selectedCategory === '' ? '#7c3aed' : 'rgba(255,255,255,0.08)',
              color: 'white',
              fontSize: '0.875rem',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            全部
          </button>
          {categories.map(cat => (
            <button
              key={cat.id}
              onClick={() => onCategoryChange(cat.id)}
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '0.5rem',
                border: 'none',
                background: selectedCategory === cat.id ? '#7c3aed' : 'rgba(255,255,255,0.08)',
                color: 'white',
                fontSize: '0.875rem',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {cat.name}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 style={{ color: 'white', fontSize: '1rem', fontWeight: '600', marginBottom: '0.75rem' }}>
          提供商
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: '0.5rem' }}>
          {providers.map(provider => (
            <div
              key={provider.id}
              style={{
                padding: '1rem',
                borderRadius: '0.75rem',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)',
                textAlign: 'center'
              }}
            >
              <div style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)',
                margin: '0 auto 0.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontWeight: 'bold'
              }}>
                {provider.name.charAt(0)}
              </div>
              <div style={{ color: 'white', fontSize: '0.875rem', fontWeight: '500' }}>{provider.name}</div>
              <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.75rem' }}>{provider.models_count} 模型</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}