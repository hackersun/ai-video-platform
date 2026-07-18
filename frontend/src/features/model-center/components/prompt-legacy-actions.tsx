'use client';

import { Copy, Power, Trash2 } from 'lucide-react';
import { useState } from 'react';

import {
  activatePromptSkill,
  clonePromptSkill,
  deletePromptSkill,
} from '@/lib/prompt-skills-api';
import type { PromptProfileDetail } from '../types';

export function PromptLegacyActions({
  detail,
  onChanged,
}: {
  detail: PromptProfileDetail;
  onChanged: () => Promise<void>;
}) {
  const skill = detail.legacy_skill;
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  if (!skill) return <p className="rounded-md border border-white/10 px-3 py-2 text-xs text-slate-500">这是原生规范模板，没有旧 PromptSkill 兼容操作。</p>;
  const run = async (kind: 'clone' | 'activate' | 'delete') => {
    if (kind === 'delete' && !window.confirm('删除此停用提示词？已发布历史仍受保护。')) return;
    try {
      setPending(kind); setMessage(null);
      if (kind === 'clone') await clonePromptSkill(skill.id);
      if (kind === 'activate') await activatePromptSkill(skill.id);
      if (kind === 'delete') await deletePromptSkill(skill.id);
      setMessage(kind === 'clone' ? '已克隆为新的停用草稿。' : kind === 'activate' ? '提示词已激活。' : '停用提示词已删除。');
      await onChanged();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : '快捷维护失败');
    } finally { setPending(null); }
  };
  return <section className="rounded-lg border border-white/10 bg-black/10 p-4"><h3 className="text-sm font-semibold text-white">兼容维护</h3><p className="mt-1 text-xs text-slate-500">复用原有克隆、激活和安全删除能力；内置或正在使用的版本不会被直接删除。</p><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => void run('clone')} disabled={pending !== null} className="model-center-quiet"><Copy className="h-3.5 w-3.5" />克隆技能</button><button type="button" onClick={() => void run('activate')} disabled={pending !== null || skill.is_builtin || skill.is_active} className="model-center-quiet"><Power className="h-3.5 w-3.5" />激活此版本</button><button type="button" onClick={() => void run('delete')} disabled={pending !== null || skill.is_builtin || skill.is_active} className="model-center-quiet text-rose-200"><Trash2 className="h-3.5 w-3.5" />删除技能</button></div>{message && <p className="mt-3 text-xs text-amber-100">{message}</p>}</section>;
}
