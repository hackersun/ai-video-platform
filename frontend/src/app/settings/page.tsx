'use client';

import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Settings, 
  User, 
  Bell, 
  Shield, 
  Palette, 
  ChevronRight 
} from 'lucide-react';
import Link from 'next/link';

const settingsMenu = [
  { 
    label: '个人资料', 
    path: '/settings/profile', 
    icon: User,
    desc: '管理您的个人信息和头像'
  },
  { 
    label: '通知设置', 
    path: '/settings/notifications', 
    icon: Bell,
    desc: '配置消息通知偏好'
  },
  { 
    label: '安全设置', 
    path: '/settings/security', 
    icon: Shield,
    desc: '修改密码和安全选项'
  },
  { 
    label: '外观设置', 
    path: '/settings/appearance', 
    icon: Palette,
    desc: '自定义界面主题和颜色'
  },
];

export default function SettingsPage() {
  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-3xl font-bold text-white">系统设置</h1>
          <p className="text-white/60 mt-1">管理您的账户和偏好设置</p>
        </div>

        {/* 设置菜单 */}
        <div className="space-y-4">
          {settingsMenu.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.path} href={item.path}>
                <Card className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-violet-600/20 flex items-center justify-center">
                        <Icon className="w-5 h-5 text-violet-400" />
                      </div>
                      <div className="flex-1">
                        <h3 className="text-white font-medium">{item.label}</h3>
                        <p className="text-white/60 text-sm">{item.desc}</p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-white/40" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>

        {/* 快捷设置 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white">快捷设置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-white">自动保存</span>
              <Button variant="outline" size="sm" className="border-white/20 text-white">
                已开启
              </Button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-white">深色模式</span>
              <Button variant="outline" size="sm" className="border-white/20 text-white">
                已开启
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}