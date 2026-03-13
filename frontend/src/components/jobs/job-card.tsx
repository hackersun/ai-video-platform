'use client';

import { 
  FileVideo, 
  Mic, 
  User, 
  FileText, 
  Play, 
  RotateCcw, 
  Trash2, 
  X,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  Ban
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Job, JobType, JobStatus } from '@/types/job';

interface JobCardProps {
  job: Job;
  onCancel?: (id: string) => void;
  onRetry?: (id: string) => void;
  onDelete?: (id: string) => void;
  onViewDetails?: (job: Job) => void;
  isCancelling?: boolean;
  isRetrying?: boolean;
  isDeleting?: boolean;
}

const typeIcons: Record<JobType, React.ReactNode> = {
  video_generation: <FileVideo className="w-5 h-5" />,
  tts_generation: <Mic className="w-5 h-5" />,
  avatar_generation: <User className="w-5 h-5" />,
  script_generation: <FileText className="w-5 h-5" />,
};

const typeColors: Record<JobType, string> = {
  video_generation: 'from-cyan-500 to-blue-500',
  tts_generation: 'from-emerald-500 to-teal-500',
  avatar_generation: 'from-pink-500 to-rose-500',
  script_generation: 'from-amber-500 to-orange-500',
};

const typeLabels: Record<JobType, string> = {
  video_generation: '视频生成',
  tts_generation: '语音合成',
  avatar_generation: '角色生成',
  script_generation: '剧本生成',
};

const statusConfig: Record<JobStatus, { icon: React.ReactNode; color: string; label: string }> = {
  pending: { icon: <Clock className="w-3.5 h-3.5" />, color: 'bg-yellow-500/20 text-yellow-400', label: '等待中' },
  processing: { icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />, color: 'bg-blue-500/20 text-blue-400', label: '处理中' },
  completed: { icon: <CheckCircle2 className="w-3.5 h-3.5" />, color: 'bg-green-500/20 text-green-400', label: '已完成' },
  failed: { icon: <AlertCircle className="w-3.5 h-3.5" />, color: 'bg-red-500/20 text-red-400', label: '失败' },
  cancelled: { icon: <Ban className="w-3.5 h-3.5" />, color: 'bg-gray-500/20 text-gray-400', label: '已取消' },
};

export function JobCard({
  job,
  onCancel,
  onRetry,
  onDelete,
  onViewDetails,
  isCancelling,
  isRetrying,
  isDeleting,
}: JobCardProps) {
  const status = statusConfig[job.status];
  const typeColor = typeColors[job.type];
  const typeIcon = typeIcons[job.type];
  const typeLabel = typeLabels[job.type];

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const canCancel = job.status === 'pending' || job.status === 'processing';
  const canRetry = job.status === 'failed' || job.status === 'cancelled';
  const canDelete = job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled';

  return (
    <div className="group relative p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] hover:border-white/15 transition-all">
      <div className="flex items-start gap-4">
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${typeColor} flex items-center justify-center text-white shrink-0`}>
          {typeIcon}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-white font-medium truncate">
              {job.title || typeLabel}
            </h3>
            <span className={`px-2 py-0.5 rounded text-xs flex items-center gap-1 ${status.color}`}>
              {status.icon}
              {status.label}
            </span>
          </div>
          
          {job.description && (
            <p className="text-white/40 text-sm truncate mb-2">
              {job.description}
            </p>
          )}
          
          <div className="flex items-center gap-4 text-xs text-white/40 mb-3">
            <span>{formatDate(job.created_at)}</span>
            <span>{typeLabel}</span>
          </div>
          
          {(job.status === 'processing' || job.status === 'pending') && (
            <div className="relative h-1.5 bg-white/10 rounded-full overflow-hidden mb-3">
              <div 
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all duration-500"
                style={{ width: `${job.progress}%` }}
              />
            </div>
          )}
          
          {job.status === 'processing' && (
            <div className="text-xs text-white/40 mb-3">
              进度: {job.progress}%
            </div>
          )}
          
          {job.error && job.status === 'failed' && (
            <div className="text-xs text-red-400 mb-3 p-2 rounded bg-red-500/10">
              {job.error}
            </div>
          )}
          
          <div className="flex items-center gap-2">
            {canCancel && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onCancel?.(job.id)}
                disabled={isCancelling}
                className="text-white/60 hover:text-white"
              >
                {isCancelling ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <X className="w-3.5 h-3.5 mr-1" />
                )}
                取消
              </Button>
            )}
            
            {canRetry && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRetry?.(job.id)}
                disabled={isRetrying}
                className="text-white/60 hover:text-white"
              >
                {isRetrying ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="w-3.5 h-3.5 mr-1" />
                )}
                重试
              </Button>
            )}
            
            {canDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete?.(job.id)}
                disabled={isDeleting}
                className="text-white/60 hover:text-red-400"
              >
                {isDeleting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5 mr-1" />
                )}
                删除
              </Button>
            )}
            
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onViewDetails?.(job)}
              className="text-white/60 hover:text-white ml-auto"
            >
              查看详情
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}