"use client";

import { useState, useEffect } from "react";
import { Link } from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { 
  Search, 
  Grid, 
  List, 
  Filter, 
  Heart, 
  Download, 
  Star,
  Plus,
  Sparkles,
  Video,
  Megaphone,
  Package,
  Book,
  Share2,
  Target,
  Camera,
  Film
} from "lucide-react";
import { api } from "@/lib/api";

interface Template {
  id: string;
  title: string;
  description: string;
  thumbnail_url: string;
  price: number;
  download_count: number;
  rating: number;
  content_type: string;
  style_type: string;
}

const contentTypeIcons: Record<string, any> = {
  short_video: Video,
  promo: Megaphone,
  product: Package,
  education: Book,
  social: Share2,
  ad: Target,
  vlog: Camera,
  animation: Film,
};

export default function TemplateMarketPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedStyle, setSelectedStyle] = useState("all");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  useEffect(() => {
    loadTemplates();
  }, [selectedCategory, selectedStyle]);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (selectedCategory !== "all") params.content_type = selectedCategory;
      if (selectedStyle !== "all") params.style_type = selectedStyle;
      if (searchTerm) params.search = searchTerm;

      const response = await api.get("/api/v1/templates/market", { params });
      setTemplates(response.data.items || []);
    } catch (error) {
      console.error("加载模板失败:", error);
      // 使用示例数据
      setTemplates([
        {
          id: "1",
          title: "电商产品展示模板",
          description: "适合电商产品展示的动画模板",
          thumbnail_url: "",
          price: 0,
          download_count: 1234,
          rating: 4.8,
          content_type: "product",
          style_type: "modern",
        },
        {
          id: "2",
          title: "企业宣传片模板",
          description: "专业大气的企业宣传片",
          thumbnail_url: "",
          price: 99,
          download_count: 567,
          rating: 4.9,
          content_type: "promo",
          style_type: "business",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const categories = [
    { id: "all", name: "全部", icon: Grid },
    { id: "short_video", name: "短视频", icon: Video },
    { id: "promo", name: "宣传片", icon: Megaphone },
    { id: "product", name: "产品介绍", icon: Package },
    { id: "education", name: "教育培训", icon: Book },
    { id: "social", name: "社交媒体", icon: Share2 },
    { id: "ad", name: "广告", icon: Target },
    { id: "animation", name: "动画", icon: Film },
  ];

  const styles = [
    { id: "all", name: "全部风格" },
    { id: "business", name: "商务专业" },
    { id: "lively", name: "活泼可爱" },
    { id: "tech", name: "科技感" },
    { id: "retro", name: "复古风" },
    { id: "cinematic", name: "电影感" },
  ];

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 头部 */}
      <header className="glass sticky top-0 z-50 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/dashboard" className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold gradient-text">AI视频平台</span>
            </Link>

            <nav className="hidden md:flex items-center gap-6">
              <Link href="/dashboard" className="text-white/60 hover:text-white transition-colors">控制台</Link>
              <Link href="/templates" className="text-white font-medium">模板市场</Link>
              <Link href="/tts" className="text-white/60 hover:text-white transition-colors">语音合成</Link>
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <Film className="h-8 w-8 text-violet-400" />
            模板市场
          </h1>
          <p className="text-white/60 mt-2">发现优质模板，快速创建专业视频</p>
        </div>

        {/* 搜索和筛选 */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <Input
              type="text"
              placeholder="搜索模板..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 bg-white/5 border-white/10 text-white placeholder-white/40"
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant={viewMode === "grid" ? "default" : "outline"}
              size="icon"
              onClick={() => setViewMode("grid")}
              className="bg-white/5 border-white/10"
            >
              <Grid className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === "list" ? "default" : "outline"}
              size="icon"
              onClick={() => setViewMode("list")}
              className="bg-white/5 border-white/10"
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* 分类导航 */}
        <div className="flex gap-2 mb-8 overflow-x-auto pb-2">
          {categories.map((cat) => {
            const Icon = cat.icon;
            return (
              <Button
                key={cat.id}
                variant={selectedCategory === cat.id ? "default" : "outline"}
                onClick={() => setSelectedCategory(cat.id)}
                className="flex items-center gap-2 whitespace-nowrap bg-white/5 border-white/10 hover:bg-white/10"
              >
                <Icon className="h-4 w-4" />
                {cat.name}
              </Button>
            );
          })}
        </div>

        {/* 风格筛选 */}
        <div className="flex gap-2 mb-8">
          {styles.map((style) => (
            <Button
              key={style.id}
              variant={selectedStyle === style.id ? "default" : "ghost"}
              size="sm"
              onClick={() => setSelectedStyle(style.id)}
              className="text-white/60 hover:text-white"
            >
              {style.name}
            </Button>
          ))}
        </div>

        {/* 模板列表 */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="bg-white/5 rounded-xl h-64"></div>
              </div>
            ))}
          </div>
        ) : templates.length > 0 ? (
          <div className={`grid gap-6 ${viewMode === "grid" ? "grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" : "grid-cols-1"}`}>
            {templates.map((template) => {
              const IconComponent = contentTypeIcons[template.content_type] || Video;
              return (
                <Card key={template.id} className="bg-white/5 border-white/10 overflow-hidden hover:border-violet-500/50 transition-all group">
                  {/* 缩略图 */}
                  <div className="relative aspect-video bg-gradient-to-br from-violet-900/50 to-indigo-900/50 flex items-center justify-center">
                    <IconComponent className="h-16 w-16 text-white/20" />
                    {template.price === 0 && (
                      <Badge className="absolute top-2 right-2 bg-green-500">免费</Badge>
                    )}
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                      <Button size="sm" className="bg-violet-600">
                        <Download className="h-4 w-4 mr-1" />
                        使用
                      </Button>
                      <Button size="sm" variant="outline" className="bg-white/10">
                        <Heart className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  
                  <CardContent className="p-4">
                    <h3 className="text-white font-medium mb-1 line-clamp-1">{template.title}</h3>
                    <p className="text-white/40 text-sm mb-3 line-clamp-2">{template.description}</p>
                    
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 text-yellow-400 fill-yellow-400" />
                        <span className="text-white/60 text-sm">{template.rating.toFixed(1)}</span>
                      </div>
                      <span className="text-white/40 text-sm">{template.download_count} 次使用</span>
                    </div>
                    
                    {template.price > 0 && (
                      <div className="mt-3 pt-3 border-t border-white/10">
                        <span className="text-violet-400 font-bold">¥{template.price}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-20">
            <Film className="h-16 w-16 text-white/20 mx-auto mb-4" />
            <p className="text-white/40 mb-4">暂无模板</p>
            <Button className="bg-violet-600">
              <Plus className="h-4 w-4 mr-2" />
              创建第一个模板
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}