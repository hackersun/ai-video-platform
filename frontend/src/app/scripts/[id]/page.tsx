'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  FileText, 
  ArrowLeft,
  Save,
  Loader2,
  AlertCircle,
  Eye,
  Sparkles,
  Film,
  LayoutGrid,
  Clock,
  Plus,
  Edit2,
  Trash2,
  Play
} from 'lucide-react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Script {
  id: string;
  title: string;
  description?: string;
  content?: string;
  genre?: string;
  style?: string;
  duration?: number;
  status: 'draft' | 'writing' | 'completed';
  novel_id?: string;
  created_at: string;
  updated_at: string;
}

interface Storyboard {
  id: string;
  title: string;
  status: string;
  shots_count?: number;
  created_at: string;
}

export default function ScriptDetailPage() {
  const params = useParams();
  const router = useRouter();
  const scriptId = params.id as string;
  
  const [script, setScript] = useState<Script | null>(null);
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [generatingStoryboard, setGeneratingStoryboard] = useState(false);
  
  // 编辑状态
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [content, setContent] = useState('');

  useEffect(() => {
    if (scriptId) {
      loadScript();
    }
  }, [scriptId]);

  const loadScript = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/scripts/${scriptId}`);
      
      if (response.ok) {
        const data = await response.json();
        setScript(data);
        setTitle(data.title || '');
        setDescription(data.description || '');
        setContent(data.content || '');
        
        // 加载关联的分镜
        loadStoryboards(scriptId);
      } else {
        throw new Error('剧本不存在');
      }
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadStoryboards = async (sid: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/storyboards?script_id=${sid}`);
      if (response.ok) {
        const data = await response.json();
        setStoryboards(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('加载分镜失败:', err);
    }
  };

  const handleSave = async () => {
    if (!title.trim()) {
      alert('请输入剧本标题');
      return;
    }
    
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/scripts/${scriptId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          description,
          content,
          status: script?.status
        })
      });
      
      if (response.ok) {
        setHasChanges(false);
        alert('保存成功！');
      } else {
        throw new Error('保存失败');
      }
    } catch (err: any) {
      alert(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateStoryboard = async () => {
    if (!script) return;
    
    setGeneratingStoryboard(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/storyboards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${script.title} - 分镜`,
          description: script.description,
          script_id: script.id
        })
      });
      
      if (response.ok) {
        const newStoryboard = await response.json();
        alert('分镜创建成功！');
        // 刷新分镜列表
        loadStoryboards(scriptId);
      } else {
        throw new Error('创建失败');
      }
    } catch (err: any) {
      alert(err.message || '生成分镜失败');
    } finally {
      setGeneratingStoryboard(false);
    }
  };

  // 监听内容变化
  useEffect(() => {
    if (script && (title !== script.title || description !== (script.description || '') || content !== (script.content || ''))) {
      setHasChanges(true);
    }
  }, [title, description, content, script]);

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      </MainLayout>
    );
  }

  if (error || !script) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          <h2 className="text-xl font-bold text-white mb-2">{error || '剧本不存在'}</h2>
          <Button onClick={() => router.push('/scripts')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回剧本列表
          </Button>
        </div>
      </MainLayout>
    );
  }

  const STATUS_COLORS = {
    draft: 'bg-yellow-500/20 text-yellow-400',
    writing: 'bg-blue-500/20 text-blue-400',
    completed: 'bg-green-500/20 text-green-400'
  };

  const STATUS_LABELS = {
    draft: '草稿',
    writing: '连载中',
    completed: '已完成'
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => router.push('/scripts')}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <FileText className="w-6 h-6" />
                {script.title}
              </h1>
              <div className="flex items-center gap-2 mt-1">
                <Badge className={STATUS_COLORS[script.status]}>
                  {STATUS_LABELS[script.status]}
                </Badge>
                {script.genre && (
                  <span className="text-white/60 text-sm">{script.genre}</span>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {hasChanges && (
              <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                未保存
              </Badge>
            )}
            <Button 
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              保存
            </Button>
          </div>
        </div>

        {/* 标签页 */}
        <Tabs defaultValue="content" className="space-y-4">
          <TabsList className="bg-white/5">
            <TabsTrigger value="content" className="data-[state=active]:bg-blue-600">
              <FileText className="w-4 h-4 mr-2" />
              剧本内容
            </TabsTrigger>
            <TabsTrigger value="storyboards" className="data-[state=active]:bg-blue-600">
              <LayoutGrid className="w-4 h-4 mr-2" />
              分镜 ({storyboards.length})
            </TabsTrigger>
          </TabsList>

          {/* 剧本内容 */}
          <TabsContent value="content">
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-white/80 mb-2 block">剧本标题</label>
                    <Input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="输入剧本标题"
                      className="bg-white/10 border-white/20 text-white"
                    />
                  </div>
                  <div>
                    <label className="text-white/80 mb-2 block">题材</label>
                    <Input
                      value={script.genre || ''}
                      disabled
                      className="bg-white/5 border-white/20 text-white/60"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="text-white/80 mb-2 block">剧本描述</label>
                  <Input
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="简要描述剧本内容"
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                
                <div>
                  <label className="text-white/80 mb-2 block">剧本正文</label>
                  <Textarea
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    placeholder="输入或粘贴剧本内容..."
                    className="bg-white/10 border-white/20 text-white min-h-[400px] resize-none"
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* 分镜列表 */}
          <TabsContent value="storyboards">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">分镜列表</CardTitle>
                <Button 
                  onClick={handleGenerateStoryboard}
                  disabled={generatingStoryboard}
                  className="bg-purple-600 hover:bg-purple-700"
                >
                  {generatingStoryboard ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4 mr-2" />
                  )}
                  生成分镜
                </Button>
              </CardHeader>
              <CardContent>
                {storyboards.length === 0 ? (
                  <div className="text-center py-12">
                    <LayoutGrid className="w-12 h-12 mx-auto text-white/20 mb-4" />
                    <p className="text-white/60 mb-2">暂无分镜</p>
                    <p className="text-white/40 text-sm">点击"生成分镜"基于剧本创建分镜</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {storyboards.map((sb) => (
                      <div
                        key={sb.id}
                        className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <LayoutGrid className="w-5 h-5 text-purple-400" />
                          <div>
                            <div className="text-white font-medium">{sb.title}</div>
                            <div className="text-white/40 text-sm flex items-center gap-2">
                              <span>{sb.shots_count || 0} 个镜头</span>
                              <span>·</span>
                              <span>{new Date(sb.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Link href={`/storyboards?sb=${sb.id}`}>
                            <Button variant="ghost" size="sm">
                              <Eye className="w-4 h-4 mr-1" />
                              查看
                            </Button>
                          </Link>
                          <Link href={`/video-generation?storyboard=${sb.id}`}>
                            <Button variant="ghost" size="sm" className="text-purple-400">
                              <Film className="w-4 h-4 mr-1" />
                              生成视频
                            </Button>
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* 底部快捷操作 */}
        {script.status === 'completed' && storyboards.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="bg-gradient-to-br from-purple-600/20 to-fuchsia-600/20 border-purple-500/30 cursor-pointer hover:border-purple-500/50 transition-colors">
              <Link href={`/storyboards`}>
                <CardContent className="p-4 text-center">
                  <LayoutGrid className="w-8 h-8 mx-auto mb-2 text-purple-400" />
                  <div className="text-white font-medium">查看分镜</div>
                  <div className="text-white/60 text-sm">管理分镜和镜头</div>
                </CardContent>
              </Link>
            </Card>
            <Card className="bg-gradient-to-br from-violet-600/20 to-indigo-600/20 border-violet-500/30 cursor-pointer hover:border-violet-500/50 transition-colors">
              <Link href={`/video-generation?script=${scriptId}`}>
                <CardContent className="p-4 text-center">
                  <Film className="w-8 h-8 mx-auto mb-2 text-violet-400" />
                  <div className="text-white font-medium">生成视频</div>
                  <div className="text-white/60 text-sm">基于剧本生成视频</div>
                </CardContent>
              </Link>
            </Card>
          </div>
        )}
      </div>
    </MainLayout>
  );
}
