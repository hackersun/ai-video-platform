'use client';

import { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, FileText, Plus, Trash2, Edit2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface Chapter {
  id: string;
  title: string;
  content?: string;
  order: number;
}

interface ChapterListProps {
  chapters: Chapter[];
  onChaptersChange?: (chapters: Chapter[]) => void;
  onChapterSelect?: (chapter: Chapter) => void;
  onChapterAdd?: () => void;
  onChapterDelete?: (chapterId: string) => void;
  onChapterEdit?: (chapter: Chapter) => void;
  selectedChapterId?: string;
}

interface SortableChapterItemProps {
  chapter: Chapter;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onEdit: () => void;
}

function SortableChapterItem({
  chapter,
  isSelected,
  onSelect,
  onDelete,
  onEdit,
}: SortableChapterItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: chapter.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group flex items-center gap-2 p-3 rounded-lg border transition-all',
        isDragging
          ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20 shadow-lg'
          : isSelected
          ? 'border-violet-300 dark:border-violet-700 bg-violet-50/50 dark:bg-violet-900/10'
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800/50',
        isDragging && 'z-50 opacity-90'
      )}
    >
      <button
        className="cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 touch-none"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="w-4 h-4" />
      </button>

      <button
        onClick={onSelect}
        className="flex-1 flex items-center gap-2 text-left min-w-0"
      >
        <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
        <span className="truncate text-sm font-medium text-gray-700 dark:text-gray-200">
          {chapter.title || '未命名章节'}
        </span>
        {chapter.content && (
          <span className="text-xs text-gray-400 flex-shrink-0">
            {chapter.content.replace(/<[^>]*>/g, '').length} 字
          </span>
        )}
      </button>

      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onEdit}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          title="编辑"
        >
          <Edit2 className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-500 hover:text-red-600 dark:hover:text-red-400"
          title="删除"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

export function ChapterList({
  chapters,
  onChaptersChange,
  onChapterSelect,
  onChapterAdd,
  onChapterDelete,
  onChapterEdit,
  selectedChapterId,
}: ChapterListProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const [localChapters, setLocalChapters] = useState(chapters);

  // Sync with props when chapters change
  useState(() => {
    setLocalChapters(chapters);
  });

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = localChapters.findIndex((c) => c.id === active.id);
      const newIndex = localChapters.findIndex((c) => c.id === over.id);

      const newChapters = arrayMove(localChapters, oldIndex, newIndex).map(
        (chapter, index) => ({ ...chapter, order: index })
      );

      setLocalChapters(newChapters);
      onChaptersChange?.(newChapters);
    }
  };

  const handleAdd = () => {
    onChapterAdd?.();
  };

  const handleDelete = (chapterId: string) => {
    onChapterDelete?.(chapterId);
  };

  const handleEdit = (chapter: Chapter) => {
    onChapterEdit?.(chapter);
  };

  const handleSelect = (chapter: Chapter) => {
    onChapterSelect?.(chapter);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
          章节列表
        </h3>
        <span className="text-xs text-gray-500">
          {localChapters.length} 章
        </span>
      </div>

      {localChapters.length > 0 ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={localChapters.map((c) => c.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="flex-1 space-y-2 overflow-y-auto min-h-0">
              {localChapters.map((chapter) => (
                <SortableChapterItem
                  key={chapter.id}
                  chapter={chapter}
                  isSelected={selectedChapterId === chapter.id}
                  onSelect={() => handleSelect(chapter)}
                  onDelete={() => handleDelete(chapter.id)}
                  onEdit={() => handleEdit(chapter)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          暂无章节，点击下方添加
        </div>
      )}

      <button
        onClick={handleAdd}
        className="mt-3 flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 text-gray-500 hover:border-violet-400 hover:text-violet-600 dark:hover:text-violet-400 transition-colors"
      >
        <Plus className="w-4 h-4" />
        <span className="text-sm font-medium">添加章节</span>
      </button>
    </div>
  );
}