'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Copy,
  Eye,
  FileText,
  Loader2,
  Plus,
  Power,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
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
  deletePromptSkill,
  listPromptSkills,
  optimizePromptSkill,
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

type OptimizationResult = {
  task: string;
  source: 'ai_model' | 'local_rules';
  original_content: string;
  optimized_content: string;
  suggestions: string[];
  warnings: string[];
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
  const [optimizing, setOptimizing] = useState(false);
  const [optimization, setOptimization] = useState<OptimizationResult | null>(null);
  const [error, setError] = useState('');

  const selectedSkill = useMemo(
    () => skills.find((item) => item.id === selectedSkillId) || null,
    [selectedSkillId, skills]
  );

  const selectedTaskLabel = useMemo(
    () => taskOptions.find((item) => item.value === task)?.label || task,
    [task]
  );

  const canEdit = !(formMode === 'edit' && selectedSkill?.is_builtin);
  const canDelete = Boolean(selectedSkill && !selectedSkill.is_builtin && !selectedSkill.is_active);
  const deleteBlockReason = !selectedSkill
    ? '请选择一个技能后再删除'
    : selectedSkill.is_builtin
      ? '内置技能不能删除；可先克隆为自定义版本'
      : selectedSkill.is_active
        ? '当前激活技能正在使用；请先激活其它版本后再删除'
        : '';

  const contentVariables = useMemo(() => {
    return Array.from(new Set(Array.from(content.matchAll(/\{([^}]+)\}/g)).map((match) => match[1].trim()))).filter(Boolean);
  }, [content]);

  const boundaryChecks = useMemo(
    () => [
      { label: '技能名称不能为空', passed: Boolean(name.trim()) },
      { label: '技能内容不能为空', passed: Boolean(content.trim()) },
      { label: '建议包含禁止项或不得项', passed: /禁止|不得|不要|避免/.test(content) },
      { label: '预览优先使用当前草稿', passed: Boolean(content.trim()) && canEdit },
    ],
    [canEdit, content, name]
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
      } else if ((!selectedSkillId || !nextItems.some((item) => item.id === selectedSkillId)) && nextItems[0]) {
        setSelectedSkillId(nextItems[0].id);
        setFormMode('edit');
      } else if (!nextItems.length) {
        setSelectedSkillId('');
        setFormMode('create');
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
    setOptimization(null);
  }, [formMode, selectedSkill]);

  const resetForm = () => {
    setFormMode('create');
    setSelectedSkillId('');
    setName('');
    setDescription('');
    setContent('');
    setPreview('');
    setOptimization(null);
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

  const handleOptimize = async () => {
    if (!content.trim()) {
      toast({ title: '请先填写技能内容', type: 'error' });
      return;
    }
    if (!canEdit) {
      toast({ title: '内置技能请先克隆后优化', type: 'error' });
      return;
    }
    setOptimizing(true);
    setError('');
    try {
      const result = await optimizePromptSkill({
        task,
        name: name.trim(),
        description: description.trim(),
        content: content.trim(),
        mode: 'polish',
      });
      setOptimization(result);
      toast({ title: result.source === 'ai_model' ? 'AI 优化建议已生成' : '本地优化建议已生成', type: 'success' });
    } catch (err: any) {
      setError(err.message || 'AI 优化 Prompt 技能失败');
    } finally {
      setOptimizing(false);
    }
  };

  const applyOptimization = () => {
    if (!optimization) return;
    setContent(optimization.optimized_content);
    setPreview('');
    toast({ title: '已应用优化结果，可继续预览或保存', type: 'success' });
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

  const handleDelete = async () => {
    if (!selectedSkill) {
      toast({ title: '请先选择要删除的技能', type: 'error' });
      return;
    }
    if (!canDelete) {
      toast({ title: deleteBlockReason, type: 'error' });
      return;
    }
    const confirmed = window.confirm(`确定删除「${selectedSkill.name}」吗？此操作不可恢复。`);
    if (!confirmed) return;

    setSaving(true);
    setError('');
    try {
      await deletePromptSkill(selectedSkill.id);
      setPreview('');
      setOptimization(null);
      await loadSkills(task);
      toast({ title: '未发布 Prompt 技能已删除', type: 'success' });
    } catch (err: any) {
      setError(err.message || '删除 Prompt 技能失败');
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    const draftContent = content.trim();
    const useDraft = canEdit && Boolean(draftContent);
    const skillIds = !useDraft && selectedSkill?.id ? [selectedSkill.id] : [];
    if (!useDraft && !skillIds.length) {
      toast({ title: '请先选择技能或填写草稿内容', type: 'error' });
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await previewPromptSkill({
        task,
        skill_ids: skillIds,
        context: defaultContext,
        draft_name: useDraft ? name.trim() || '当前编辑草稿' : undefined,
        draft_content: useDraft ? draftContent : undefined,
        draft_stage: useDraft ? selectedSkill?.stage || 'draft' : undefined,
      });
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

        <div className="grid gap-3 rounded-lg border border-amber-400/25 bg-amber-400/10 p-3 text-sm leading-6 text-amber-50 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <span className="font-medium">当前任务：{selectedTaskLabel}</span>
            <span className="ml-2 text-amber-50/75">修改后先预览草稿，再保存并用测试验证模式跑完整流程。</span>
          </div>
          <div className="text-amber-50/75">示例上下文：tone=冷蓝月光，bad_case=脸型变化</div>
        </div>

        {error && <div className="rounded-lg border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-50">{error}</div>}

        <div className="grid gap-5 lg:grid-cols-[minmax(18rem,0.85fr)_minmax(0,1.15fr)]">
          <Card className="border-white/10 bg-white/5">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-white">技能列表</CardTitle>
                  <p className="mt-2 text-xs leading-5 text-white/45">选择任务后会显示可用技能。</p>
                </div>
                <Badge variant="outline" className="border-cyan-300/40 text-cyan-100">
                  {skills.length} 个
                </Badge>
              </div>
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
                      setPreview('');
                      setOptimization(null);
                    }}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${
                      selectedSkill?.id === skill.id
                        ? 'border-cyan-400/50 bg-cyan-500/10 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]'
                        : 'border-white/10 bg-black/20 hover:border-white/20 hover:bg-white/10'
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
                    <div className="mt-2 line-clamp-2 text-xs leading-5 text-white/55">
                      {skill.description || skill.content}
                    </div>
                    <div className="mt-3 flex items-center gap-2 text-[11px] text-white/35">
                      <span>{skill.stage || '未分阶段'}</span>
                      <span>·</span>
                      <span>{skill.content?.length || 0} 字符</span>
                    </div>
                  </button>
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-white/15 bg-black/20 p-6 text-center">
                  <FileText className="mx-auto mb-3 h-5 w-5 text-white/35" />
                  <div className="text-sm font-medium text-white">当前任务还没有 Prompt 技能</div>
                  <p className="mt-2 text-xs leading-5 text-white/45">可以先新建一个草稿，预览后再激活。</p>
                  <Button type="button" size="sm" className="mt-4 bg-cyan-600 hover:bg-cyan-700" onClick={resetForm}>
                    <Plus className="mr-2 h-4 w-4" />
                    新建技能
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-white/5">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-white">{formMode === 'edit' ? '编辑技能' : '新建技能'}</CardTitle>
                  <p className="mt-2 text-xs text-white/45">
                    {selectedSkill?.is_builtin ? '内置模板只读，克隆后可编辑。' : '当前草稿可直接预览注入效果。'}
                  </p>
                </div>
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
                disabled={!canEdit}
              />
              <Input
                aria-label="用途说明"
                className="border-white/10 bg-black/20 text-white placeholder:text-white/35"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="用途说明，可选"
                disabled={!canEdit}
              />
              <div className="overflow-hidden rounded-lg border border-white/10 bg-black/20">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-3 py-2 text-xs text-white/45">
                  <span>技能内容</span>
                  <span>
                    {content.length} 字符 · {content.split('\n').filter(Boolean).length || 0} 行 · {contentVariables.length} 个变量
                  </span>
                </div>
                <Textarea
                  aria-label="技能内容"
                  data-testid="prompt-skill-content-input"
                  value={content}
                  onChange={(event) => {
                    setContent(event.target.value);
                    setOptimization(null);
                  }}
                  placeholder="输入可复用的 Prompt 技能内容"
                  disabled={!canEdit}
                  className="min-h-[14rem] resize-y rounded-none border-0 bg-transparent font-mono text-sm leading-6"
                />
              </div>
              <div className="grid gap-3 rounded-lg border border-white/10 bg-black/20 p-3 md:grid-cols-2">
                <div>
                  <div className="mb-2 text-xs font-medium text-white/65">边界检查</div>
                  <div className="space-y-2">
                    {boundaryChecks.map((item) => (
                      <div key={item.label} className="flex items-center gap-2 text-xs text-white/55">
                        {item.passed ? (
                          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />
                        ) : (
                          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" />
                        )}
                        <span>{item.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mb-2 text-xs font-medium text-white/65">变量占位</div>
                  {contentVariables.length ? (
                    <div className="flex flex-wrap gap-2">
                      {contentVariables.map((variable) => (
                        <Badge key={variable} variant="outline" className="border-white/20 text-white/70">
                          {`{${variable}}`}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/45">
                      暂无变量占位
                    </div>
                  )}
                </div>
              </div>
              {formMode === 'edit' && selectedSkill?.is_builtin ? (
                <div className="rounded-lg border border-violet-300/20 bg-violet-400/10 p-3 text-sm leading-6 text-violet-50">
                  内置技能作为模板保留，克隆后可编辑、AI 优化、预览和激活。
                </div>
              ) : null}
              <div className="flex flex-col gap-2 xl:flex-row xl:flex-wrap">
                <Button
                  data-testid="prompt-skill-save"
                  className="bg-cyan-600 hover:bg-cyan-700"
                  onClick={handleSave}
                  disabled={saving || !canEdit}
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
                  data-testid="prompt-skill-optimize"
                  variant="outline"
                  className="border-emerald-300/30 text-emerald-50"
                  onClick={handleOptimize}
                  disabled={!canEdit || !content.trim() || optimizing}
                >
                  {optimizing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  AI 优化
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
                <Button
                  data-testid="prompt-skill-delete"
                  variant="outline"
                  className="border-red-300/30 text-red-100 hover:bg-red-500/10"
                  onClick={handleDelete}
                  disabled={!canDelete || saving}
                >
                  {saving && canDelete ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                  删除
                </Button>
              </div>
              {selectedSkill && !canDelete ? (
                <div className="flex items-start gap-2 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-xs leading-5 text-white/55">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
                  <span>删除限制：{deleteBlockReason}</span>
                </div>
              ) : null}
              {optimization ? (
                <div className="rounded-lg border border-emerald-300/20 bg-emerald-400/10 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm font-medium text-emerald-50">
                      <Sparkles className="h-4 w-4" />
                      优化结果
                      <Badge variant="outline" className="border-emerald-200/40 text-emerald-50">
                        {optimization.source === 'ai_model' ? 'AI 模型' : '本地规则'}
                      </Badge>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      data-testid="prompt-skill-apply-optimization"
                      className="bg-emerald-600 hover:bg-emerald-700"
                      onClick={applyOptimization}
                    >
                      应用优化结果
                    </Button>
                  </div>
                  <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-3 text-xs leading-5 text-white/75">
                    {optimization.optimized_content}
                  </pre>
                  {optimization.suggestions.length || optimization.warnings.length ? (
                    <div className="mt-3 grid gap-2 md:grid-cols-2">
                      <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                        <div className="mb-2 text-xs font-medium text-white/65">建议</div>
                        <ul className="space-y-1 text-xs leading-5 text-white/55">
                          {optimization.suggestions.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="rounded-lg border border-amber-300/20 bg-amber-400/10 p-3">
                        <div className="mb-2 text-xs font-medium text-amber-50">提示</div>
                        <ul className="space-y-1 text-xs leading-5 text-amber-50/75">
                          {optimization.warnings.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>

        <Card className="border-white/10 bg-white/5">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle className="text-white">预览结果</CardTitle>
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge variant="outline" className="border-white/20 text-white/60">
                  {canEdit ? '草稿优先' : '已保存技能'}
                </Badge>
                <Badge variant="outline" className="border-white/20 text-white/60">
                  {selectedTaskLabel}
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {preview ? (
              <pre
                data-testid="prompt-skill-preview-output"
                className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-4 text-sm leading-6 text-white/75"
              >
                {preview}
              </pre>
            ) : (
              <div
                data-testid="prompt-skill-preview-output"
                className="rounded-lg border border-dashed border-white/15 bg-black/20 p-8 text-center"
              >
                <Eye className="mx-auto mb-3 h-5 w-5 text-white/35" />
                <div className="text-sm font-medium text-white">暂无预览结果</div>
                <p className="mt-2 text-xs leading-5 text-white/45">
                  编辑草稿或选择技能后，可预览 Prompt 注入效果。
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
