'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  BookOpen, 
  ArrowLeft,
  Save,
  Loader2,
  AlertCircle,
  FileText,
  Users,
  Sparkles,
  Film,
  Clock
} from 'lucide-react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Chapter {
  id: string;
  novel_id: string;
  title: string;
  content: string;
  chapter_number: number;
  word_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

interface Novel {
  id: string;
  title: string;
  description?: string;
}

export default function ChapterDetailPage() {
  const params = useParams();
  const router = useRouter();
  const novelId = params.id as string;
  const chapterId = params.chapterId as string;
  
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [novel, setNovel] = useState<Novel | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // 编辑状态
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (novelId && chapterId) {
      loadChapter();
    }
  }, [novelId, chapterId]);

  const loadChapter = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Authorization': `Bearer ${token}` };
      
      const [chapterRes, novelRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/chapters/${chapterId}`, { headers }),
        fetch(`${API_BASE}/api/v1/novels/${novelId}`, { headers })
      ]);
      
      if (chapterRes.ok) {
        const data = await chapterRes.json();
        setChapter(data);
        setTitle(data.title);
        setContent(data.content || '');
      } else {
        throw new Error('章节不存在');
      }
      
      if (novelRes.ok) {
        setNovel(await novelRes.json());
      }
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!title.trim()) {
      alert('请输入章节标题');
      return;
    }
    
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/v1/chapters/${chapterId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          title,
          content
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

  // 监听内容变化
  useEffect(() => {
    if (chapter && (title !== chapter.title || content !== (chapter.content || ''))) {
      setHasChanges(true);
    }
  }, [title, content, chapter]);

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
        </div>
      </MainLayout>
    );
  }

  if (error || !chapter) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          <h2 className="text-xl font-bold text-white mb-2">{error || '章节不存在'}</h2>
          <Button onClick={() => router.push(`/novels/${novelId}`)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回小说
          </Button>
        </div>
      </MainLayout>
    );
  }

  const wordCount = content.trim().split(/\s+/).filter(Boolean).length;

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => router.push(`/novels/${novelId}`)}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <FileText className="w-6 h-6" />
                {chapter.novel_id ? `第${chapter.chapter_number}章` : '章节编辑'}
              </h1>
              {novel && (
                <p className="text-white/60 text-sm mt-1">
                  《{novel.title}》
                </p>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="text-white/60 border-white/20">
              <Clock className="w-3 h-3 mr-1" />
              {wordCount} 字
            </Badge>
            {hasChanges && (
              <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                未保存
              </Badge>
            )}
            <Button 
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="bg-violet-600 hover:bg-violet-700"
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

        {/* 章节内容编辑 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-6 space-y-4">
            <div>
              <label className="text-white/80 mb-2 block">章节标题</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="输入章节标题"
                className="bg-white/10 border-white/20 text-white text-lg"
              />
            </div>
            
            <div>
              <label className="text-white/80 mb-2 block">章节内容</label>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="开始创作您的章节内容..."
                className="bg-white/10 border-white/20 text-white min-h-[500px] resize-none"
              />
            </div>
          </CardContent>
        </Card>

        {/* 底部快捷操作 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-gradient-to-br from-violet-600/20 to-purple-600/20 border-violet-500/30 cursor-pointer hover:border-violet-500/50 transition-colors">
            <Link href={`/novels/${novelId}`}>
              <CardContent className="p-4 text-center">
                <BookOpen className="w-8 h-8 mx-auto mb-2 text-violet-400" />
                <div className="text-white font-medium">返回小说</div>
                <div className="text-white/60 text-sm">查看小说详情</div>
              </CardContent>
            </Link>
          </Card>
          <Card className="bg-gradient-to-br from-blue-600/20 to-cyan-600/20 border-blue-500/30 cursor-pointer hover:border-blue-500/50 transition-colors">
            <Link href={`/characters?novel_id=${novelId}`}>
              <CardContent className="p-4 text-center">
                <Users className="w-8 h-8 mx-auto mb-2 text-blue-400" />
                <div className="text-white font-medium">角色管理</div>
                <div className="text-white/60 text-sm">管理小说角色</div>
              </CardContent>
            </Link>
          </Card>
          <Card className="bg-gradient-to-br from-green-600/20 to-emerald-600/20 border-green-500/30 cursor-pointer hover:border-green-500/50 transition-colors">
            <Link href={`/scripts/new?novel_id=${novelId}&chapter_id=${chapterId}`}>
              <CardContent className="p-4 text-center">
                <Film className="w-8 h-8 mx-auto mb-2 text-green-400" />
                <div className="text-white font-medium">基于本章创作</div>
                <div className="text-white/60 text-sm">生成分镜剧本</div>
              </CardContent>
            </Link>
          </Card>
        </div>
      </div>
    </MainLayout>
  );
}
