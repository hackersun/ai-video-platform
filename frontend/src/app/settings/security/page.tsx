'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import {
  Shield,
  Lock,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle,
  Eye,
  EyeOff
} from 'lucide-react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function SecuritySettingsPage() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChangePassword = async () => {
    setError(null);
    setSuccess(false);

    // 验证
    if (!currentPassword) {
      setError('请输入当前密码');
      return;
    }
    if (!newPassword) {
      setError('请输入新密码');
      return;
    }
    if (newPassword.length < 6) {
      setError('新密码长度至少为6位');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    if (currentPassword === newPassword) {
      setError('新密码不能与当前密码相同');
      return;
    }

    setSaving(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      });

      if (response.ok) {
        setSuccess(true);
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
        setTimeout(() => setSuccess(false), 5000);
      } else {
        const errData = await response.json();
        throw new Error(errData.detail || '修改密码失败');
      }
    } catch (err: any) {
      setError(err.message || '修改密码失败，请重试');
    } finally {
      setSaving(false);
    }
  };

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
            <h1 className="text-2xl font-bold text-white">安全设置</h1>
            <p className="text-white/60 mt-1">管理您的账户安全</p>
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
              <span className="text-green-300">密码修改成功</span>
            </CardContent>
          </Card>
        )}

        {/* 修改密码 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white text-lg flex items-center gap-2">
              <Lock className="w-5 h-5" />
              修改密码
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-2">当前密码</label>
              <div className="relative max-w-md">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="输入当前密码"
                  className="bg-white/5 border-white/10 text-white pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? '隐藏当前密码' : '显示当前密码'}
                  title={showPassword ? '隐藏密码' : '显示密码'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/60 mb-2">新密码</label>
              <div className="relative max-w-md">
                <Input
                  type={showNewPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="输入新密码（至少6位）"
                  className="bg-white/5 border-white/10 text-white pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  aria-label={showNewPassword ? '隐藏新密码' : '显示新密码'}
                  title={showNewPassword ? '隐藏密码' : '显示密码'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
                >
                  {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/60 mb-2">确认新密码</label>
              <div className="relative max-w-md">
                <Input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="再次输入新密码"
                  className="bg-white/5 border-white/10 text-white pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  aria-label={showConfirmPassword ? '隐藏确认新密码' : '显示确认新密码'}
                  title={showConfirmPassword ? '隐藏密码' : '显示密码'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
                >
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="pt-2">
              <Button
                onClick={handleChangePassword}
                disabled={saving}
                className="bg-violet-600 hover:bg-violet-700"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Lock className="w-4 h-4 mr-2" />
                )}
                修改密码
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 安全提示 */}
        <Card className="bg-blue-500/10 border-blue-500/30">
          <CardContent className="p-4">
            <h4 className="font-medium text-blue-300 mb-2 flex items-center gap-2">
              <Shield className="w-4 h-4" />
              安全建议
            </h4>
            <ul className="text-sm text-white/60 space-y-1">
              <li>使用至少8位包含字母、数字和特殊字符的密码</li>
              <li>不要在多个网站使用相同的密码</li>
              <li>定期更换密码，建议每3个月更换一次</li>
              <li>不要在公共电脑上保存密码</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
