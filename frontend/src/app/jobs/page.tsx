"use client";

import { useState } from "react";
import { MainLayout } from "@/components/layout/main-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  ListTodo, 
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  Film,
  Mic,
  Image as ImageIcon,
  FileText
} from "lucide-react";

// 模拟任务数据
const mockJobs = [
  {
    id: "job-001",
    type: "video_generation",
    status: "completed",
    title: "视频生成 - 第一章",
    progress: 100,
    createdAt: "2026-03-14 10:00",
  },
  {
    id: "job-002",
    type: "image_generation",
    status: "processing",
    title: "图片生成 - 角色头像",
    progress: 65,
    createdAt: "2026-03-14 11:30",
  },
  {
    id: "job-003",
    type: "tts",
    status: "pending",
    title: "语音合成 - 旁白",
    progress: 0,
    createdAt: "2026-03-14 12:00",
  },
];

const getStatusIcon = (status: string) => {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-5 h-5 text-green-400" />;
    case "processing":
      return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
    case "pending":
      return <Clock className="w-5 h-5 text-yellow-400" />;
    case "failed":
      return <AlertCircle className="w-5 h-5 text-red-400" />;
    default:
      return <Clock className="w-5 h-5 text-white/40" />;
  }
};

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    completed: "已完成",
    processing: "处理中",
    pending: "等待中",
    failed: "失败",
  };
  return statusMap[status] || status;
};

const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    completed: "bg-green-500/20 text-green-400",
    processing: "bg-blue-500/20 text-blue-400",
    pending: "bg-yellow-500/20 text-yellow-400",
    failed: "bg-red-500/20 text-red-400",
  };
  return colorMap[status] || "bg-white/10 text-white/60";
};

const getTypeIcon = (type: string) => {
  switch (type) {
    case "video_generation":
      return <Film className="w-5 h-5" />;
    case "image_generation":
      return <ImageIcon className="w-5 h-5" />;
    case "tts":
      return <Mic className="w-5 h-5" />;
    case "script_generation":
      return <FileText className="w-5 h-5" />;
    default:
      return <ListTodo className="w-5 h-5" />;
  }
};

export default function JobsPage() {
  const [jobs, setJobs] = useState(mockJobs);
  const [filter, setFilter] = useState("all");

  const filteredJobs = filter === "all" 
    ? jobs 
    : jobs.filter(job => job.status === filter);

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <ListTodo className="w-6 h-6" />
              任务队列
            </h1>
            <p className="text-white/60 mt-1">查看和管理AI生成任务</p>
          </div>
          <Button variant="outline" className="border-white/10 text-white hover:bg-white/5">
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-white">{jobs.length}</div>
              <div className="text-white/60 text-sm">总任务</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-yellow-400">
                {jobs.filter(j => j.status === "pending").length}
              </div>
              <div className="text-white/60 text-sm">等待中</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-blue-400">
                {jobs.filter(j => j.status === "processing").length}
              </div>
              <div className="text-white/60 text-sm">处理中</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-green-400">
                {jobs.filter(j => j.status === "completed").length}
              </div>
              <div className="text-white/60 text-sm">已完成</div>
            </CardContent>
          </Card>
        </div>

        {/* 筛选标签 */}
        <div className="flex gap-2">
          {["all", "pending", "processing", "completed", "failed"].map((status) => (
            <Button
              key={status}
              variant={filter === status ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(status)}
              className={
                filter === status
                  ? "bg-violet-600 text-white"
                  : "border-white/10 text-white/60 hover:bg-white/5"
              }
            >
              {status === "all" ? "全部" : getStatusText(status)}
            </Button>
          ))}
        </div>

        {/* 任务列表 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white">任务列表</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {filteredJobs.length > 0 ? (
              filteredJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center gap-4 p-4 rounded-lg bg-white/5 border border-white/10"
                >
                  <div className="p-2 rounded-lg bg-violet-500/20 text-violet-400">
                    {getTypeIcon(job.type)}
                  </div>
                  <div className="flex-1">
                    <div className="text-white font-medium">{job.title}</div>
                    <div className="text-white/40 text-sm">{job.createdAt}</div>
                  </div>
                  <div className="flex items-center gap-3">
                    {job.status === "processing" && (
                      <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-violet-500 transition-all"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    )}
                    <Badge className={getStatusColor(job.status)}>
                      <span className="flex items-center gap-1">
                        {getStatusIcon(job.status)}
                        {getStatusText(job.status)}
                      </span>
                    </Badge>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-12">
                <ListTodo className="w-12 h-12 text-white/20 mx-auto mb-4" />
                <p className="text-white/60">暂无任务</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
