"use client";

import { MainLayout } from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  User, 
  Key, 
  Cpu, 
  Globe,
  Bell,
  Shield,
  ChevronRight
} from "lucide-react";
import Link from "next/link";

const settingsMenu = [
  {
    title: "个人资料",
    description: "管理您的个人信息和头像",
    icon: User,
    href: "/settings/profile",
    color: "text-blue-400",
    bgColor: "bg-blue-500/20",
  },
  {
    title: "API密钥",
    description: "管理外部API访问密钥",
    icon: Key,
    href: "/settings/api-keys",
    color: "text-violet-400",
    bgColor: "bg-violet-500/20",
  },
  {
    title: "AI模型配置",
    description: "配置和管理AI模型",
    icon: Cpu,
    href: "/settings/models",
    color: "text-green-400",
    bgColor: "bg-green-500/20",
  },
  {
    title: "外部API",
    description: "配置第三方API接入",
    icon: Globe,
    href: "/settings/external",
    color: "text-orange-400",
    bgColor: "bg-orange-500/20",
  },
  {
    title: "通知设置",
    description: "管理通知偏好",
    icon: Bell,
    href: "/settings/notifications",
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/20",
  },
  {
    title: "安全设置",
    description: "修改密码和安全选项",
    icon: Shield,
    href: "/settings/security",
    color: "text-red-400",
    bgColor: "bg-red-500/20",
  },
];

export default function SettingsPage() {
  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-bold text-white">设置</h1>
          <p className="text-white/60 mt-1">管理您的账户和平台配置</p>
        </div>

        {/* 设置菜单 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {settingsMenu.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href}>
                <Card className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors cursor-pointer group">
                  <CardContent className="p-6">
                    <div className="flex items-start gap-4">
                      <div className={`p-3 rounded-lg ${item.bgColor}`}>
                        <Icon className={`w-6 h-6 ${item.color}`} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="text-lg font-medium text-white group-hover:text-violet-400 transition-colors">
                            {item.title}
                          </h3>
                          <ChevronRight className="w-5 h-5 text-white/40 group-hover:text-white/60" />
                        </div>
                        <p className="text-white/60 text-sm mt-1">
                          {item.description}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>

        {/* 平台信息 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white">平台信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between py-2 border-b border-white/10">
              <span className="text-white/60">版本</span>
              <span className="text-white">v1.0.0</span>
            </div>
            <div className="flex justify-between py-2 border-b border-white/10">
              <span className="text-white/60">构建时间</span>
              <span className="text-white">2026-03-14</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-white/60">技术支持</span>
              <span className="text-white">support@aivideo.com</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
