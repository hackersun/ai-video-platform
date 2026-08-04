'use client';

import { FormEvent, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

import type { ModelConnectionView } from '../types';
import { connectionDisplayName } from '../model-center-labels';

type RemoveConnectionDialogProps = {
  connection: ModelConnectionView;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
};

export function RemoveConnectionDialog({ connection, onClose, onConfirm }: RemoveConnectionDialogProps) {
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const name = connectionDisplayName(connection.name, connection.provider_name);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '账号移除失败');
    } finally {
      setPending(false);
    }
  };

  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-4">
    <form role="dialog" aria-modal="true" aria-label="移除供应商账号" onSubmit={submit} className="w-full max-w-lg rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl">
      <header className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-semibold text-white">移除供应商账号</h2><p className="mt-1 text-sm text-slate-400">{name} · {connection.provider_name}</p></div><button type="button" aria-label="关闭移除账号对话框" disabled={pending} onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button></header>
      <div className="mt-4 flex gap-3 rounded-lg border border-amber-400/20 bg-amber-500/[0.07] p-3 text-sm text-amber-100"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div><p className="font-medium">密钥会被清除，历史测试与任务记录仍会保留。</p><p className="mt-1 text-xs leading-5 text-amber-200/75">如果账号正在被默认模型使用，系统会阻止移除并提示先更换默认模型。</p></div></div>
      <label className="mt-4 block text-xs text-slate-400">移除说明<input aria-label="移除说明" required minLength={2} maxLength={200} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="例如：停用旧生产账号" className="model-center-input mt-1 w-full" /></label>
      {error && <p className="mt-3 rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-100">{error}</p>}
      <footer className="mt-5 flex justify-end gap-2"><button type="button" disabled={pending} onClick={onClose} className="model-center-quiet whitespace-nowrap">取消</button><button type="submit" disabled={pending || reason.trim().length < 2} className="inline-flex items-center justify-center rounded-md bg-rose-500 px-3 py-2 text-sm font-medium text-white transition hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-50">{pending ? '移除中' : '确认移除'}</button></footer>
    </form>
  </div>;
}
