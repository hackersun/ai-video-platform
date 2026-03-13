'use client';

import { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { 
  GripVertical, 
  Trash2, 
  Clock, 
  Image as ImageIcon,
  RefreshCw,
  Check,
  Loader2,
  MoreVertical,
  Copy,
  Edit3
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Image from 'next/image';
import { Shot, CameraMovementType, ShotAngle, ShotType } from '@/types/storyboard';

interface Character {
  id: string;
  name: string;
  avatar_url?: string;
  color?: string;
}

interface ShotCardProps {
  shot: Shot;
  characters: Character[];
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onUpdate: (updates: Partial<Shot>) => void;
  onGenerateImage: () => void;
  isGeneratingImage?: boolean;
}

const cameraMovementLabels: Record<CameraMovementType, string> = {
  '推': '推',
  '拉': '拉',
  '摇': '摇',
  '移': '移',
  '跟': '跟',
  '升': '升',
  '降': '降',
  '俯': '俯',
  '仰': '仰',
  '变焦': '变焦',
  '固定': '固定',
  '环绕': '环绕',
  '升降': '升降',
  '轨道': '轨道',
  '斯坦尼康': '斯坦尼康',
};

export function ShotCard({
  shot,
  characters,
  isSelected,
  onSelect,
  onDelete,
  onUpdate,
  onGenerateImage,
  isGeneratingImage,
}: ShotCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [copied, setCopied] = useState(false);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: shot.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const shotCharacters = shot.characters
    .map((charId) => characters.find((c) => c.id === charId))
    .filter(Boolean) as Character[];

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}:${secs.toString().padStart(2, '0')}` : `0:${secs.toString().padStart(2, '0')}`;
  };

  const copyPrompt = async () => {
    await navigator.clipboard.writeText(shot.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case '已完成': return 'bg-green-500/20 text-green-400';
      case '生成中': return 'bg-yellow-500/20 text-yellow-400';
      case '已审核': return 'bg-blue-500/20 text-blue-400';
      default: return 'bg-white/10 text-white/60';
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group relative rounded-xl border transition-all overflow-hidden',
        isDragging
          ? 'border-violet-500 bg-violet-600/20 shadow-lg z-50 opacity-90'
          : isSelected
          ? 'border-violet-500/50 bg-violet-600/10'
          : 'border-white/10 bg-white/5 hover:border-white/20'
      )}
    >
      <div onClick={onSelect} className="cursor-pointer">
        <div className="aspect-video bg-white/5 relative overflow-hidden">
          {shot.generated_image ? (
            <Image
              src={shot.generated_image}
              alt={shot.title}
              fill
              className="object-cover"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <ImageIcon className="w-12 h-12 text-white/20 mx-auto mb-2" />
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onGenerateImage();
                  }}
                  disabled={isGeneratingImage}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white text-sm hover:bg-violet-500 transition-colors disabled:opacity-50"
                >
                  {isGeneratingImage ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  {isGeneratingImage ? '生成中...' : '生成图片'}
                </button>
              </div>
            </div>
          )}
          
          <div className="absolute top-2 left-2">
            <span className={cn(
              'px-2 py-0.5 rounded text-xs font-medium',
              getStatusColor(shot.status)
            )}>
              {shot.status}
            </span>
          </div>

          <div className="absolute bottom-2 right-2">
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-black/50 text-white text-xs">
              <Clock className="w-3 h-3" />
              {formatDuration(shot.duration)}
            </div>
          </div>
        </div>

        <div className="p-3">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <button
                className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60 touch-none"
                {...attributes}
                {...listeners}
                onClick={(e) => e.stopPropagation()}
              >
                <GripVertical className="w-4 h-4" />
              </button>
              <span className="text-violet-400 text-sm font-medium">
                #{shot.shot_number}
              </span>
            </div>
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMenu(!showMenu);
                }}
                className="p-1 rounded hover:bg-white/10 text-white/40 hover:text-white transition-colors"
              >
                <MoreVertical className="w-4 h-4" />
              </button>
              {showMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-10" 
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowMenu(false);
                    }}
                  />
                  <div className="absolute right-0 top-full mt-1 w-32 rounded-lg bg-slate-800 border border-white/10 shadow-xl z-20 overflow-hidden">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        copyPrompt();
                        setShowMenu(false);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white/80 hover:bg-white/10"
                    >
                      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      复制提示词
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete();
                        setShowMenu(false);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
                    >
                      <Trash2 className="w-3 h-3" />
                      删除
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          <h4 className="text-white font-medium text-sm mb-2 truncate">
            {shot.title || `镜头 ${shot.shot_number}`}
          </h4>

          <p className="text-white/40 text-xs line-clamp-2 mb-3">
            {shot.description}
          </p>

          <div className="flex flex-wrap gap-1">
            <span className="px-2 py-0.5 bg-violet-500/20 text-violet-300 rounded text-xs">
              {cameraMovementLabels[shot.camera_movement]}
            </span>
            <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-300 rounded text-xs">
              {shot.camera_angle}
            </span>
            <span className="px-2 py-0.5 bg-pink-500/20 text-pink-300 rounded text-xs">
              {shot.shot_type}
            </span>
          </div>

          {shotCharacters.length > 0 && (
            <div className="flex items-center gap-1 mt-3">
              <div className="flex -space-x-2">
                {shotCharacters.slice(0, 3).map((char) => (
                  <div
                    key={char.id}
                    className="w-6 h-6 rounded-full border-2 border-slate-900 overflow-hidden flex-shrink-0"
                    style={{ backgroundColor: char.color || '#6366f1' }}
                    title={char.name}
                  >
                    {char.avatar_url ? (
                      <Image
                        src={char.avatar_url}
                        alt={char.name}
                        width={24}
                        height={24}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-white text-xs font-medium">
                        {char.name.charAt(0)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}