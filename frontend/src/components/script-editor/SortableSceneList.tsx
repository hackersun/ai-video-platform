'use client';

import { useState, useEffect } from 'react';
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
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { Plus, Film } from 'lucide-react';
import { SceneCard, Character, Scene } from './SceneCard';

interface SortableSceneListProps {
  scenes: Scene[];
  characters: Character[];
  selectedSceneId?: string;
  onSceneSelect: (scene: Scene) => void;
  onSceneDelete: (sceneId: string) => void;
  onSceneReorder: (scenes: Scene[]) => void;
  onAddScene: () => void;
}

export function SortableSceneList({
  scenes,
  characters,
  selectedSceneId,
  onSceneSelect,
  onSceneDelete,
  onSceneReorder,
  onAddScene,
}: SortableSceneListProps) {
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

  const [localScenes, setLocalScenes] = useState(scenes);

  useEffect(() => {
    setLocalScenes(scenes);
  }, [scenes]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = localScenes.findIndex((s) => s.id === active.id);
      const newIndex = localScenes.findIndex((s) => s.id === over.id);

      const newScenes = arrayMove(localScenes, oldIndex, newIndex).map(
        (scene, index) => ({
          ...scene,
          scene_number: index + 1,
        })
      );

      setLocalScenes(newScenes);
      onSceneReorder(newScenes);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">场景列表</h3>
        <span className="text-xs text-white/40">
          {localScenes.length} 个场景
        </span>
      </div>

      {localScenes.length > 0 ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={localScenes.map((s) => s.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="flex-1 space-y-2 overflow-y-auto min-h-0">
              {localScenes.map((scene) => (
                <SceneCard
                  key={scene.id}
                  scene={scene}
                  characters={characters}
                  isSelected={selectedSceneId === scene.id}
                  onSelect={() => onSceneSelect(scene)}
                  onDelete={() => onSceneDelete(scene.id)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-white/40">
          <Film className="w-12 h-12 mb-3 opacity-30" />
          <p className="text-sm mb-4">还没有场景</p>
        </div>
      )}

      <button
        onClick={onAddScene}
        className="mt-3 flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl border-2 border-dashed border-white/20 text-white/60 hover:border-violet-500 hover:text-violet-400 transition-colors"
      >
        <Plus className="w-4 h-4" />
        <span className="text-sm font-medium">添加场景</span>
      </button>
    </div>
  );
}