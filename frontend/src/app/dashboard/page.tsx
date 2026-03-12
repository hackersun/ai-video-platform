"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { 
  LayoutDashboard, 
  BookOpen, 
  FileText, 
  Users, 
  Video, 
  Settings,
  LogOut,
  Plus,
  TrendingUp,
  Clock,
  CheckCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

const menuItems = [
  { icon: LayoutDashboard, label: "概览", href: "/dashboard", active: true },
  { icon: BookOpen, label: "小说管理", href: "/novels" },
  { icon: FileText, label: "剧本编辑", href: "/scripts" },
  { icon: Users, label: "角色管理", href: "/characters" },
  { icon: Video, label: "视频生成", href: "/videos" },
  { icon: Settings, label: "设置", href: "/settings" },
];

const stats = [
  { label: "小说数量", value: "12", icon: BookOpen, trend: "+2" },
  { label: "剧本数量", value: "8", icon: FileText, trend: "+1" },
  { label: "角色数量", value: "24", icon: Users, trend: "+5" },
  { label: "视频数量", value: "6", icon: Video, trend: "+3" },
];

const recentActivities = [
  { action: "创建了新小说", target: "《星际穿越》", time: "2小时前", icon: Plus },
  { action: "生成了视频", target: "第一章", time: "5小时前", icon: Video },
  { action: "添加了角色", target: "主角-李明", time: "1天前", icon: Users },
  { action: "完成了剧本", target: "《未来世界》", time: "2天前", icon: CheckCircle },
];

export default function DashboardPage() {
  const router = useRouter();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside 
        className={cn(
          "fixed left-0 top-0 h-full bg-[#0d0d12] border-r border-white/10 transition-all duration-300 z-50",
          isSidebarOpen ? "w-64" : "w-20"
        )}
      >
        <div className="p-6">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
              <Video className="w-5 h-5 text-white" />
            </div>
            {isSidebarOpen && (
              <span className="font-bold text-lg">AI视频平台</span>
            )}
          </div>

          <nav className="space-y-2">
            {menuItems.map((item) => (
              <button
                key={item.label}
                onClick={() => router.push(item.href)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200",
                  item.active 
                    ? "bg-violet-500/20 text-violet-400 border border-violet-500/30" 
                    : "text-white/60 hover:text-white hover:bg-white/5"
                )}
              >
                <item.icon className="w-5 h-5" />
                {isSidebarOpen && <span>{item.label}</span>}
              </button>
            ))}
          </nav>
        </div>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-white/10">
          <button 
            onClick={() => router.push("/login")}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-white/60 hover:text-white hover:bg-white/5 transition-all"
          >
            <LogOut className="w-5 h-5" />
            {isSidebarOpen && <span>退出登录</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main 
        className={cn(
          "flex-1 transition-all duration-300",
          isSidebarOpen ? "ml-64" : "ml-20"
        )}
      >
        {/* Header */}
        <header className="h-16 border-b border-white/10 flex items-center justify-between px-8">
          <h1 className="text-xl font-semibold">概览</h1>
          <div className="flex items-center gap-4">
            <Button variant="secondary" size="sm">
              <Plus className="w-4 h-4 mr-2" />
              新建项目
            </Button>
          </div>
        </header>

        {/* Content */}
        <div className="p-8">
          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {stats.map((stat) => (
              <Card key={stat.label} className="hover:border-violet-500/30 transition-colors">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm text-white/60">{stat.label}</p>
                      <p className="text-2xl font-bold mt-1">{stat.value}</p>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-violet-500/10 flex items-center justify-center">
                      <stat.icon className="w-5 h-5 text-violet-400" />
                    </div>
                  </div>
                  <div className="flex items-center gap-1 mt-4 text-sm">
                    <TrendingUp className="w-4 h-4 text-green-400" />
                    <span className="text-green-400">{stat.trend}</span>
                    <span className="text-white/40">本周</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-violet-400" />
                最近活动
              </CardTitle>
              <CardDescription>您的创作动态</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentActivities.map((activity, index) => (
                  <div 
                    key={index}
                    className="flex items-center gap-4 p-4 rounded-lg bg-white/[0.02] hover:bg-white/[0.05] transition-colors"
                  >
                    <div className="w-10 h-10 rounded-lg bg-violet-500/10 flex items-center justify-center">
                      <activity.icon className="w-5 h-5 text-violet-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-white">
                        {activity.action}
                        <span className="text-violet-400 ml-1">{activity.target}</span>
                      </p>
                      <p className="text-sm text-white/40">{activity.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
