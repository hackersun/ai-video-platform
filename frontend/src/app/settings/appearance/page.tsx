'use client';

import { useEffect, useState, type ElementType } from 'react';
import Link from 'next/link';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/toast';
import {
  applyAppearancePreferences,
  AppearancePreferences,
  defaultAppearancePreferences,
  getAppearancePreferences,
  saveAppearancePreferences,
} from '@/lib/user-preferences';
import {
  Check,
  ChevronLeft,
  Eye,
  LayoutDashboard,
  Monitor,
  Moon,
  Paintbrush,
  RotateCcw,
  Rows3,
  Sparkles,
  Sun,
  Wand2,
} from 'lucide-react';

const accentOptions: Array<{
  value: AppearancePreferences['accentColor'];
  label: string;
  description: string;
  gradient: string;
}> = [
  { value: 'violet', label: '星云紫', description: '默认创作风格，适合 AI 生成工具。', gradient: 'from-violet-500 to-indigo-500' },
  { value: 'cyan', label: '赛博青', description: '更突出数据和任务状态。', gradient: 'from-cyan-400 to-blue-500' },
  { value: 'emerald', label: '森林绿', description: '更温和，适合长时间编辑。', gradient: 'from-emerald-400 to-teal-500' },
  { value: 'amber', label: '胶片橙', description: '更接近影视制作氛围。', gradient: 'from-amber-400 to-orange-500' },
];

const themeOptions: Array<{
  value: AppearancePreferences['theme'];
  label: string;
  description: string;
  icon: ElementType;
}> = [
  { value: 'dark', label: '深色模式', description: '适合暗光环境和长时间视频制作。', icon: Moon },
  { value: 'light', label: '浅色模式', description: '明亮清晰，适合白天和办公环境。', icon: Sun },
  { value: 'system', label: '跟随系统', description: '自动跟随设备当前的深浅色设置。', icon: Monitor },
];

