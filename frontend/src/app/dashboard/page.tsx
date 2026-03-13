'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState({ username: 'user' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setTimeout(() => setLoading(false), 500);
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 48, height: 48, borderRadius: '50%', border: '3px solid #8b5cf6', borderTopColor: 'transparent', animation: 'spin 1s linear infinite' }}></div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <header style={{ position: 'sticky', top: 0, zIndex: 50, borderBottom: '1px solid rgba(255,255,255,0.05)', backgroundColor: 'rgba(15,23,42,0.8)', backdropFilter: 'blur(8px)' }}>
        <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '0 1rem', height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link href="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ width: 40, height: 40, borderRadius: 12, background: 'linear-gradient(to bottom right, #7c3aed, #4f46e5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ color: 'white', fontSize: 20 }}>✨</span>
            </div>
            <span style={{ fontSize: '1.25rem', fontWeight: 'bold', color: 'white' }}>AI视频平台</span>
          </Link>
          <nav style={{ display: 'flex', gap: '1rem' }}>
            <Link href="/dashboard" style={{ color: 'white' }}>控制台</Link>
            <Link href="/novels" style={{ color: 'rgba(255,255,255,0.6)' }}>作品</Link>
            <Link href="/tts" style={{ color: 'rgba(255,255,255,0.6)' }}>语音合成</Link>
            <Link href="/templates/market" style={{ color: 'rgba(255,255,255,0.6)' }}>模板</Link>
            <Link href="/analytics" style={{ color: 'rgba(255,255,255,0.6)' }}>分析</Link>
            <Link href="/teams" style={{ color: 'rgba(255,255,255,0.6)' }}>团队</Link>
          </nav>
        </div>
      </header>

      <main style={{ maxWidth: '80rem', margin: '0 auto', padding: '2rem 1rem' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white', marginBottom: '0.5rem' }}>
          欢迎回来，{user.username}
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.6)', marginBottom: '2rem' }}>管理您的创作项目</p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: '1rem', marginBottom: '2rem' }}>
          <Link href="/novels/new" style={{ padding: '1.5rem', borderRadius: '1rem', background: 'linear-gradient(to bottom right, #7c3aed, #4f46e5)', color: 'white' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>+</div>
            <div style={{ fontWeight: 500 }}>创建小说</div>
          </Link>
          <Link href="/tts" style={{ padding: '1.5rem', borderRadius: '1rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🎤</div>
            <div style={{ fontWeight: 500 }}>语音合成</div>
          </Link>
          <Link href="/templates/market" style={{ padding: '1.5rem', borderRadius: '1rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📋</div>
            <div style={{ fontWeight: 500 }}>模板市场</div>
          </Link>
          <Link href="/analytics" style={{ padding: '1.5rem', borderRadius: '1rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📊</div>
            <div style={{ fontWeight: 500 }}>数据分析</div>
          </Link>
        </div>
      </main>
    </div>
  );
}