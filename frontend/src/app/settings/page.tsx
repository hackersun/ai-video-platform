'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import apiClient from '@/lib/api-client';
import {
  applyAppearancePreferences,
  AppearancePreferences,
  defaultAppearancePreferences,
  defaultNotificationPreferences,
  getAppearancePreferences,
  getNotificationPreferences,
  NotificationPreferences,
  saveAppearancePreferences,
  saveNotificationPreferences,
} from '@/lib/user-preferences';
import {
  Bell,
  CheckCircle,
  ChevronRight,
  Loader2,
  Palette,
  Save,
  Settings,
  Shield,
  User,
  Zap
} from 'lucide-react';

const settingsMenu = [
  {
    label: '个人资料',
    path: '/settings/profile',
    icon: User,
    desc: '管理用户名、邮箱和头像',
    status: '后端同步',
  },
  {
    label: '通知设置',
    path: '/settings/notifications',
    icon: Bell,
    desc: '配置生成完成、失败提醒和浏览器通知',
    status: '本机保存',
  },
  {
    label: '安全设置',
    path: '/settings/security',
    icon: Shield,
    desc: '修改密码和账户安全策略',
    status: '后端同步',
  },
  {
    label: '外观设置',
    path: '/settings/appearance',
    icon: Palette,
    desc: '调整主题强调色、紧凑布局和动效',
    status: '本机保存',
  },
];

type CurrentUser = {
  username?: string;
  email?: string;
};

export default function SettingsPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [notifications, setNotifications] = useState<NotificationPreferences>(defaultNotificationPreferences);
  const [appearance, setAppearance] = useState<AppearancePreferences>(defaultAppearancePreferences);

  useEffect(() => {
    setNotifications(getNotificationPreferences());
    const savedAppearance = getAppearancePreferences();
    setAppearance(savedAppearance);
    applyAppearancePreferences(savedAppearance);

    apiClient.getCurrentUser()
      .then((data) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setLoadingUser(false));
  }, []);

  const toggleNotification = (key: keyof NotificationPreferences) => {
    const next = { ...notifications, [key]: !notifications[key] };
    setNotifications(next);
    saveNotificationPreferences(next);
  };

  const toggleAppearance = (key: keyof Pick<AppearancePreferences, 'compactMode' | 'reduceMotion'>) => {
    const next = { ...appearance, [key]: !appearance[key] };
    setAppearance(next);
    saveAppearancePreferences(next);
    applyAppearancePreferences(next);
  };

  const enabledNotificationCount = Object.values(notifications).filter(Boolean).length;

  return (
    <MainLayout>
      <div className="space-y-6">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-white/70">
            <Settings className="h-4 w-4" />
            系统偏好
          </div>
          <h1 className="mt-3 text-3xl font-bold text-white">系统设置</h1>
          <p className="mt-1 text-white/60">管理账户、安全、通知和本机界面偏好。</p>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1.25fr]">
          <Card className="border-white/10 bg-gradient-to-br from-white/10 to-white/[0.03]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <User className="h-5 w-5 text-cyan-300" />
                当前账户
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {loadingUser ? (
                <div className="flex items-center gap-2 text-white/60">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在读取账户信息...
                </div>
              ) : (
                <div>
                  <p className="text-2xl font-semibold text-white">{user?.username || '未读取到用户'}</p>
                  <p className="mt-1 text-sm text-white/50">{user?.email || '请检查登录状态或后端服务'}</p>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="border-cyan-300/30 text-cyan-200">
                  通知 {enabledNotificationCount}/5 已开
                </Badge>
                <Badge variant="outline" className="border-white/20 text-white/65">
                  强调色 {accentLabel(appearance.accentColor)}
                </Badge>
                {appearance.compactMode && (
                  <Badge variant="outline" className="border-emerald-300/30 text-emerald-200">紧凑布局</Badge>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-white/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Zap className="h-5 w-5 text-amber-300" />
                快捷设置
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <QuickToggle
                label="生成完成提醒"
                description="视频、语音、图片生成成功后提醒"
                enabled={notifications.generationComplete}
                onClick={() => toggleNotification('generationComplete')}
              />
              <QuickToggle
                label="失败任务提醒"
                description="生成失败时保留可见提示"
                enabled={notifications.failedTasks}
                onClick={() => toggleNotification('failedTasks')}
              />
              <QuickToggle
                label="紧凑布局"
                description="减少页面间距，适合高密度操作"
                enabled={appearance.compactMode}
                onClick={() => toggleAppearance('compactMode')}
              />
              <QuickToggle
                label="减少动效"
                description="降低动画和过渡效果"
                enabled={appearance.reduceMotion}
                onClick={() => toggleAppearance('reduceMotion')}
              />
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {settingsMenu.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.path} href={item.path} className="group block">
                <Card className="h-full border-white/10 bg-white/5 transition-colors hover:bg-white/10">
                  <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/10">
                        <Icon className="h-5 w-5 text-cyan-200" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-white">{item.label}</h3>
                          <Badge variant="outline" className="border-white/15 text-white/45">
                            {item.status}
                          </Badge>
                        </div>
                        <p className="mt-1 text-sm text-white/55">{item.desc}</p>
                      </div>
                      <ChevronRight className="mt-2 h-5 w-5 text-white/35 transition-transform group-hover:translate-x-1 group-hover:text-white/70" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>

        <Card className="border-emerald-500/20 bg-emerald-500/10">
          <CardContent className="flex items-start gap-3 p-4">
            <CheckCircle className="mt-0.5 h-5 w-5 text-emerald-300" />
            <div>
              <p className="font-medium text-emerald-100">设置保存策略</p>
              <p className="mt-1 text-sm text-white/55">
                个人资料和密码会同步到后端；通知和外观属于本机操作偏好，保存到浏览器 localStorage，不影响生成链路。
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}

function QuickToggle({
  label,
  description,
  enabled,
  onClick,
}: {
  label: string;
  description: string;
  enabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border p-4 text-left transition-colors ${
        enabled
          ? 'border-cyan-300/30 bg-cyan-400/10'
          : 'border-white/10 bg-slate-950/30 hover:bg-white/5'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium text-white">{label}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${enabled ? 'bg-cyan-300/20 text-cyan-100' : 'bg-white/10 text-white/45'}`}>
          {enabled ? '已开启' : '已关闭'}
        </span>
      </div>
      <p className="mt-2 text-sm text-white/45">{description}</p>
      <div className="mt-3 flex items-center gap-1 text-xs text-white/35">
        <Save className="h-3.5 w-3.5" />
        点击即保存
      </div>
    </button>
  );
}

function accentLabel(value: AppearancePreferences['accentColor']) {
  const labels = {
    violet: '紫',
    cyan: '青',
    emerald: '绿',
    amber: '橙',
  };
  return labels[value];
}