export default function AppearanceSettingsPage() {
  const { toast } = useToast();
  const [preferences, setPreferences] = useState<AppearancePreferences>(defaultAppearancePreferences);

  useEffect(() => {
    const saved = getAppearancePreferences();
    setPreferences(saved);
    applyAppearancePreferences(saved);
  }, []);

  const updatePreferences = (next: AppearancePreferences, message = '外观设置已保存') => {
    setPreferences(next);
    saveAppearancePreferences(next);
    applyAppearancePreferences(next);
    toast({ title: message, type: 'success' });
  };

  const togglePreference = (key: keyof Pick<AppearancePreferences, 'compactMode' | 'reduceMotion' | 'denseCards'>) => {
    updatePreferences({ ...preferences, [key]: !preferences[key] });
  };

  const resetPreferences = () => {
    updatePreferences(defaultAppearancePreferences, '外观设置已恢复默认');
  };

  return (
    <MainLayout>
      <div className="max-w-5xl space-y-6">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon" className="text-white/60 hover:text-white">
            <Link href="/settings">
              <ChevronLeft className="h-5 w-5" />
              <span className="sr-only">返回设置</span>
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-white">外观设置</h1>
            <p className="mt-1 text-white/60">选择主题、界面密度、动效和强调色；设置会按当前账户保存。</p>
          </div>
        </div>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Sun className="h-5 w-5 text-amber-300" />
              界面主题
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {themeOptions.map((option) => {
              const selected = preferences.theme === option.value;
              const Icon = option.icon;
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-label={option.label}
                  onClick={() => updatePreferences(
                    { ...preferences, theme: option.value },
                    `已切换为${option.label}`,
                  )}
                  className={`rounded-2xl border p-4 text-left transition-all ${
                    selected
                      ? 'border-violet-400/60 bg-violet-500/15 shadow-lg shadow-violet-950/10'
                      : 'border-white/10 bg-white/5 hover:border-white/25 hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <span className={`rounded-xl p-2.5 ${selected ? 'bg-violet-500 text-white' : 'bg-white/10 text-white/70'}`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    {selected && <Check className="h-5 w-5 text-violet-300" />}
                  </div>
                  <p className="mt-4 font-medium text-white">{option.label}</p>
                  <p className="mt-1 text-sm leading-5 text-white/50">{option.description}</p>
                </button>
              );
            })}
          </CardContent>
        </Card>

        <Card className="overflow-hidden border-white/10 bg-white/5">
          <CardContent className="grid grid-cols-1 gap-0 p-0 lg:grid-cols-[1fr_1.1fr]">
            <div className="space-y-4 p-6">
              <Badge variant="outline" className="border-cyan-300/30 text-cyan-200">
                当前主题：{themeLabel(preferences.theme)}
              </Badge>
              <h2 className="text-2xl font-semibold text-white">适配创作环境的双主题工作台</h2>
              <p className="text-sm leading-6 text-white/55">
                浅色模式使用柔和灰白背景、清晰深色文字和保留品牌强调色；深色模式继续沿用当前专业影视工作台视觉。
              </p>
              <Button onClick={resetPreferences} variant="outline" className="border-white/20 text-white">
                <RotateCcw className="mr-2 h-4 w-4" />
                恢复默认外观
              </Button>
            </div>
            <div className="bg-slate-950/60 p-6">
              <div className={`rounded-3xl border border-white/10 bg-gradient-to-br ${previewGradient(preferences.accentColor)} p-[1px]`}>
                <div className="rounded-3xl bg-slate-950/90 p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-white/45">预览</p>
                      <p className="mt-1 text-lg font-semibold text-white">镜头生成控制台</p>
                    </div>
                    <div className={`h-10 w-10 rounded-2xl bg-gradient-to-br ${previewGradient(preferences.accentColor)}`} />
                  </div>
                  <div className="mt-5 grid grid-cols-3 gap-3">
                    {[72, 48, 88].map((height, index) => (
                      <div key={height} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                        <div className={`h-2 rounded-full bg-gradient-to-r ${previewGradient(preferences.accentColor)}`} style={{ width: `${height}%` }} />
                        <div className="mt-3 h-2 rounded-full bg-white/10" />
                        <div className="mt-2 h-2 w-2/3 rounded-full bg-white/10" />
                        <p className="mt-4 text-xs text-white/40">模块 {index + 1}</p>
                      </div>
                    ))}
                  </div>
                  <div className={`mt-5 rounded-2xl border border-white/10 bg-white/5 ${preferences.compactMode ? 'p-3' : 'p-5'}`}>
                    <div className="flex items-center gap-3">
                      <Sparkles className="h-5 w-5 text-white/70" />
                      <div>
                        <p className="text-sm font-medium text-white">布局密度预览</p>
                        <p className="text-xs text-white/45">{preferences.compactMode ? '紧凑间距已开启' : '标准间距'}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Paintbrush className="h-5 w-5 text-cyan-300" />
              强调色
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {accentOptions.map((option) => {
              const selected = preferences.accentColor === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => updatePreferences({ ...preferences, accentColor: option.value })}
                  className={`rounded-2xl border p-4 text-left transition-colors ${
                    selected ? 'border-white/30 bg-white/10' : 'border-white/10 bg-slate-950/30 hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className={`h-10 w-10 rounded-2xl bg-gradient-to-br ${option.gradient}`} />
                      <div>
                        <p className="font-medium text-white">{option.label}</p>
                        <p className="mt-1 text-sm text-white/45">{option.description}</p>
                      </div>
                    </div>
                    {selected && (
                      <span className="rounded-full bg-white/15 p-1 text-white">
                        <Check className="h-4 w-4" />
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <OptionToggle
            title="紧凑布局"
            description="减少主要页面纵向间距，适合高频管理任务。"
            enabled={preferences.compactMode}
            icon={LayoutDashboard}
            onToggle={() => togglePreference('compactMode')}
          />
          <OptionToggle
            title="减少动效"
            description="降低动画和过渡，适合低性能设备或动效敏感用户。"
            enabled={preferences.reduceMotion}
            icon={Eye}
            onToggle={() => togglePreference('reduceMotion')}
          />
          <OptionToggle
            title="紧凑卡片圆角"
            description="收敛卡片圆角，提升后台工具感和信息密度。"
            enabled={preferences.denseCards}
            icon={Rows3}
            onToggle={() => togglePreference('denseCards')}
          />
        </div>

        <Card className="border-white/10 bg-white/5">
          <CardContent className="flex items-start gap-3 p-4 text-sm text-white/60">
            <Monitor className="mt-0.5 h-5 w-5 shrink-0 text-white/50" />
            <div>
              <p className="font-medium text-white">主题如何保存</p>
              <p className="mt-1">
                每个登录用户在当前浏览器中拥有独立的外观偏好；选择“跟随系统”后，设备主题变化会自动同步，无需刷新页面。
              </p>
            </div>
            <Wand2 className="ml-auto hidden h-5 w-5 text-cyan-300 md:block" />
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}

function OptionToggle({
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
        <div className="rounded-2xl border border-white/10 bg-white/10 p-3">
          <Icon className="h-5 w-5 text-cyan-200" />
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs ${enabled ? 'bg-cyan-300/20 text-cyan-100' : 'bg-white/10 text-white/45'}`}>
          {enabled ? '已开启' : '已关闭'}
        </span>
      </div>
      <p className="mt-4 font-medium text-white">{title}</p>
      <p className="mt-1 text-sm leading-5 text-white/50">{description}</p>
    </button>
  );
}

function previewGradient(value: AppearancePreferences['accentColor']) {
  const gradients = {
    violet: 'from-violet-500 to-indigo-500',
    cyan: 'from-cyan-400 to-blue-500',
    emerald: 'from-emerald-400 to-teal-500',
    amber: 'from-amber-400 to-orange-500',
  };
  return gradients[value];
}

function themeLabel(value: AppearancePreferences['theme']) {
  return {
    dark: '深色模式',
    light: '浅色模式',
    system: '跟随系统',
  }[value];
}
