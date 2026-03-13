'use client';

import { Scene } from './SceneCard';
import { Clock, Play, Pause } from 'lucide-react';
import { useState } from 'react';

interface TimelineProps {
  scenes: Scene[];
  selectedSceneId?: string;
  onSceneSelect: (scene: Scene) => void;
  currentTime?: number;
}

export function Timeline({
  scenes,
  selectedSceneId,
  onSceneSelect,
  currentTime = 0,
}: TimelineProps) {
  const [isPlaying, setIsPlaying] = useState(false);

  const totalDuration = scenes.reduce((acc, scene) => acc + (scene.duration || 0), 0);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getScenePosition = (scene: Scene, index: number) => {
    let position = 0;
    for (let i = 0; i < index; i++) {
      position += scenes[i].duration || 0;
    }
    return totalDuration > 0 ? (position / totalDuration) * 100 : 0;
  };

  const getSceneWidth = (scene: Scene) => {
    return totalDuration > 0 ? ((scene.duration || 0) / totalDuration) * 100 : 0;
  };

  return (
    <div className="glass rounded-2xl p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-white/60" />
          <span className="text-sm text-white/60">时间轴</span>
          <span className="text-xs text-white/40">
            总时长: {formatTime(totalDuration)}
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 text-white" />
            ) : (
              <Play className="w-4 h-4 text-white" />
            )}
          </button>
          <span className="text-white/60 text-sm font-mono">
            {formatTime(currentTime)} / {formatTime(totalDuration)}
          </span>
        </div>
      </div>

      <div className="relative">
        <div className="h-16 bg-white/5 rounded-xl overflow-hidden flex">
          {scenes.map((scene, index) => {
            const position = getScenePosition(scene, index);
            const width = getSceneWidth(scene);
            
            return (
              <button
                key={scene.id}
                onClick={() => onSceneSelect(scene)}
                className={`h-full border-r border-white/10 transition-all hover:brightness-110 ${
                  selectedSceneId === scene.id
                    ? 'bg-violet-600/40'
                    : 'bg-violet-600/20'
                }`}
                style={{
                  width: `${Math.max(width, 8)}%`,
                  minWidth: '40px',
                }}
              >
                <div className="px-2 py-1 h-full flex flex-col justify-center">
                  <span className="text-white text-xs font-medium truncate">
                    {scene.scene_number}
                  </span>
                  {scene.duration && (
                    <span className="text-white/40 text-[10px]">
                      {formatTime(scene.duration)}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
          
          {scenes.length === 0 && (
            <div className="flex-1 flex items-center justify-center text-white/40 text-sm">
              暂无场景
            </div>
          )}
        </div>

        {totalDuration > 0 && (
          <div className="absolute top-0 h-full w-px bg-white/30 pointer-events-none"
            style={{ left: `${(currentTime / totalDuration) * 100}%` }}
          />
        )}
      </div>

      <div className="flex items-center justify-between mt-3 text-xs text-white/40">
        {scenes.map((scene, index) => (
          <div key={scene.id} className="flex items-center gap-1">
            <span className="w-5 h-5 rounded bg-violet-600/30 flex items-center justify-center text-white/60">
              {scene.scene_number}
            </span>
            <span className="truncate max-w-[80px]">{scene.title || `场景 ${index + 1}`}</span>
          </div>
        ))}
      </div>
    </div>
  );
}