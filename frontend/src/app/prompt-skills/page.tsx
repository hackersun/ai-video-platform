'use client';

import { useEffect, useMemo, useState } from 'react';
import { BrainCircuit, Copy, Eye, Loader2, Plus, Power, Save } from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import {
  activatePromptSkill,
  clonePromptSkill,
  createPromptSkill,
  listPromptSkills,
  previewPromptSkill,
  updatePromptSkill,
  type PromptSkill,
} from '@/lib/prompt-skills-api';

const taskOptions = [
  { value: 'novel_generation', label: '小说创建' },
  { value: 'chapter_writing', label: '章节创建' },
  { value: 'script_generation', label: '剧本创建' },
  { value: 'storyboard_generation', label: '分镜创建' },
  { value: 'shot_prompt', label: '镜头创建' },
  { value: 'shot_video', label: '镜头视频' },
  { value: 'character_image', label: '头像/角色图' },
  { value: 'scene_reference_image', label: '场景图' },
  { value: 'prop_image', label: '道具图' },
  { value: 'novel_cover', label: '封面图' },
  { value: 'tts_dialogue', label: '角色配音' },
  { value: 'shot_audio_video', label: '音视频直生' },
  { value: 'consistency_review', label: '一致性审查' },
  { value: 'repair_suggestion', label: '返修建议' },
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
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [content, setContent] = useState('');
  const [preview, setPreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const selectedSkill = useMemo(
    () => skills.find((item) => item.id === selectedSkillId) || null,
    [selectedSkillId, skills]
  );

  const loadSkills = async (nextTask = task, nextSelectedId?: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await listPromptSkills(nextTask);
      const nextItems = data.items || [];
      setSkills(nextItems);
      if (nextSelectedId) {
        setSelectedSkillId(nextSelectedId);
        setFormMode('edit');
      } else if (!selectedSkillId && nextItems[0]) {
        setSelectedSkillId(nextItems[0].id);
        setFormMode('edit');
      }
      return nextItems;
    } catch (err: any) {
      setError(err.message || '加载 Prompt 技能失败');
      return [];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSkills(task);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task]);

  useEffect(() => {
    if (formMode !== 'edit' || !selectedSkill) return;
    setName(selectedSkill.name || '');
    setDescription(selectedSkill.description || '');
    setContent(selectedSkill.content || '');
  }, [formMode, selectedSkill]);

  const resetForm = () => {
    setFormMode('create');
    setSelectedSkillId('');
    setName('');
    setDescription('');
    setContent('');
    setPreview('');
  };

  const handleTaskChange = (nextTask: string) => {
    setTask(nextTask);
    resetForm();
  };

  const buildPayload = (isActive: boolean) => ({
    name: name.trim(),
    description: description.trim(),
    task,
    stage: selectedSkill?.stage || 'consistency',
    content: content.trim(),
    variables: selectedSkill?.variables || {},
    priority: selectedSkill?.priority ?? 100,
    inject_position: selectedSkill?.inject_position || 'before_constraints',
    is_active: isActive,
    tags: selectedSkill?.tags || [],
  });

  const handleSave = async () => {
    if (!name.trim() || !content.trim()) {
      toast({ title: '请补齐技能名称和内容', type: 'error' });
      return;
    }
    if (formMode === 'edit' && selectedSkill?.is_builtin) {
      toast({ title: '内置技能不能直接修改，请先克隆', type: 'error' });
      return;
    }
    setSaving(true);
    setError('');
    try {
      if (formMode === 'edit' && selectedSkill) {
        const updated = await updatePromptSkill(selectedSkill.id, buildPayload(Boolean(selectedSkill.is_active)));
        await loadSkills(task, updated.id);
        toast({ title: 'Prompt 技能已更新', type: 'success' });
      } else {
        const created = await createPromptSkill(buildPayload(true));
        await loadSkills(task, created.id);
        toast({ title: 'Prompt 技能已保存并激活', type: 'success' });
      }
    } catch (err: any) {
      setError(err.message || '保存 Prompt 技能失败');
    } finally {
      setSaving(false);
    }
  };

  const handleClone = async () => {
    if (!selectedSkill) {
      toast({ title: '请先选择要克隆的技能', type: 'error' });
      return;
    }
    setSaving(true);
    setError('');
    try {
      const cloned = await clonePromptSkill(selectedSkill.id);
      await loadSkills(task, cloned.id);
      toast({ title: '已克隆为未激活版本，可先编辑和预览', type: 'success' });
    } catch (err: any) {
      setError(err.message || '克隆 Prompt 技能失败');
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async () => {
    if (!selectedSkill) {
      toast({ title: '请先选择要激活的技能', type: 'error' });
      return;
    }
    if (selectedSkill.is_builtin) {
      toast({ title: '内置技能请先克隆后激活', type: 'error' });
      return;
    }
    setSaving(true);
    setError('');
    try {
      const activated = await activatePromptSkill(selectedSkill.id);
      await loadSkills(task, activated.id);
      toast({ title: '已切换当前激活 Prompt 技能', type: 'success' });
    } catch (err: any) {
      setError(err.message || '激活 Prompt 技能失败');
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
            <Select
              aria-label="任务类型"
              data-testid="prompt-skill-task-select"
              value={task}
              onChange={(event) => handleTaskChange(event.target.value)}
              options={taskOptions}
            />
          </div>
        </div>

        <div className="rounded-lg border border-amber-400/25 bg-amber-400/10 p-3 text-sm leading-6 text-amber-50">
          Prompt 技能会影响生成质量。修改后建议先用测试验证模式跑完整流程。
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
                    data-testid={`prompt-skill-card-${skill.id}`}
                    onClick={() => {
                      setSelectedSkillId(skill.id);
                      setFormMode('edit');
                    }}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${
                      selectedSkill?.id === skill.id
                        ? 'border-cyan-400/40 bg-cyan-500/10'
                        : 'border-white/10 bg-black/20 hover:bg-white/10'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0 truncate text-sm font-medium text-white">{skill.name}</div>
                      <div className="flex shrink-0 items-center gap-1">
                        {skill.is_active ? (
                          <Badge variant="outline" className="border-emerald-300/70 text-emerald-100">
                            当前激活
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-white/30 text-white/60">
                            未激活
                          </Badge>
                        )}
                        {skill.is_builtin ? (
                          <Badge variant="outline" className="border-violet-300/70 text-violet-100">
                            内置
                          </Badge>
                        ) : null}
                        <Badge variant="outline" className="border-current text-current">
                          v{skill.version || 1}
                        </Badge>
                      </div>
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
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-white">{formMode === 'edit' ? '编辑技能' : '新建技能'}</CardTitle>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-white/20 text-white"
                  onClick={resetForm}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  新建
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                aria-label="技能名称"
                data-testid="prompt-skill-name-input"
                className="border-white/10 bg-black/20 text-white placeholder:text-white/35"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：面部一致性"
                disabled={formMode === 'edit' && selectedSkill?.is_builtin}
              />
              <Input
                aria-label="用途说明"
                className="border-white/10 bg-black/20 text-white placeholder:text-white/35"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="用途说明，可选"
                disabled={formMode === 'edit' && selectedSkill?.is_builtin}
              />
              <Textarea
                aria-label="技能内容"
                data-testid="prompt-skill-content-input"
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="输入可复用的 Prompt 技能内容"
                disabled={formMode === 'edit' && selectedSkill?.is_builtin}
              />
              {formMode === 'edit' && selectedSkill?.is_builtin ? (
                <div className="rounded-lg border border-violet-300/20 bg-violet-400/10 p-3 text-sm leading-6 text-violet-50">
                  内置技能作为模板保留，克隆后可编辑、预览和激活。
                </div>
              ) : null}
              <div className="flex flex-col gap-2 xl:flex-row xl:flex-wrap">
                <Button
                  data-testid="prompt-skill-save"
                  className="bg-cyan-600 hover:bg-cyan-700"
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  {formMode === 'edit' ? '保存修改' : '保存技能'}
                </Button>
                <Button
                  data-testid="prompt-skill-clone"
                  variant="outline"
                  className="border-white/20 text-white"
                  onClick={handleClone}
                  disabled={!selectedSkill || saving}
                >
                  <Copy className="mr-2 h-4 w-4" />
                  克隆技能
                </Button>
                <Button
                  variant="outline"
                  data-testid="prompt-skill-activate"
                  className="border-white/20 text-white"
                  onClick={handleActivate}
                  disabled={!selectedSkill || Boolean(selectedSkill.is_active) || Boolean(selectedSkill.is_builtin) || saving}
                >
                  <Power className="mr-2 h-4 w-4" />
                  {selectedSkill?.is_active ? '已激活' : '设为当前激活'}
                </Button>
                <Button
                  data-testid="prompt-skill-preview"
                  variant="outline"
                  className="border-white/20 text-white"
                  onClick={handlePreview}
                  disabled={loading}
                >
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
            <pre
              data-testid="prompt-skill-preview-output"
              className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-4 text-sm leading-6 text-white/75"
            >
              {preview || '选择或保存技能后，可在这里查看最终 Prompt 片段如何注入生成上下文。'}
            </pre>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
