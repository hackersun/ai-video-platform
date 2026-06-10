'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
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
  Settings,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/toast';
import {
  activatePromptSkill,
  bulkActionPromptSkills,
  clonePromptSkill,
  createPromptSkill,
  deletePromptSkill,
  getPromptSkillVariableGuide,
  listPromptSkillOptimizationModelConfigs,
  listPromptSkills,
  optimizePromptSkill,
  previewPromptSkill,
  updatePromptSkill,
  type PromptSkill,
  type PromptSkillVariableGuide,
} from '@/lib/prompt-skills-api';
import {
  getConfigsByCapability,
  getDefaultConfigForCapability,
  modelStatusClass,
  modelStatusLabel,
  type SavedModelConfig,
} from '@/lib/model-configs';

const taskOptions = [
  { value: 'novel_generation', label: '小说创建' },
  { value: 'chapter_writing', label: '章节创建' },
  { value: 'script_generation', label: '剧本创建' },
  { value: 'storyboard_generation', label: '分镜创建' },
  { value: 'entity_extraction', label: '实体/资产抽取' },
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
  const [selectedSkillIds, setSelectedSkillIds] = useState<Set<string>>(new Set());
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
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [selectedOptimizeModelConfigId, setSelectedOptimizeModelConfigId] = useState('');
  const [loadingModelConfigs, setLoadingModelConfigs] = useState(false);
  const [modelConfigError, setModelConfigError] = useState('');
  const [variableGuide, setVariableGuide] = useState<PromptSkillVariableGuide | null>(null);
  const [variableGuideError, setVariableGuideError] = useState('');

  const selectedSkill = useMemo(
    () => skills.find((item) => item.id === selectedSkillId) || null,
    [selectedSkillId, skills]
  );

  const selectedBulkSkillIds = useMemo(() => Array.from(selectedSkillIds), [selectedSkillIds]);

  const selectedTaskLabel = useMemo(
    () => taskOptions.find((item) => item.value === task)?.label || task,
    [task]
  );

  const textModelConfigs = useMemo(() => getConfigsByCapability(modelConfigs, 'text'), [modelConfigs]);
  const selectedOptimizeModelConfig = useMemo(
    () => textModelConfigs.find((config) => config.id === selectedOptimizeModelConfigId) || null,
    [selectedOptimizeModelConfigId, textModelConfigs]
  );
  const selectedOptimizeModelReady = Boolean(
    selectedOptimizeModelConfig?.test_status === 'success' && selectedOptimizeModelConfig.key_available !== false
  );
  const selectedOptimizeModelBlocked = Boolean(selectedOptimizeModelConfig && !selectedOptimizeModelReady);
  const selectedOptimizeModelStatus = selectedOptimizeModelConfig?.key_available === false
    ? 'Key 缺失'
    : modelStatusLabel(selectedOptimizeModelConfig?.test_status);
  const optimizeModelRepairMessage = useMemo(() => {
    if (modelConfigError) return modelConfigError;
    if (loadingModelConfigs) return '正在加载可用于提示词优化的文本模型配置。';
    if (!textModelConfigs.length) {
      return '还没有配置文本生成模型，本次可先使用本地规则生成结构化优化建议；生产使用前请配置并验证文本模型。';
    }
    if (!selectedOptimizeModelConfig) return '请选择一个文本模型后再使用 AI 优化。';
    if (selectedOptimizeModelConfig.key_available === false) {
      return selectedOptimizeModelConfig.test_message || '当前模型 API Key 不可用，请到大模型配置页重新填写并测试。';
    }
    if (selectedOptimizeModelConfig.test_status === 'failed') {
      return selectedOptimizeModelConfig.test_message || '当前模型验证失败，请到大模型配置页重新测试或切换可用模型。';
    }
    if (selectedOptimizeModelConfig.test_status !== 'success') {
      return '当前模型还未验证通过，请先完成模型测试，或切换到已验证文本模型。';
    }
    return '';
  }, [loadingModelConfigs, modelConfigError, selectedOptimizeModelConfig, textModelConfigs.length]);

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

  const variableGuideByName = useMemo(() => {
    return new Map((variableGuide?.items || []).map((item) => [item.name, item]));
  }, [variableGuide]);

  const previewContext = useMemo(
    () => ({
      ...(variableGuide?.sample_context || {}),
      ...(selectedSkill?.variables || {}),
    }),
    [selectedSkill, variableGuide]
  );

  const contextPreviewPairs = useMemo(() => Object.entries(previewContext).slice(0, 5), [previewContext]);

  const contentVariableDetails = useMemo(
    () =>
      contentVariables.map((variable) => {
        const guide = variableGuideByName.get(variable);
        const hasPreviewValue = Object.prototype.hasOwnProperty.call(previewContext, variable);
        return {
          name: variable,
          guide,
          hasPreviewValue,
          status: guide?.system_fill ? '系统可填' : guide ? '模板默认' : hasPreviewValue ? '技能默认' : '未知变量',
        };
      }),
    [contentVariables, previewContext, variableGuideByName]
  );

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
      setSelectedSkillIds((current) => {
        const availableIds = new Set(nextItems.map((item) => item.id));
        const next = new Set(Array.from(current).filter((id) => availableIds.has(id)));
        return next.size === current.size ? current : next;
      });
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

  const loadOptimizationModelConfigs = async () => {
    setLoadingModelConfigs(true);
    setModelConfigError('');
    try {
      const configs = await listPromptSkillOptimizationModelConfigs();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const defaultConfig = getDefaultConfigForCapability(list, 'text');
      setSelectedOptimizeModelConfigId((current) => {
        const textConfigs = getConfigsByCapability(list, 'text');
        if (current && textConfigs.some((config) => config.id === current)) return current;
        return defaultConfig?.id || '';
      });
    } catch (err: any) {
      setModelConfigError(err.message || '加载模型配置失败，可先使用本地规则优化；如需 AI 优化，请到大模型配置页检查配置。');
    } finally {
      setLoadingModelConfigs(false);
    }
  };

  const loadVariableGuide = async (nextTask = task) => {
    setVariableGuideError('');
    try {
      const guide = await getPromptSkillVariableGuide(nextTask);
      setVariableGuide(guide);
      return guide;
    } catch (err: any) {
      setVariableGuide(null);
      setVariableGuideError(err.message || '加载变量说明失败');
      return null;
    }
  };

  useEffect(() => {
    loadSkills(task);
    loadVariableGuide(task);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task]);

  useEffect(() => {
    loadOptimizationModelConfigs();
  }, []);

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
    setSelectedSkillIds(new Set());
    resetForm();
  };

  const summarizeBulkResult = (result: {
    updated_count?: number;
    deleted_count?: number;
    created_count?: number;
    skipped?: Array<{ id: string; reason: string; repair_action?: string | null }>;
    warnings?: string[];
  }) => {
    const changedCount = (result.created_count || 0) + (result.deleted_count || 0) + (result.updated_count || 0);
    const skipped = result.skipped || [];
    const warnings = result.warnings || [];
    const details = [
      changedCount ? `处理 ${changedCount} 项` : '',
      skipped.length ? `跳过 ${skipped.length} 项：${skipped.map((item) => item.reason).join('；')}` : '',
      warnings.length ? warnings.join('；') : '',
    ].filter(Boolean);
    return details.join('；');
  };

  const handleSelectSkillForBulk = (skillId: string) => {
    setSelectedSkillIds((current) => {
      const next = new Set(current);
      if (next.has(skillId)) {
        next.delete(skillId);
      } else {
        next.add(skillId);
      }
      return next;
    });
  };

  const parseTagsInput = (value: string) => value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);

  const handleBulkSkillAction = async (action: 'clone' | 'delete' | 'set_tags') => {
    if (!selectedBulkSkillIds.length) return;
    if (action === 'delete') {
      const confirmed = window.confirm(`确定批量删除已选择的 ${selectedBulkSkillIds.length} 个 Prompt 技能吗？内置或激活技能会由后端跳过并返回原因。`);
      if (!confirmed) return;
    }
    let tags: string[] | undefined;
    if (action === 'set_tags') {
      const raw = window.prompt('输入 Prompt 技能标签，多个标签用逗号分隔');
      if (raw === null) return;
      tags = parseTagsInput(raw);
      if (!tags.length) {
        toast({ title: '请至少输入一个标签', type: 'error' });
        return;
      }
    }
    setSaving(true);
    setError('');
    try {
      const result = await bulkActionPromptSkills({
        skill_ids: selectedBulkSkillIds,
        action,
        tags,
      });
      const skippedCount = result.skipped?.length || 0;
      toast({
        title:
          action === 'clone'
            ? '批量克隆已完成'
            : action === 'delete'
              ? '批量删除已完成'
              : '批量标记已完成',
        description: summarizeBulkResult(result) || undefined,
        type: skippedCount ? 'info' : 'success',
      });
      setSelectedSkillIds(new Set());
      await loadSkills(task);
    } catch (err: any) {
      setError(err.message || '批量维护 Prompt 技能失败');
    } finally {
      setSaving(false);
    }
  };

  const buildPayload = (isActive: boolean) => ({
    name: name.trim(),
    description: description.trim(),
    task,
    stage: selectedSkill?.stage || 'consistency',
    content: content.trim(),
    variables: contentVariables.reduce<Record<string, any>>((acc, variable) => {
      if (selectedSkill?.variables && Object.prototype.hasOwnProperty.call(selectedSkill.variables, variable)) {
        acc[variable] = selectedSkill.variables[variable];
      } else if (variableGuide?.sample_context && Object.prototype.hasOwnProperty.call(variableGuide.sample_context, variable)) {
        acc[variable] = variableGuide.sample_context[variable];
      }
      return acc;
    }, {}),
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
    if (selectedOptimizeModelBlocked) {
      toast({ title: '所选模型未验证通过，请先修复或切换模型', type: 'error' });
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
        model_config_id: selectedOptimizeModelConfig?.id || undefined,
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
        context: previewContext,
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
          <div className="text-amber-50/75">
            预览样例：
            {contextPreviewPairs.length
              ? contextPreviewPairs.map(([key, value]) => `${key}=${String(value).slice(0, 14)}`).join('，')
              : '等待变量说明加载'}
          </div>
        </div>

        <div className="rounded-lg border border-cyan-300/20 bg-cyan-400/10 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-cyan-50">
                <BrainCircuit className="h-4 w-4" />
                统一变量说明
              </div>
              <p className="mt-2 text-xs leading-5 text-cyan-50/70">
                使用 {`{变量名}`} 作为占位；真实生成和预览会优先使用系统上下文，其次使用技能变量默认值。未识别变量会保留为占位符，预览后再保存。
              </p>
            </div>
            <Badge variant="outline" className="w-fit border-cyan-200/40 text-cyan-50">
              {variableGuide?.task_label || selectedTaskLabel}变量
            </Badge>
          </div>
          {variableGuideError ? (
            <div className="mt-3 rounded-md border border-red-300/25 bg-red-500/10 p-3 text-xs text-red-50">
              {variableGuideError}
            </div>
          ) : null}
          <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(variableGuide?.items || []).slice(0, 12).map((item) => (
              <div key={item.name} className="rounded-md border border-white/10 bg-black/20 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-cyan-100">{`{${item.name}}`}</span>
                  <Badge
                    variant="outline"
                    className={item.system_fill ? 'border-emerald-300/40 text-emerald-100' : 'border-amber-300/40 text-amber-100'}
                  >
                    {item.system_fill ? '系统可填' : '模板默认'}
                  </Badge>
                </div>
                <div className="mt-1 text-xs font-medium text-white/75">{item.label}</div>
                <div className="mt-1 line-clamp-2 text-xs leading-5 text-white/45">{item.description}</div>
              </div>
            ))}
          </div>
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
              {selectedSkillIds.size > 0 ? (
                <div className="rounded-lg border border-cyan-300/25 bg-cyan-400/10 p-3">
                  <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                    <div className="text-sm font-medium text-cyan-50">已选择 {selectedSkillIds.size} 项</div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="border-white/20 text-white"
                        onClick={() => handleBulkSkillAction('clone')}
                        disabled={saving}
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        批量克隆
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="border-white/20 text-white"
                        onClick={() => handleBulkSkillAction('set_tags')}
                        disabled={saving}
                      >
                        <Sparkles className="mr-2 h-4 w-4" />
                        批量标签
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="border-red-300/30 text-red-100 hover:bg-red-500/10"
                        onClick={() => handleBulkSkillAction('delete')}
                        disabled={saving}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        批量删除
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="text-white/60 hover:text-white"
                        onClick={() => setSelectedSkillIds(new Set())}
                        disabled={saving}
                      >
                        清空
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
              {loading && !skills.length ? (
                <div className="rounded-lg border border-white/10 bg-black/20 p-6 text-center text-sm text-white/55">
                  <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
                  正在加载技能…
                </div>
              ) : null}
              {skills.length ? (
                skills.map((skill) => (
                  <div
                    key={skill.id}
                    role="button"
                    tabIndex={0}
                    data-testid={`prompt-skill-card-${skill.id}`}
                    onClick={() => {
                      setSelectedSkillId(skill.id);
                      setFormMode('edit');
                      setPreview('');
                      setOptimization(null);
                    }}
                    onKeyDown={(event) => {
                      if (event.key !== 'Enter' && event.key !== ' ') return;
                      event.preventDefault();
                      setSelectedSkillId(skill.id);
                      setFormMode('edit');
                      setPreview('');
                      setOptimization(null);
                    }}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${
                      selectedSkill?.id === skill.id
                        ? 'border-cyan-400/50 bg-cyan-500/10 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]'
                        : selectedSkillIds.has(skill.id)
                          ? 'border-violet-400/40 bg-violet-500/10'
                        : 'border-white/10 bg-black/20 hover:border-white/20 hover:bg-white/10'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-2">
                        <Checkbox
                          checked={selectedSkillIds.has(skill.id)}
                          onCheckedChange={() => handleSelectSkillForBulk(skill.id)}
                          onClick={(event) => event.stopPropagation()}
                          aria-label={`选择${skill.name}`}
                        />
                        <div className="min-w-0 truncate text-sm font-medium text-white">{skill.name}</div>
                      </div>
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
                  </div>
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
                  {contentVariableDetails.length ? (
                    <div className="space-y-2">
                      {contentVariableDetails.map((item) => (
                        <div key={item.name} className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              variant="outline"
                              className={
                                item.status === '系统可填'
                                  ? 'border-emerald-300/40 text-emerald-100'
                                  : item.status === '未知变量'
                                    ? 'border-red-300/40 text-red-100'
                                    : 'border-amber-300/40 text-amber-100'
                              }
                            >
                              {item.status}
                            </Badge>
                            <span className="font-mono text-xs text-white/75">{`{${item.name}}`}</span>
                            {item.guide ? <span className="text-xs text-white/45">{item.guide.label}</span> : null}
                          </div>
                          <div className="mt-1 text-xs leading-5 text-white/45">
                            {item.guide?.description || '当前任务变量说明中没有该占位；请确认是否需要补充默认值或改用系统变量。'}
                          </div>
                          {item.hasPreviewValue ? (
                            <div className="mt-1 truncate text-xs text-cyan-100/70">预览值：{String(previewContext[item.name])}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/45">
                      暂无变量占位
                    </div>
                  )}
                </div>
              </div>
              <div className="rounded-lg border border-emerald-300/20 bg-emerald-400/10 p-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-emerald-50">
                      <Sparkles className="h-4 w-4 shrink-0" />
                      <span>优化模型</span>
                      <Badge
                        variant="outline"
                        className={
                          selectedOptimizeModelConfig
                            ? modelStatusClass(selectedOptimizeModelConfig.test_status)
                            : 'border-amber-300/30 bg-amber-400/10 text-amber-50'
                        }
                      >
                        {selectedOptimizeModelConfig ? selectedOptimizeModelStatus : textModelConfigs.length ? '未选择' : '本地规则'}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-emerald-50/70">
                      选择用于润色 Prompt 技能的文本模型；未配置模型时可先用本地规则兜底，生产前建议完成模型验证。
                    </p>
                  </div>
                  <div className="w-full lg:w-80">
                    {textModelConfigs.length ? (
                      <Select
                        aria-label="优化模型"
                        data-testid="prompt-skill-optimize-model-select"
                        value={selectedOptimizeModelConfigId}
                        onChange={(event) => {
                          setSelectedOptimizeModelConfigId(event.target.value);
                          setOptimization(null);
                        }}
                        disabled={loadingModelConfigs}
                        options={textModelConfigs.map((config) => ({
                          value: config.id,
                          label: `${config.is_default ? '默认 · ' : ''}${config.name} · ${config.provider_name || config.provider_id} / ${config.model_name} · ${
                            config.key_available === false ? 'Key 缺失' : modelStatusLabel(config.test_status)
                          }`,
                        }))}
                      />
                    ) : (
                      <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-xs leading-5 text-white/60">
                        暂无文本模型配置
                      </div>
                    )}
                  </div>
                </div>
                {optimizeModelRepairMessage ? (
                  <div
                    className={`mt-3 flex flex-col gap-2 rounded-md border p-3 text-xs leading-5 sm:flex-row sm:items-center sm:justify-between ${
                      selectedOptimizeModelBlocked || modelConfigError
                        ? 'border-red-300/25 bg-red-500/10 text-red-50'
                        : 'border-amber-300/25 bg-amber-400/10 text-amber-50'
                    }`}
                  >
                    <span>{optimizeModelRepairMessage}</span>
                    <Link
                      href="/llm-config"
                      className="inline-flex shrink-0 items-center justify-center gap-1 rounded-md border border-white/20 px-2.5 py-1.5 text-white hover:bg-white/10"
                    >
                      <Settings className="h-3.5 w-3.5" />
                      去配置模型
                    </Link>
                  </div>
                ) : null}
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
                  disabled={!canEdit || !content.trim() || optimizing || selectedOptimizeModelBlocked}
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
