'use client';

import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-white/10',
        className
      )}
    />
  );
}

// Dashboard加载骨架屏
export function DashboardSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* 欢迎区域 */}
      <div className="flex items-center justify-between">
        <div>
          <div className="h-10 w-64 bg-white/10 rounded-lg mb-2" />
          <div className="h-5 w-48 bg-white/10 rounded" />
        </div>
        <div className="h-10 w-32 bg-white/10 rounded-lg" />
      </div>

      {/* 时间线 */}
      <div className="h-32 bg-white/5 rounded-xl" />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 bg-white/5 rounded-lg" />
        ))}
      </div>

      {/* 作品列表骨架 */}
      <div>
        <div className="h-6 w-32 bg-white/10 rounded mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 bg-white/5 rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}

// 卡片列表骨架屏
export function CardListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-20 bg-white/5 rounded-lg" />
      ))}
    </div>
  );
}

// 表格骨架屏
export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3">
      {/* 表头 */}
      <div className="flex gap-4 pb-2 border-b border-white/10">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-4 bg-white/10 rounded flex-1" />
        ))}
      </div>
      {/* 行 */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: cols }).map((_, j) => (
            <div key={j} className="h-4 bg-white/5 rounded flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}
