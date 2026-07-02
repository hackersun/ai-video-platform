'use client';

import { useState } from 'react';
import { Image as ImageIcon, Maximize2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface ReferenceImagePreviewProps {
  src?: string | null;
  title?: string;
  alt?: string;
  caption?: string;
  emptyText?: string;
  className?: string;
  thumbnailClassName?: string;
}

export function ReferenceImagePreview({
  src,
  title = '参考图',
  alt = '参考图',
  caption,
  emptyText = '暂无参考图',
  className = '',
  thumbnailClassName = '',
}: ReferenceImagePreviewProps) {
  const [open, setOpen] = useState(false);

  if (!src) {
    return (
      <div className={`flex min-h-24 items-center justify-center rounded-lg border border-dashed border-white/10 bg-white/[0.03] text-sm text-white/40 ${className}`}>
        <ImageIcon className="mr-2 h-4 w-4" />
        {emptyText}
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen(true);
        }}
        className={`group relative block overflow-hidden rounded-lg border border-white/10 bg-black/30 text-left transition hover:border-cyan-400/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${className}`}
        title="点击查看完整大图"
      >
        <img
          src={src}
          alt={alt}
          loading="lazy"
          className={`h-full w-full object-contain ${thumbnailClassName}`}
        />
        <span className="absolute bottom-2 right-2 inline-flex items-center rounded bg-black/70 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
          <Maximize2 className="mr-1 h-3 w-3" />
          查看大图
        </span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto border-white/20 bg-slate-950/95">
          <DialogHeader className="pr-10">
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="rounded-lg border border-white/10 bg-black/40 p-2">
            <img
              src={src}
              alt={alt}
              className="mx-auto max-h-[76vh] w-auto max-w-full object-contain"
            />
          </div>
          {caption && <p className="text-sm text-white/60">{caption}</p>}
        </DialogContent>
      </Dialog>
    </>
  );
}
