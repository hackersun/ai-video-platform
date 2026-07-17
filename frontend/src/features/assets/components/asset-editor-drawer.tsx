'use client';

import { useEffect, type ReactNode } from 'react';
import { Boxes, Loader2, Save, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

type Props = {
  title: '编辑资产' | '新建资产';
  saving: boolean;
  children: ReactNode;
  onClose: () => void;
  onSave: () => void;
};

export function AssetEditorDrawer({ title, saving, children, onClose, onSave }: Props) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, saving]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/65 backdrop-blur-sm">
      <button type="button" aria-label="关闭资产编辑器" className="min-w-0 flex-1 cursor-default" onClick={onClose} />
      <aside role="dialog" aria-label={title} aria-modal="true" className="flex h-full w-full max-w-2xl flex-col border-l border-white/15 bg-slate-950 shadow-2xl shadow-black/50">
        <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div><div className="flex items-center gap-2 text-lg font-semibold text-white"><Boxes className="h-5 w-5 text-violet-300" />{title}</div><div className="mt-1 text-xs text-white/45">修改当前资产，不会改变其他版本或制片对象。</div></div>
          <Button type="button" variant="ghost" size="icon" aria-label="关闭" className="text-white/60" onClick={onClose}><X className="h-4 w-4" /></Button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
        <footer className="flex justify-end gap-2 border-t border-white/10 bg-slate-950 px-5 py-4">
          <Button type="button" variant="outline" className="border-white/20 text-white" disabled={saving} onClick={onClose}>取消</Button>
          <Button type="button" className="bg-violet-600 hover:bg-violet-700" disabled={saving} onClick={onSave}>{saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}保存资产</Button>
        </footer>
      </aside>
    </div>
  );
}
