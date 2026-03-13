'use client';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Trash2, Clock, Users } from 'lucide-react';
import { cn } from '@/lib/utils';
import Image from 'next/image';

export interface Character {
  id: string;
  name: string;
  avatar_url?: string;
  color?: string;
}

export interface Scene {
  id: string;
  scene_number: number;
  title: string;
  description: string;
  location: string;
  time_of_day: string;
  characters: string[];
  dialogue: Record<string, unknown>;
  action_description: string;
  camera_direction: string;
  duration?: number;
  preview_image?: string;
}

interface SceneCardProps {
  scene: Scene;
  characters: Character[];
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

export function SceneCard({
  scene,
  characters,
  isSelected,
  onSelect,
  onDelete,
}: SceneCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: scene.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const sceneCharacters = scene.characters
    .map((charId) => characters.find((c) => c.id === charId))
    .filter(Boolean) as Character[];

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all',
        isDragging
          ? 'border-violet-500 bg-violet-600/20 shadow-lg z-50 opacity-90'
          : isSelected
          ? 'border-violet-500/50 bg-violet-600/10'
          : 'border-white/10 bg-white/5 hover:border-white/20'
      )}
      onClick={onSelect}
      >
        <button
          className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60 touch-none"
          {...attributes}
          {...listeners}
          onClick={(e) => e.stopPropagation()}
        >
          <GripVertical className="w-4 h-4" />
        </button>

        <div className="w-8 h-8 rounded-lg bg-violet-600/30 flex items-center justify-center text-violet-300 text-sm font-medium flex-shrink-0">
          {scene.scene_number}
        </div>

        <div className="flex-1 min-w-0">
        <h3 className="text-white font-medium text-sm truncate">
          {scene.title || `场景 ${scene.scene_number}`}
        </h3>
        <div className="flex items-center gap-3 text-white/40 text-xs">
          <span className="truncate">{scene.location || '未设置地点'}</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatDuration(scene.duration)}
          </span>
        </div>
      </div>

      {sceneCharacters.length > 0 && (
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          <Users className="w-3 h-3 text-white/40" />
          <div className="flex -space-x-2">
            {sceneCharacters.slice(0, 3).map((char) => (
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
            {sceneCharacters.length > 3 && (
              <div className="w-6 h-6 rounded-full bg-white/20 border-2 border-slate-900 flex items-center justify-center text-white text-xs">
                +{sceneCharacters.length - 3}
              </div>
            )}
          </div>
        </div>
      )}

      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="p-1.5 rounded hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
        title="删除场景"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}