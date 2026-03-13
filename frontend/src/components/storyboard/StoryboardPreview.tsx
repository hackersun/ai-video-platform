'use client';

import { useState } from 'react';
import { 
  Grid3X3, 
  List, 
  Plus, 
  ChevronLeft,
  ChevronRight,
  Play,
  Sparkles,
  Download
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ShotCard } from './ShotCard';
import { Shot, Storyboard } from '@/types/storyboard';

interface Character {
  id: string;
  name: string;
  avatar_url?: string;
  color?: string;
}

interface StoryboardPreviewProps {
  storyboard: Storyboard;
  characters: Character[];
  isGeneratingImage?: boolean;
  onShotSelect?: (shot: Shot) => void;
  onShotDelete?: (shotId: string) => void;
  onShotUpdate?: (shotId: string, updates: Partial<Shot>) => void;
  onGenerateImage?: (shotId: string) => void;
  onGenerateAllImages?: () => void;
  onExport?: () => void;
  selectedShotId?: string;
}

type ViewMode = 'grid' | 'list';

export function StoryboardPreview({
  storyboard,
  characters,
  isGeneratingImage,
  onShotSelect,
  onShotDelete,
  onShotUpdate,
  onGenerateImage,
  onGenerateAllImages,
  onExport,
  selectedShotId,
}: StoryboardPreviewProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [currentPage, setCurrentPage] = useState(1);
  const shotsPerPage = viewMode === 'grid' ? 9 : 5;

  const totalPages = Math.ceil(storyboard.shots.length / shotsPerPage);
  const paginatedShots = storyboard.shots.slice(
    (currentPage - 1) * shotsPerPage,
    currentPage * shotsPerPage
  );

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`;
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-white">{storyboard.title}</h2>
          <p className="text-white/40 text-sm mt-1">
            {storyboard.shots.length} 个镜头 · 总时长 {formatDuration(storyboard.total_duration)}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center bg-white/5 rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                'p-2 rounded-md transition-colors',
                viewMode === 'grid' 
                  ? 'bg-violet-600 text-white' 
                  : 'text-white/60 hover:text-white'
              )}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'p-2 rounded-md transition-colors',
                viewMode === 'list' 
                  ? 'bg-violet-600 text-white' 
                  : 'text-white/60 hover:text-white'
              )}
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          {onGenerateAllImages && storyboard.shots.length > 0 && (
            <button
              onClick={onGenerateAllImages}
              disabled={isGeneratingImage}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all',
                'bg-gradient-to-r from-violet-600 to-purple-600 text-white',
                'hover:from-violet-500 hover:to-purple-500',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <Sparkles className="w-4 h-4" />
              批量生成
            </button>
          )}

          {onExport && (
            <button
              onClick={onExport}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all',
                'bg-white/10 text-white hover:bg-white/20'
              )}
            >
              <Download className="w-4 h-4" />
              导出
            </button>
          )}
        </div>
      </div>

      {storyboard.shots.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-20 h-20 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
              <Play className="w-10 h-10 text-white/20" />
            </div>
            <h3 className="text-white font-medium mb-2">暂无分镜</h3>
            <p className="text-white/40 text-sm">请先生成分镜或添加镜头</p>
          </div>
        </div>
      ) : (
        <>
          <div className={cn(
            'flex-1 overflow-y-auto',
            viewMode === 'grid' 
              ? 'grid grid-cols-3 gap-4 auto-rows-auto' 
              : 'space-y-3'
          )}>
            {paginatedShots.map((shot) => (
              <ShotCard
                key={shot.id}
                shot={shot}
                characters={characters}
                isSelected={selectedShotId === shot.id}
                onSelect={() => onShotSelect?.(shot)}
                onDelete={() => onShotDelete?.(shot.id)}
                onUpdate={(updates) => onShotUpdate?.(shot.id, updates)}
                onGenerateImage={() => onGenerateImage?.(shot.id)}
                isGeneratingImage={isGeneratingImage}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-2 rounded-lg bg-white/5 text-white/60 hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              
              <div className="flex items-center gap-1">
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page)}
                    className={cn(
                      'w-8 h-8 rounded-lg text-sm font-medium transition-colors',
                      currentPage === page
                        ? 'bg-violet-600 text-white'
                        : 'text-white/60 hover:text-white hover:bg-white/10'
                    )}
                  >
                    {page}
                  </button>
                ))}
              </div>

              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-2 rounded-lg bg-white/5 text-white/60 hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}