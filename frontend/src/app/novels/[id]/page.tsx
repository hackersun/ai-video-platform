'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  BookOpen, 
  Plus, 
  Edit2, 
  Trash2,
  Search,
  FileText,
  Users,
  Clock,
  Copy,
  Eye,
  Loader2,
  AlertCircle,
  ArrowLeft,
  Sparkles,
  Film,
  Volume2,
  Image,
  Play,
  Settings
} from 'lucide-react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Novel {
  id: string;
  title: string;
  description?: string;
  genre?: string;
  status: string;
  cover_url?: string;
  created_at: string;
  updated_at: string;
}

interface Chapter {
  id: string;
  title: string;
  chapter_number: number;
  word_count?: number;
  status: string;
  created_at: string;
}

interface Character {
  id: string;
  name: string;
  description?: string;
  avatar_url?: string;
}

interface Script {
  id: string;
  title: string;
  genre?: string;
  status: string;
  created_at: string;
}

export default function NovelDetailPage() {
  const params = useParams();
  const router = useRouter();
  const novelId = params.id as string;
  
  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 新章节表单
  const [showChapterForm, setShowChapterForm] = useState(false);
  const [newChapterTitle, setNewChapterTitle] = useState('');
  const [newChapterContent, setNewChapterContent] = useState('');
  const [creatingChapter, setCreatingChapter] = useState(false);
  
  // 新角色表单
  const [showCharacterForm, setShowCharacterForm] = useState(false);
  const [newCharacterName, setNewCharacterName] = useState('');
  const [newCharacterDesc, setNewCharacterDesc] = useState('');
  const [creatingCharacter, setCreatingCharacter] = useState(false);

  useEffect(() => {
    if (novelId) {
      loadNovelData();
    }
  }, [novelId]);

  const loadNovelData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Authorization': `Bearer ${token}` };
      
      // 并行加载小说、章节、角色、剧本
      const [novelRes, chaptersRes, charactersRes, scriptsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/novels/${novelId}`, { headers }),
        fetch(`${API_BASE}/api/v1/chapters/novel/${novelId}`, { headers }),
        fetch(`${API_BASE}/api/v1/characters?novel_id=${novelId}`, { headers }),
        fetch(`${API_BASE}/api/v1/scripts?novel_id=${novelId}`, { headers })
      ]);
      
      if (novelRes.ok) {
        const novelData = await novelRes.json();
        setNovel(novelData);
      }
      
      if (chaptersRes.ok) {
        const chaptersData = await chaptersRes.json();
        setChapters(Array.isArray(chaptersData) ? chaptersData : []);
      }
      
      if (charactersRes.ok) {
        const charsData = await charactersRes.json();
        setCharacters(Array.isArray(charsData) ? charsData : []);
      }
      
      if (scriptsRes.ok) {
        const scriptsData = await scriptsRes.json();
        setScripts(Array.isArray(scriptsData) ? scriptsData : []);
      }
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const createChapter = async () => {
    if (!newChapterTitle.trim()) return;
    
    setCreatingChapter(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_BASE}/api/v1/chapters`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          novel_id: novelId,
          title: newChapterTitle,
          content: newChapterContent || ' '
        })
      });
      
      if (res.ok) {
        setNewChapterTitle('');
        setNewChapterContent('');
        setShowChapterForm(false);
        loadNovelData();
      }
    } finally {
      setCreatingChapter(false);
    }
  };

  const createCharacter = async () => {
    if (!newCharacterName.trim()) return;
    
    setCreatingCharacter(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_BASE}/api/v1/characters`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          novel_id: novelId,
          name: newCharacterName,
          description: newCharacterDesc
        })
      });
      
      if (res.ok) {
        setNewCharacterName('');
        setNewCharacterDesc('');
        setShowCharacterForm(false);
        loadNovelData();
      }
    } finally {
      setCreatingCharacter(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
        </div>
      </MainLayout>
    );
  }

  if (!novel) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          <h2 className="text-xl font-bold text-white mb-2">小说不存在</h2>
          <Button onClick={() => router.push('/novels')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回列表
          </Button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => router.push('/novels')}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <BookOpen className="w-6 h-6" />
                {novel.title}
              </h1>
              <p className="text-white/60 text-sm mt-1">
                {novel.genre} · {novel.status === 'draft' ? '草稿' : novel.status === 'writing' ? '创作中' : '已完成'}
              </p>
            </div>
          </div>
          
          {/* 快捷操作 */}
          <div className="flex gap-2">
            <Button variant="outline" className="border-violet-500/50">
              <Image className="w-4 h-4 mr-2" />
              生成封面
            </Button>
            <Link href={`/video-generation?novel_id=${novelId}`}>
              <Button className="bg-violet-600 hover:bg-violet-700">
                <Film className="w-4 h-4 mr-2" />
                开始视频
              </Button>
            </Link>
          </div>
        </div>

        {/* 标签页 */}
        <Tabs defaultValue="chapters" className="space-y-4">
          <TabsList className="bg-white/5">
            <TabsTrigger value="chapters" className="data-[state=active]:bg-violet-600">
              <FileText className="w-4 h-4 mr-2" />
              章节 ({chapters.length})
            </TabsTrigger>
            <TabsTrigger value="characters" className="data-[state=active]:bg-violet-600">
              <Users className="w-4 h-4 mr-2" />
              角色 ({characters.length})
            </TabsTrigger>
            <TabsTrigger value="scripts" className="data-[state=active]:bg-violet-600">
              <FileText className="w-4 h-4 mr-2" />
              剧本 ({scripts.length})
            </TabsTrigger>
            <TabsTrigger value="settings" className="data-[state=active]:bg-violet-600">
              <Settings className="w-4 h-4 mr-2" />
              设置
            </TabsTrigger>
          </TabsList>

          {/* 章节列表 */}
          <TabsContent value="chapters">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">章节管理</CardTitle>
                <Button size="sm" onClick={() => setShowChapterForm(!showChapterForm)}>
                  <Plus className="w-4 h-4 mr-2" />
                  新建章节
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 新建章节表单 */}
                {showChapterForm && (
                  <div className="p-4 bg-white/5 rounded-lg space-y-3">
                    <Input
                      placeholder="章节标题"
                      value={newChapterTitle}
                      onChange={(e) => setNewChapterTitle(e.target.value)}
                      className="bg-white/10 border-white/20 text-white"
                    />
                    <Textarea
                      placeholder="章节内容（可选，后续可编辑）"
                      value={newChapterContent}
                      onChange={(e) => setNewChapterContent(e.target.value)}
                      className="bg-white/10 border-white/20 text-white min-h-[100px]"
                    />
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        onClick={createChapter}
                        disabled={creatingChapter || !newChapterTitle.trim()}
                        className="bg-violet-600 hover:bg-violet-700"
                      >
                        {creatingChapter && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        创建
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        onClick={() => setShowChapterForm(false)}
                      >
                        取消
                      </Button>
                    </div>
                  </div>
                )}
                
                {/* 章节列表 */}
                {chapters.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无章节</p>
                    <p className="text-sm">点击"新建章节"开始创作</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {chapters.map((chapter, index) => (
                      <div
                        key={chapter.id}
                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-white/40 text-sm w-8">
                            {chapter.chapter_number || index + 1}
                          </span>
                          <div>
                            <div className="text-white font-medium">{chapter.title}</div>
                            <div className="text-white/40 text-sm">
                              {chapter.word_count || 0} 字 · {chapter.status || '草稿'}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="ghost">
                            <Edit2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 角色列表 */}
          <TabsContent value="characters">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">角色管理</CardTitle>
                <Button size="sm" onClick={() => setShowCharacterForm(!showCharacterForm)}>
                  <Plus className="w-4 h-4 mr-2" />
                  新建角色
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 新建角色表单 */}
                {showCharacterForm && (
                  <div className="p-4 bg-white/5 rounded-lg space-y-3">
                    <Input
                      placeholder="角色名称"
                      value={newCharacterName}
                      onChange={(e) => setNewCharacterName(e.target.value)}
                      className="bg-white/10 border-white/20 text-white"
                    />
                    <Textarea
                      placeholder="角色描述"
                      value={newCharacterDesc}
                      onChange={(e) => setNewCharacterDesc(e.target.value)}
                      className="bg-white/10 border-white/20 text-white min-h-[80px]"
                    />
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        onClick={createCharacter}
                        disabled={creatingCharacter || !newCharacterName.trim()}
                        className="bg-violet-600 hover:bg-violet-700"
                      >
                        {creatingCharacter && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        创建
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        onClick={() => setShowCharacterForm(false)}
                      >
                        取消
                      </Button>
                    </div>
                  </div>
                )}
                
                {/* 角色列表 */}
                {characters.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无角色</p>
                    <p className="text-sm">点击"新建角色"添加</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {characters.map((char) => (
                      <div
                        key={char.id}
                        className="p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div className="w-16 h-16 rounded-full bg-violet-500/20 flex items-center justify-center mx-auto mb-3">
                          <Users className="w-8 h-8 text-violet-400" />
                        </div>
                        <div className="text-center">
                          <div className="text-white font-medium">{char.name}</div>
                          <div className="text-white/40 text-sm truncate">
                            {char.description || '暂无描述'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 剧本列表 */}
          <TabsContent value="scripts">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">剧本管理</CardTitle>
                <Link href={`/scripts/new?novel_id=${novelId}`}>
                  <Button size="sm">
                    <Plus className="w-4 h-4 mr-2" />
                    新建剧本
                  </Button>
                </Link>
              </CardHeader>
              <CardContent>
                {scripts.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无剧本</p>
                    <p className="text-sm">从章节内容生成剧本</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {scripts.map((script) => (
                      <div
                        key={script.id}
                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div>
                          <div className="text-white font-medium">{script.title}</div>
                          <div className="text-white/40 text-sm">
                            {script.genre} · {script.status || '草稿'}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Link href={`/scripts/${script.id}`}>
                            <Button size="sm" variant="ghost">
                              <Eye className="w-4 h-4" />
                            </Button>
                          </Link>
                          <Button size="sm" variant="ghost">
                            <Sparkles className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 设置 */}
          <TabsContent value="settings">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white">小说设置</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-white/80 mb-2 block">小说标题</label>
                  <Input 
                    value={novel.title} 
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                <div>
                  <label className="text-white/80 mb-2 block">简介</label>
                  <Textarea 
                    value={novel.description || ''} 
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                <div>
                  <label className="text-white/80 mb-2 block">类型</label>
                  <Input 
                    value={novel.genre || ''} 
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                <Button className="bg-violet-600 hover:bg-violet-700">
                  保存修改
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* 底部快捷入口 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-violet-600/20 to-purple-600/20 border-violet-500/30">
            <CardContent className="p-4 text-center">
              <Film className="w-8 h-8 mx-auto mb-2 text-violet-400" />
              <div className="text-white font-medium">视频生成</div>
              <div className="text-white/60 text-sm">基于剧本生成视频</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-600/20 to-cyan-600/20 border-blue-500/30">
            <CardContent className="p-4 text-center">
              <Volume2 className="w-8 h-8 mx-auto mb-2 text-blue-400" />
              <div className="text-white font-medium">语音合成</div>
              <div className="text-white/60 text-sm">TTS语音生成</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-green-600/20 to-emerald-600/20 border-green-500/30">
            <CardContent className="p-4 text-center">
              <Play className="w-8 h-8 mx-auto mb-2 text-green-400" />
              <div className="text-white font-medium">音视频合成</div>
              <div className="text-white/60 text-sm">视频+音频合并</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-orange-600/20 to-amber-600/20 border-orange-500/30">
            <CardContent className="p-4 text-center">
              <Image className="w-8 h-8 mx-auto mb-2 text-orange-400" />
              <div className="text-white font-medium">封面生成</div>
              <div className="text-white/60 text-sm">AI生成小说封面</div>
            </CardContent>
          </Card>
        </div>
      </div>
    </MainLayout>
  );
}
