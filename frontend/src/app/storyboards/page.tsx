"use client";

import { useState } from "react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  LayoutGrid, 
  Plus, 
  Film,
  Image as ImageIcon,
  Wand2
} from "lucide-react";

export default function StoryboardsPage() {
  const [storyboards, setStoryboards] = useState([]);

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <LayoutGrid className="w-6 h-6" />
              分镜管理
            </h1>
            <p className="text-white/60 mt-1">创建和管理视频分镜设计</p>
          </div>
          <Button className="bg-violet-600 hover:bg-violet-700">
            <Plus className="w-4 h-4 mr-2" />
            新建分镜
          </Button>
        </div>

        {/* 功能介绍 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <Film className="w-8 h-8 text-violet-400 mb-2" />
              <CardTitle className="text-white text-lg">场景规划</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-white/60">规划视频场景和镜头顺序</p>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <ImageIcon className="w-8 h-8 text-violet-400 mb-2" />
              <CardTitle className="text-white text-lg">镜头设计</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-white/60">设计每个镜头的画面和动作</p>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <Wand2 className="w-8 h-8 text-violet-400 mb-2" />
              <CardTitle className="text-white text-lg">AI生成</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-white/60">AI辅助生成分镜图</p>
            </CardContent>
          </Card>
        </div>

        {/* 空状态 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <LayoutGrid className="w-16 h-16 text-white/20 mb-4" />
            <h3 className="text-xl font-medium text-white mb-2">暂无分镜</h3>
            <p className="text-white/60 mb-6">创建您的第一个分镜项目</p>
            <Button className="bg-violet-600 hover:bg-violet-700">
              <Plus className="w-4 h-4 mr-2" />
              创建分镜
            </Button>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
