'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import {
  User,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle,
  Mail,
  UserCircle,
  Image as ImageIcon
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface UserProfile {
  id: string;
  username: string;
  email: string;
  avatar?: string;
}

export default function ProfileSettingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    avatar: ''
  });

  // 加载用户信息
  const loadProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      // 尝试从用户信息接口获取
      const response = await fetchWithAuth(`${API_BASE}/auth/me`);
      if (response.ok) {
        const data = await response.json();
        setProfile(data);
        setFormData({
          username: data.username || '',
          email: data.email || '',
          avatar: data.avatar || ''
        });
      } else {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.message || `加载用户信息失败：HTTP ${response.status}`);
      }
    } catch (err) {
      console.error('加载用户信息失败:', err);
      const message = err instanceof Error ? err.message : '加载用户信息失败';
      setError(message);
      setProfile(null);
      setFormData({ username: '', email: '', avatar: '' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  // 保存修改
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const response = await fetchWithAuth(`${API_BASE}/auth/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      if (response.ok) {
        const data = await response.json();
        setProfile(data);
        setFormData({
          username: data.username || '',
          email: data.email || '',
          avatar: data.avatar || ''
        });
        localStorage.setItem('user', JSON.stringify(data));
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.message || '保存失败');
      }
    } catch (err: any) {
      setError(err.message || '保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
          <span className="ml-3 text-white/60">加载中…</span>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6 max-w-2xl">
        {/* 页面标题 */}
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon" className="text-white/60 hover:text-white">
            <Link href="/settings">
              <span className="sr-only">返回</span>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-white">个人资料</h1>
            <p className="text-white/60 mt-1">管理您的个人信息</p>
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <Card className="bg-red-500/10 border-red-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-300">{error}</span>
            </CardContent>
          </Card>
        )}

        {/* 成功提示 */}
        {success && (
          <Card className="bg-green-500/10 border-green-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span className="text-green-300">保存成功</span>
            </CardContent>
          </Card>
        )}

        {/* 头像 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white text-lg">头像</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-6">
              <div className="relative">
                {profile?.avatar ? (
                  <img
                    src={profile.avatar}
                    alt={profile.username}
                    width={96}
                    height={96}
                    loading="lazy"
                    className="w-24 h-24 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                    <UserCircle className="w-12 h-12 text-white" />
                  </div>
                )}
                <button
                  type="button"
                  disabled
                  aria-label="头像由下方图片 URL 设置"
                  title="头像由下方图片URL保存到资料中"
                  className="absolute bottom-0 right-0 w-8 h-8 rounded-full bg-violet-600 hover:bg-violet-700 flex items-center justify-center text-white"
                >
                  <ImageIcon className="w-4 h-4" />
                </button>
              </div>
              <div>
                <p className="text-white font-medium">{profile?.username}</p>
                <p className="text-white/60 text-sm mt-1">使用公开可访问的正方形图片 URL</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 基本信息 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white text-lg flex items-center gap-2">
              <User className="w-5 h-5" />
              基本信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-2">用户名</label>
              <Input
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder="输入用户名"
                className="bg-white/5 border-white/10 text-white max-w-md"
              />
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-2">邮箱</label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="输入邮箱"
                className="bg-white/5 border-white/10 text-white max-w-md"
              />
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-2">头像 URL</label>
              <Input
                type="url"
                value={formData.avatar}
                onChange={(e) => setFormData({ ...formData, avatar: e.target.value })}
                placeholder="https://example.com/avatar.png"
                className="bg-white/5 border-white/10 text-white max-w-md"
              />
              <p className="text-xs text-white/40 mt-2">保存后会同步到个人资料并写入数据库。</p>
            </div>
          </CardContent>
        </Card>

        {/* 保存按钮 */}
        <div className="flex items-center gap-3">
          <Button
            onClick={handleSave}
            disabled={saving || !profile}
            className="bg-violet-600 hover:bg-violet-700"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            保存修改
          </Button>
          <Button asChild variant="outline" className="border-white/20 text-white">
            <Link href="/settings">
              取消
            </Link>
          </Button>
        </div>
      </div>
    </MainLayout>
  );
}
