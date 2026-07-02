"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
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
    title: "导入小说",
    description: "粘贴完整小说或首章内容，AI先整理故事主线",
  },
  {
    icon: Palette,
    title: "统一角色与世界观",
    description: "自动生成动漫设定本，锁定人物、场景、道具和风格",
  },
  {
    icon: Zap,
    title: "制作第一集",
    description: "自动生成剧本、分镜、配音、字幕和可预览草片",
  },
  {
    icon: Film,
    title: "连续多集一致",
    description: "后续集数复用同一套设定，减少反复调提示词",
  },
];

const highlights = [
  "适合完整小说改编",
  "自动维护角色与声线一致性",
  "支持首集几秒草片验证",
  "保留高级模型与提示词配置",
];

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? "/quick-start" : "/login";

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
            <span className="text-sm text-violet-300">小说一键变连续动漫</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
            把完整小说
            <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-blue-400 bg-clip-text text-transparent">
              做成连续动漫
            </span>
          </h1>

          <p className="text-xl text-white/60 max-w-2xl mx-auto mb-10">
            不用先学分镜、提示词和模型参数。
            <br />
            先导入故事，AI帮你统一风格、角色、场景、道具和声音，再生成第一集草片。
          </p>

          <div className="flex items-center justify-center gap-4">
            <Button asChild size="lg">
              <Link href={startHref}>
                开始连续动漫向导
                <ArrowRight className="w-4 h-4 ml-2" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <a href="#features">
                了解更多
              </a>
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
      <section id="features" className="py-20 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold mb-4">从第一章到第一集</h2>
            <p className="text-white/60">把专业制作流程收进一个向导里，必要时再进入高级工具精修</p>
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
              <h2 className="text-3xl font-bold mb-4">先做一集，验证风格</h2>
              <p className="text-white/60 mb-8 max-w-xl mx-auto">
                用一段小说生成几秒草片，确认人物、场景、声音和节奏后，再扩展到多集连续制作。
              </p>
              <Button asChild size="lg">
                <Link href={startHref}>
                  进入向导
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Link>
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
