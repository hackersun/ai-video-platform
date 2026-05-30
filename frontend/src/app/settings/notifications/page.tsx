'use client';

import { useEffect, useState, type ElementType } from 'react';
import Link from 'next/link';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/toast';
import {
  Bell,
  BellRing,
  CheckCircle,
  ChevronLeft,
  Clock3,
  Mail,
  RotateCcw,
  Send,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import {
  defaultNotificationPreferences,
  getNotificationPreferences,
  NotificationPreferences,
  saveNotificationPreferences,
} from '@/lib/user-preferences';

type PermissionState = 'unsupported' | NotificationPermission;

export default function NotificationSettingsPage() {
  const { toast } = useToast();
  const [preferences, setPreferences] = useState<NotificationPreferences>(defaultNotificationPreferences);
  const [permission, setPermission] = useState<PermissionState>('unsupported');

  useEffect(() => {
    setPreferences(getNotificationPreferences());
    setPermission(getNotificationPermission());
  }, []);

  const updatePreferences = (next: NotificationPreferences) => {
    setPreferences(next);
    saveNotificationPreferences(next);
  };

  const togglePreference = async (key: keyof NotificationPreferences) => {
    if (key === 'browserNotifications' && !preferences.browserNotifications) {
      const nextPermission = await requestBrowserPermission();
      setPermission(nextPermission);
      if (nextPermission !== 'granted') {
        toast({
          title: nextPermission === 'unsupported' ? '当前浏览器不支持系统通知' : '浏览器通知未授权',
          description: '可以继续使用站内提示，不影响生成任务。',
          type: 'info',
        });
        return;
      }
    }

    updatePreferences({ ...preferences, [key]: !preferences[key] });
  };

  const handleTestNotification = async () => {
    let nextPermission = permission;
    if (nextPermission === 'default') {
      nextPermission = await requestBrowserPermission();
      setPermission(nextPermission);
    }

    if (!preferences.browserNotifications || nextPermission !== 'granted') {
      toast({
        title: '站内测试提醒',
        description: '浏览器通知未开启，当前使用站内 Toast 提示。',
        type: 'info',
      });
      return;
    }

    new Notification('AI 视频平台测试通知', {
      body: '生成完成、失败任务和摘要提醒会按这里的偏好展示。',
    });
    toast({ title: '测试通知已发送', type: 'success' });
  };

  const resetPreferences = () => {
    updatePreferences(defaultNotificationPreferences);
    toast({ title: '通知设置已恢复默认', type: 'success' });
  };

  const enabledCount = Object.values(preferences).filter(Boolean).length;

  return (
    <MainLayout>
      <div className="max-w-4xl space-y-6">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon" className="text-white/60 hover:text-white">
            <Link href="/settings">
              <ChevronLeft className="h-5 w-5" />
              <span className="sr-only">返回设置</span>
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-white">通知设置</h1>
            <p className="mt-1 text-white/60">控制生成任务、系统摘要和浏览器通知的提醒方式。</p>
          </div>
        </div>

        <Card className="border-cyan-400/20 bg-gradient-to-br from-cyan-400/10 to-violet-500/5">
          <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <BellRing className="h-5 w-5 text-cyan-200" />
                <p className="font-medium text-white">当前已开启 {enabledCount}/5 项提醒</p>
              </div>
              <p className="mt-1 text-sm text-white/55">通知偏好保存在当前浏览器，不会改动后端任务流程。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="border-white/20 text-white/65">
                浏览器权限：{permissionLabel(permission)}
              </Badge>
              <Button onClick={handleTestNotification} className="bg-cyan-600 hover:bg-cyan-700">
                <Send className="mr-2 h-4 w-4" />
                测试通知
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <PreferenceCard
            title="生成完成提醒"
            description="视频、图片、语音或合成任务成功后展示提醒。"
            enabled={preferences.generationComplete}
            icon={CheckCircle}
            onToggle={() => togglePreference('generationComplete')}
          />
          <PreferenceCard
            title="失败任务提醒"
            description="任务失败或取消时保留醒目提示，便于快速排查。"
            enabled={preferences.failedTasks}
            icon={ShieldAlert}
            onToggle={() => togglePreference('failedTasks')}
          />
          <PreferenceCard
            title="周报摘要"
            description="预留每周创作数据摘要入口，目前保存偏好供后续通知服务使用。"
            enabled={preferences.weeklySummary}
            icon={Mail}
            onToggle={() => togglePreference('weeklySummary')}
          />
          <PreferenceCard
            title="浏览器系统通知"
            description="允许浏览器在页面后台时弹出任务结果提醒。"
            enabled={preferences.browserNotifications}
            icon={Bell}
            onToggle={() => togglePreference('browserNotifications')}
          />
          <PreferenceCard
            title="免打扰时段"
            description="预留夜间静默策略，当前仅保存本机偏好。"
            enabled={preferences.quietHours}
            icon={Clock3}
            onToggle={() => togglePreference('quietHours')}
          />
        </div>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Sparkles className="h-5 w-5 text-amber-300" />
              使用说明
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-white/60">
            <p>站内 Toast 提示始终可用；浏览器系统通知需要用户授权，未授权不会影响生成任务提交和结果查询。</p>
            <p>周报摘要和免打扰时段先保存为本机偏好，后续接入真实通知服务时可直接复用该配置。</p>
            <Button onClick={resetPreferences} variant="outline" className="border-white/20 text-white">
              <RotateCcw className="mr-2 h-4 w-4" />
              恢复默认通知设置
            </Button>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}

function PreferenceCard({
  title,
  description,
  enabled,
  icon: Icon,
  onToggle,
}: {
  title: string;
  description: string;
  enabled: boolean;
  icon: ElementType;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`rounded-2xl border p-5 text-left transition-colors ${
        enabled
          ? 'border-cyan-300/30 bg-cyan-400/10'
          : 'border-white/10 bg-white/5 hover:bg-white/10'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-2xl border border-white/10 bg-white/10 p-3">
            <Icon className="h-5 w-5 text-cyan-200" />
          </div>
          <div>
            <p className="font-medium text-white">{title}</p>
            <p className="mt-1 text-sm leading-5 text-white/50">{description}</p>
          </div>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${enabled ? 'bg-cyan-300/20 text-cyan-100' : 'bg-white/10 text-white/45'}`}>
          {enabled ? '已开启' : '已关闭'}
        </span>
      </div>
    </button>
  );
}

function getNotificationPermission(): PermissionState {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported';
  return Notification.permission;
}

async function requestBrowserPermission(): Promise<PermissionState> {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported';
  return Notification.requestPermission();
}

function permissionLabel(value: PermissionState) {
  const labels = {
    granted: '已允许',
    denied: '已拒绝',
    default: '未询问',
    unsupported: '不支持',
  };
  return labels[value];
}
