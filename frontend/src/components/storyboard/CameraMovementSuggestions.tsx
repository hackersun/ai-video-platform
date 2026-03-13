'use client';

import { useState } from 'react';
import { 
  Video, 
  ChevronDown, 
  Check,
  Info,
  X
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { 
  CameraMovementType, 
  CameraMovementSuggestion,
  CAMERA_MOVEMENT_SUGGESTIONS 
} from '@/types/storyboard';

interface CameraMovementSuggestionsProps {
  onSelect?: (movement: CameraMovementType) => void;
  selectedMovements?: CameraMovementType[];
  showDescriptions?: boolean;
  multiple?: boolean;
}

export function CameraMovementSuggestions({
  onSelect,
  selectedMovements = [],
  showDescriptions = true,
  multiple = false,
}: CameraMovementSuggestionsProps) {
  const [expandedType, setExpandedType] = useState<CameraMovementType | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const filteredMovements = CAMERA_MOVEMENT_SUGGESTIONS.filter(
    (m) => 
      m.type.includes(searchTerm) || 
      m.description.includes(searchTerm) ||
      m.recommended_for.some(r => r.includes(searchTerm))
  );

  const handleSelect = (type: CameraMovementType) => {
    if (multiple) {
      const newSelection = selectedMovements.includes(type)
        ? selectedMovements.filter(m => m !== type)
        : [...selectedMovements, type];
      onSelect?.(newSelection as any);
    } else {
      onSelect?.(type);
    }
  };

  const isSelected = (type: CameraMovementType) => {
    return multiple 
      ? selectedMovements.includes(type)
      : selectedMovements[0] === type;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <Video className="w-5 h-5 text-violet-400" />
        <h3 className="text-white font-medium">镜头运动建议</h3>
      </div>

      <input
        type="text"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        placeholder="搜索镜头运动..."
        className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500"
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-96 overflow-y-auto">
        {filteredMovements.map((movement) => (
          <button
            key={movement.type}
            onClick={() => handleSelect(movement.type)}
            className={cn(
              'relative p-3 rounded-xl border text-left transition-all',
              isSelected(movement.type)
                ? 'border-violet-500 bg-violet-500/20'
                : 'border-white/10 bg-white/5 hover:border-white/30'
            )}
          >
            {isSelected(movement.type) && (
              <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-violet-500 flex items-center justify-center">
                <Check className="w-3 h-3 text-white" />
              </div>
            )}
            
            <div className="font-medium text-white mb-1">{movement.type}</div>
            
            {showDescriptions && (
              <p className="text-white/40 text-xs line-clamp-2">
                {movement.description}
              </p>
            )}

            {showDescriptions && movement.recommended_for.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {movement.recommended_for.slice(0, 2).map((tag) => (
                  <span 
                    key={tag} 
                    className="px-1.5 py-0.5 bg-white/5 rounded text-white/40 text-xs"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </button>
        ))}
      </div>

      <div className="mt-4 p-4 bg-white/5 rounded-xl border border-white/10">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-violet-400 mt-0.5 flex-shrink-0" />
          <div className="text-white/60 text-sm">
            <p className="font-medium text-white/80 mb-1">运动镜头选择建议</p>
            <ul className="text-xs space-y-1 text-white/40">
              <li>• 推镜头：强调重要人物或物体</li>
              <li>• 拉镜头：展示环境全貌或转场</li>
              <li>• 摇镜头：展示空间或跟随目标</li>
              <li>• 固定镜头：对话或静态场景</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

interface CameraMovementSelectorProps {
  value: CameraMovementType;
  onChange: (value: CameraMovementType) => void;
}

export function CameraMovementSelector({ value, onChange }: CameraMovementSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const selected = CAMERA_MOVEMENT_SUGGESTIONS.find(m => m.type === value);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center justify-between px-4 py-2 rounded-lg',
          'bg-white/5 border border-white/10 text-white',
          'hover:border-white/30 transition-colors'
        )}
      >
        <span>{selected?.type || '选择镜头运动'} - {selected?.description}</span>
        <ChevronDown className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute left-0 right-0 mt-2 max-h-80 overflow-y-auto rounded-xl bg-slate-800 border border-white/10 shadow-xl z-20">
            {CAMERA_MOVEMENT_SUGGESTIONS.map((movement) => (
              <button
                key={movement.type}
                onClick={() => {
                  onChange(movement.type);
                  setIsOpen(false);
                }}
                className={cn(
                  'w-full flex items-center justify-between px-4 py-3 text-left transition-colors',
                  value === movement.type
                    ? 'bg-violet-600/20 text-white'
                    : 'text-white/80 hover:bg-white/5'
                )}
              >
                <div>
                  <div className="font-medium">{movement.type}</div>
                  <div className="text-white/40 text-xs">{movement.description}</div>
                </div>
                {value === movement.type && (
                  <Check className="w-4 h-4 text-violet-400" />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}