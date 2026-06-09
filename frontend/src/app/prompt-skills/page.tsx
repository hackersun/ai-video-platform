'use client';

import { useEffect, useMemo, useState } from 'react';
import { BrainCircuit, Eye, Loader2, Save } from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import { createPromptSkill, listPromptSkills, previewPromptSkill, type PromptSkill } from '@/lib/prompt-skills-api';

const taskOptions = [
  { value: 'shot_video', label: '镜头视频' },
  { value: 'character_image', label: '角色定稿图' },
  { value: 'storyboard', label: '分镜生成' },
  { value: 'tts_dialogue', label: '对白配音' },
];

const defaultContext = {
  tone: '冷蓝月光',
  bad_case: '脸型变化',
};

export default function PromptSkillsPage() {
  const { toast } = useToast();
  const [task, setTask] = useState('shot_video');
  const [skills, setSkills] = useState<PromptSkill[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [content, setContent] = useState('');
  const [preview, setPreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const selectedSkill = useMemo(
    () => skills.find((item) => item.id === selectedSkillId) || skills[0],
    [selectedSkillId, skills]
  );

  const loadSkills = async (nextTask = task) => {
    setLoading(true);
    setError('');
    try {
      const data = await listPromptSkills(nextTask);
      setSkills(data.items || []);
      if (!selectedSkillId && data.items?.[0]) setSelectedSkillId(data.items[0].id);
    } catch (err: any) {
      setError(err.message || '加载 Prompt 技能失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSkills(task);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task]);

  const handleSave = async () => {
    if (!name.trim() || !content.trim()) {
      toast({ title: '请补齐技能名称和内容', type: 'error' });
      return;
    }
    setSaving(true);
    setError('');
    try {
      const created = await createPromptSkill({
        name: name.trim(),
        description: description.trim(),
        task,
        stage: 'consistency',
        content: content.trim(),
        variables: {},
        priority: 100,
        inject_position: 'before_constraints',
        is_active: true,
        tags: [],
      });
      setSelectedSkillId(created.id);
      setName('');
      setDescription('');
      setContent('');
      await loadSkills(task);
      toast({ title: 'Prompt 技能已保存', type: 'success' });
    } catch (err: any) {
      setError(err.message || '保存 Prompt 技能失败');
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    const skillIds = selectedSkill?.id ? [selectedSkill.id] : [];
    setLoading(true);
    setError('');
    try {
      const result = await previewPromptSkill({ task, skill_ids: skillIds, context: defaultContext });
      setPreview(result.prompt);
    } catch (err: any) {
      setError(err.message || '预览 Prompt 失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-cyan-200">
              <BrainCircuit className="h-4 w-4" />
              Prompt 技能
            </div>
            <h1 className="mt-2 text-2xl font-semibold text-white">Prompt 技能</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/55">
              给不同生成任务配置可复用提示词片段，先预览再保存，避免把临时写法散落到各个生成入口。
            </p>
          </div>
          <div className="w-full lg:w-72">
            <Select value={task} onChange={(event) => setTask(event.target.value)} options={taskOptions} />
          </div>
        </div>

        {error && <div className="rounded-lg border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-50">{error}</div>}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <Card className="border-white/10 bg-white/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-white">技能列表</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {loading && !skills.length ? (
                <div className="rounded-lg border border-white/10 bg-black/20 p-6 text-center text-sm text-white/55">
                  <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
                  正在加载技能…
                </div>
              ) : null}
              {skills.length ? (
                skills.map((skill) => (
                  <button
                    key={skill.id}
                    type="button"
                    onClick={() => setSelectedSkillId(skill.id)}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${
                      selectedSkill?.id === skill.id
                        ? 'border-cyan-400/40 bg-cyan-500/10'
                        : 'border-white/10 bg-black/20 hover:bg-white/10'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0 truncate text-sm font-medium text-white">{skill.name}</div>
                      <Badge variant="outline" className="shrink-0 border-current text-current">
                        v{skill.version || 1}
                      </Badge>
                    </div>
                    <div className="mt-1 line-clamp-2 text-xs leading-5 text-white/50">
                      {skill.description || skill.content}
                    </div>
                  </button>
                ))
              ) : (
                <div className="rounded-lg border border-white/10 bg-black/20 p-6 text-center text-sm text-white/50">
                  当前任务还没有 Prompt 技能。
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-white/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-white">新建技能</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                className="border-white/10 bg-black/20 text-white placeholder:text-white/35"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：面部一致性"
              />
              <Input
                className="border-white/10 bg-black/20 text-white placeholder:text-white/35"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="用途说明，可选"
              />
              <Textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="输入可复用的 Prompt 技能内容"
              />
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button className="bg-cyan-600 hover:bg-cyan-700" onClick={handleSave} disabled={saving}>
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  保存技能
                </Button>
                <Button variant="outline" className="border-white/20 text-white" onClick={handlePreview} disabled={loading}>
                  <Eye className="mr-2 h-4 w-4" />
                  预览 Prompt
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="border-white/10 bg-white/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-white">预览结果</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-4 text-sm leading-6 text-white/75">
              {preview || '选择或保存技能后，可在这里查看最终 Prompt 片段如何注入生成上下文。'}
            </pre>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
