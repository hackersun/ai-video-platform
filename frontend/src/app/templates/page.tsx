'use client';

import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LayoutTemplate, Search, Star, Download } from 'lucide-react';

const templates = [
  { id: 1, name: '仙侠开场模板', category: '仙侠', downloads: 1280, rating: 4.8 },
  { id: 2, name: '都市情感模板', category: '都市', downloads: 856, rating: 4.6 },
  { id: 3, name: '科幻冒险模板', category: '科幻', downloads: 642, rating: 4.7 },
  { id: 4, name: '历史剧模板', category: '历史', downloads: 423, rating: 4.5 },
];

export default function TemplatesPage() {
  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">模板市场</h1>
            <p className="text-white/60 mt-1">浏览和使用创作模板</p>
          </div>
        </div>

        {/* 搜索和筛选 */}
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <Input
              placeholder="搜索模板..."
              className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
            />
          </div>
          <Button variant="outline" className="border-white/20 text-white">
            全部
          </Button>
          <Button variant="outline" className="border-white/20 text-white">
            热门
          </Button>
          <Button variant="outline" className="border-white/20 text-white">
            最新
          </Button>
        </div>

        {/* 模板列表 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((template) => (
            <Card key={template.id} className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <LayoutTemplate className="w-5 h-5 text-violet-400" />
                  {template.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm text-white/60 mb-4">
                  <span>{template.category}</span>
                  <div className="flex items-center gap-1">
                    <Star className="w-4 h-4 text-yellow-400" />
                    {template.rating}
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-white/40 text-sm">
                    <Download className="w-3 h-3 inline mr-1" />
                    {template.downloads}
                  </span>
                  <Button size="sm" className="bg-violet-600 hover:bg-violet-700">
                    使用模板
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </MainLayout>
  );
}