'use client';

import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { StudioGuidedAction } from '@/lib/studio-types';

export function StudioActionConfirmationDialog({
  action,
  open,
  loading,
  onOpenChange,
  onConfirm,
}: {
  action: StudioGuidedAction | null;
  open: boolean;
  loading?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  const confirmation = action?.confirmation;
  const impact = confirmation?.impact || action?.expected_outputs || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg border border-amber-300/25 bg-amber-400/10 text-amber-100">
            <AlertTriangle className="h-5 w-5" aria-hidden />
          </div>
          <DialogTitle>{confirmation?.title || action?.label || '确认执行操作'}</DialogTitle>
          <DialogDescription>
            {confirmation?.description || action?.reason || action?.description || '该操作会改变当前工作流状态，请确认后继续。'}
          </DialogDescription>
        </DialogHeader>

        {impact.length ? (
          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
            <div className="text-xs font-medium text-white/50">预计影响</div>
            <div className="mt-2 grid gap-2">
              {impact.map((item) => (
                <div key={item} className="flex min-w-0 items-start gap-2 text-sm leading-6 text-white/75">
                  <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-cyan-300" aria-hidden />
                  <span className="min-w-0 break-words">{item}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {action?.scope?.length ? (
          <div className="text-xs leading-5 text-white/45">范围：{action.scope.join('、')}</div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" disabled={loading} onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button type="button" disabled={loading || !action} onClick={onConfirm}>
            {loading ? '执行中' : confirmation?.confirm_label || '确认执行'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
