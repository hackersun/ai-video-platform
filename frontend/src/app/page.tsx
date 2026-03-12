"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { 
  Film, 
  Sparkles, 
  Zap, 
  Palette,
  ArrowRight,
  CheckCircle
} from "lucide-react";

const features = [
  {
    icon: Sparkles,
    title: "AI智能创作",
    description: "基于大语言模型，自动生成精彩剧本",
  },
  {
    icon: Palette,
    title: "精美视觉",
    description: "现代化UI设计，流畅动画效果",
  },
  {
    icon: Zap,
    title: "高效工作流",
    description: "从小说到视频，一站式创作体验",
  },
  {
    icon: Film,
    title: "视频生成",
    description: "AI驱动，一键生成高质量视频",
  },
];

const highlights = [
  "支持多种小说格式导入",
  "智能角色管理系统",
  "可视化剧本编辑器",
  "AI辅助视频生成",
];

export default function HomePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-20 pb-32 px-4 overflow-hidden">
        {/* Background effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-violet-500/10 rounded-full blur-3xl" />
          <div className="absolute top-1/4 right-0 w-[600px] h-[600px] bg-blue-500/10 rounded-full blur-3xl" />
        </div>

        <div className="max-w-6xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-500/10 border border-violet-500/20 mb-8">
            <Sparkles className="w-4 h-4 text-violet-400" />
            <span className="text-sm text-violet-300">AI驱动的视频创作平台</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
            让创意
            <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-blue-400 bg-clip-text text-transparent">
              无限可能
            </span>
          </h1>

          <p className="text-xl text-white/60 max-w-2xl mx-auto mb-10">
            从小说到视频，AI助力您的创作之旅。
            <br />
            简单、高效、专业。
          </p>

          <div className="flex items-center justify-center gap-4">
            <Button size="lg" onClick={() => router.push("/login")}>
              开始创作
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button variant="outline" size="lg">
              了解更多
            </Button>
          </div>

          {/* Highlights */}
          <div className="flex flex-wrap items-center justify-center gap-6 mt-12">
            {highlights.map((item) => (
              <div key={item} className="flex items-center gap-2 text-sm text-white/60">
                <CheckCircle className="w-4 h-4 text-green-400" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold mb-4">强大功能</h2>
            <p className="text-white/60">为您的创作提供全方位支持</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature) => (
              <Card 
                key={feature.title}
                className="p-6 hover:border-violet-500/30 transition-all group"
              >
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <feature.icon className="w-6 h-6 text-violet-400" />
                </div>
                <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
                <p className="text-sm text-white/60">{feature.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <Card className="p-12 relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-violet-500/10 to-blue-500/10" />
            <div className="relative z-10">
              <h2 className="text-3xl font-bold mb-4">准备好开始了吗？</h2>
              <p className="text-white/60 mb-8 max-w-xl mx-auto">
                立即加入，开启您的AI视频创作之旅。
                无需信用卡，免费开始使用。
              </p>
              <Button size="lg" onClick={() => router.push("/login")}>
                免费开始
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 border-t border-white/10">
        <div className="max-w-6xl mx-auto text-center text-sm text-white/40">
          © 2024 AI视频平台. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
