"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { 
  BarChart3, 
  TrendingUp, 
  TrendingDown, 
  Users, 
  Eye, 
  Download, 
  DollarSign,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Calendar,
  Filter
} from "lucide-react";
import { api } from "@/lib/api";

interface OverviewData {
  total_works: number;
  total_views: number;
  total_exports: number;
  avg_completion_rate: number;
  this_month_new_works: number;
  this_month_views: number;
  this_month_exports: number;
  growth_rate: {
    works: number;
    views: number;
    exports: number;
  };
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("month");

  useEffect(() => {
    loadOverview();
  }, [period]);

  const loadOverview = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/v1/analytics/overview?period=${period}`);
      setOverview(response.data);
    } catch (error) {
      console.error("加载数据失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 10000) {
      return (num / 10000).toFixed(1) + "万";
    }
    return num.toString();
  };

  const getGrowthIcon = (rate: number) => {
    if (rate > 0) {
      return <ArrowUpRight className="h-4 w-4 text-green-400" />;
    } else if (rate < 0) {
      return <ArrowDownRight className="h-4 w-4 text-red-400" />;
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 头部 */}
      <header className="glass border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              数据分析
            </h1>
            <div className="flex items-center gap-4">
              <select 
                value={period} 
                onChange={(e) => setPeriod(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm"
              >
                <option value="day">今日</option>
                <option value="week">本周</option>
                <option value="month">本月</option>
                <option value="year">本年</option>
              </select>
              <Button variant="outline" size="sm" className="bg-white/5 border-white/10">
                <Download className="h-4 w-4 mr-2" />
                导出报告
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 概览卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">总作品数</p>
                  <p className="text-3xl font-bold text-white mt-1">
                    {loading ? "-" : formatNumber(overview?.total_works || 0)}
                  </p>
                  <div className="flex items-center gap-1 mt-2">
                    {getGrowthIcon(overview?.growth_rate?.works || 0)}
                    <span className={`text-sm ${(overview?.growth_rate?.works || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {Math.abs(overview?.growth_rate?.works || 0).toFixed(1)}%
                    </span>
                    <span className="text-white/40 text-sm">vs 上月</span>
                  </div>
                </div>
                <div className="w-12 h-12 rounded-xl bg-violet-500/20 flex items-center justify-center">
                  <BarChart3 className="h-6 w-6 text-violet-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">总播放量</p>
                  <p className="text-3xl font-bold text-white mt-1">
                    {loading ? "-" : formatNumber(overview?.total_views || 0)}
                  </p>
                  <div className="flex items-center gap-1 mt-2">
                    {getGrowthIcon(overview?.growth_rate?.views || 0)}
                    <span className={`text-sm ${(overview?.growth_rate?.views || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {Math.abs(overview?.growth_rate?.views || 0).toFixed(1)}%
                    </span>
                    <span className="text-white/40 text-sm">vs 上月</span>
                  </div>
                </div>
                <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                  <Eye className="h-6 w-6 text-blue-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">导出次数</p>
                  <p className="text-3xl font-bold text-white mt-1">
                    {loading ? "-" : formatNumber(overview?.total_exports || 0)}
                  </p>
                  <div className="flex items-center gap-1 mt-2">
                    {getGrowthIcon(overview?.growth_rate?.exports || 0)}
                    <span className={`text-sm ${(overview?.growth_rate?.exports || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {Math.abs(overview?.growth_rate?.exports || 0).toFixed(1)}%
                    </span>
                    <span className="text-white/40 text-sm">vs 上月</span>
                  </div>
                </div>
                <div className="w-12 h-12 rounded-xl bg-green-500/20 flex items-center justify-center">
                  <Download className="h-6 w-6 text-green-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white/60 text-sm">平均完成率</p>
                  <p className="text-3xl font-bold text-white mt-1">
                    {loading ? "-" : `${(overview?.avg_completion_rate || 0).toFixed(1)}%`}
                  </p>
                  <div className="flex items-center gap-1 mt-2">
                    <span className="text-white/40 text-sm">作品完成比例</span>
                  </div>
                </div>
                <div className="w-12 h-12 rounded-xl bg-yellow-500/20 flex items-center justify-center">
                  <Activity className="h-6 w-6 text-yellow-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 详细数据 */}
        <Tabs defaultValue="works" className="space-y-6">
          <TabsList className="bg-white/5 border border-white/10">
            <TabsTrigger value="works" className="data-[state=active]:bg-violet-600">作品数据</TabsTrigger>
            <TabsTrigger value="users" className="data-[state=active]:bg-violet-600">用户行为</TabsTrigger>
            <TabsTrigger value="revenue" className="data-[state=active]:bg-violet-600">收益统计</TabsTrigger>
          </TabsList>

          <TabsContent value="works">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white">热门作品排行</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[
                    { title: "纳米漫剧第一集", views: 12345, completion: 85.5, exports: 234 },
                    { title: "企业宣传片", views: 8765, completion: 72.3, exports: 156 },
                    { title: "产品介绍视频", views: 6543, completion: 68.9, exports: 123 },
                    { title: "教程演示", views: 4321, completion: 91.2, exports: 89 },
                    { title: "创意短片", views: 3210, completion: 76.5, exports: 67 },
                  ].map((work, index) => (
                    <div key={index} className="flex items-center gap-4 p-3 rounded-lg bg-white/5">
                      <span className="text-white/40 w-8">{index + 1}</span>
                      <div className="flex-1">
                        <p className="text-white font-medium">{work.title}</p>
                        <div className="flex items-center gap-4 mt-1">
                          <span className="text-white/40 text-sm flex items-center gap-1">
                            <Eye className="h-3 w-3" /> {formatNumber(work.views)}
                          </span>
                          <span className="text-white/40 text-sm">
                            完成率 {work.completion}%
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-white font-medium">{work.exports} 导出</p>
                        <Badge className="bg-violet-500/20 text-violet-400 text-xs">
                          热门
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="users">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white">活跃用户</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                      <span className="text-white/80">日活跃用户 (DAU)</span>
                      <span className="text-white font-bold">1,234</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                      <span className="text-white/80">周活跃用户 (WAU)</span>
                      <span className="text-white font-bold">8,765</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                      <span className="text-white/80">月活跃用户 (MAU)</span>
                      <span className="text-white font-bold">15,678</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                      <span className="text-white/80">平均会话时长</span>
                      <span className="text-white font-bold">15.6 分钟</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                      <span className="text-white/80">次日留存率</span>
                      <span className="text-green-400 font-bold">68.5%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white">功能使用</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {[
                      { name: "AI生成", count: 4567, color: "bg-violet-500" },
                      { name: "模板使用", count: 3456, color: "bg-blue-500" },
                      { name: "语音合成", count: 2345, color: "bg-green-500" },
                      { name: "视频导出", count: 1234, color: "bg-yellow-500" },
                    ].map((feature) => (
                      <div key={feature.name} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-white/80">{feature.name}</span>
                          <span className="text-white">{feature.count.toLocaleString()}</span>
                        </div>
                        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${feature.color} rounded-full`}
                            style={{ width: `${(feature.count / 4567) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="revenue">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white">总收益</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-4xl font-bold text-white">¥12,345.67</p>
                  <div className="flex items-center gap-1 mt-2">
                    <ArrowUpRight className="h-4 w-4 text-green-400" />
                    <span className="text-green-400">+23.5%</span>
                    <span className="text-white/40 text-sm">vs 上月</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white">待结算</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-4xl font-bold text-white">¥1,234.56</p>
                  <p className="text-white/40 text-sm mt-2">预计7天内到账</p>
                </CardContent>
              </Card>

              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white">已提现</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-4xl font-bold text-white">¥10,000.00</p>
                  <Button variant="outline" size="sm" className="mt-2 bg-white/5 border-white/10">
                    申请提现
                  </Button>
                </CardContent>
              </Card>
            </div>

            <Card className="mt-6 bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white">收益来源</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-lg bg-white/5">
                    <p className="text-white/60 text-sm">模板销售</p>
                    <p className="text-2xl font-bold text-white mt-1">¥5,678.90</p>
                    <p className="text-white/40 text-sm mt-1">占比 46%</p>
                  </div>
                  <div className="p-4 rounded-lg bg-white/5">
                    <p className="text-white/60 text-sm">会员分成</p>
                    <p className="text-2xl font-bold text-white mt-1">¥4,567.77</p>
                    <p className="text-white/40 text-sm mt-1">占比 37%</p>
                  </div>
                  <div className="p-4 rounded-lg bg-white/5">
                    <p className="text-white/60 text-sm">API调用</p>
                    <p className="text-2xl font-bold text-white mt-1">¥2,099.00</p>
                    <p className="text-white/40 text-sm mt-1">占比 17%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}