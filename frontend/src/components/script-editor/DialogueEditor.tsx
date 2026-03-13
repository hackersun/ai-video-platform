'use client';

import { useState } from 'react';
import { Character } from './SceneCard';
import { Plus, Trash2, MessageCircle } from 'lucide-react';

interface DialogueLine {
  id: string;
  character_id: string;
  text: string;
}

interface DialogueEditorProps {
  dialogue: Record<string, unknown>;
  characters: Character[];
  onChange: (dialogue: Record<string, unknown>) => void;
}

export function DialogueEditor({
  dialogue,
  characters,
  onChange,
}: DialogueEditorProps) {
  const [lines, setLines] = useState<DialogueLine[]>(() => {
    if (dialogue.lines && Array.isArray(dialogue.lines)) {
      return dialogue.lines as DialogueLine[];
    }
    return [];
  });

  const addLine = () => {
    const newLine: DialogueLine = {
      id: `line_${Date.now()}`,
      character_id: characters[0]?.id || '',
      text: '',
    };
    const newLines = [...lines, newLine];
    setLines(newLines);
    onChange({ lines: newLines });
  };

  const updateLine = (id: string, updates: Partial<DialogueLine>) => {
    const newLines = lines.map((line) =>
      line.id === id ? { ...line, ...updates } : line
    );
    setLines(newLines);
    onChange({ lines: newLines });
  };

  const deleteLine = (id: string) => {
    const newLines = lines.filter((line) => line.id !== id);
    setLines(newLines);
    onChange({ lines: newLines });
  };

  const getCharacter = (id: string) => characters.find((c) => c.id === id);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <label className="flex items-center gap-2 text-sm text-white/60">
          <MessageCircle className="w-4 h-4" />
          对话编辑
        </label>
        <button
          onClick={addLine}
          className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 transition-colors"
        >
          <Plus className="w-3 h-3" />
          添加台词
        </button>
      </div>

      <div className="space-y-3">
        {lines.map((line, index) => {
          const char = getCharacter(line.character_id);
          return (
            <div
              key={line.id}
              className="flex items-start gap-3 p-3 rounded-lg bg-white/5 border border-white/10"
            >
              <span className="text-white/30 text-xs mt-2">{index + 1}</span>
              
              <select
                value={line.character_id}
                onChange={(e) => updateLine(line.id, { character_id: e.target.value })}
                className="px-2 py-1 rounded bg-white/10 border border-white/10 text-white text-sm focus:outline-none focus:ring-1 focus:ring-violet-500"
              >
                {characters.map((char) => (
                  <option key={char.id} value={char.id}>
                    {char.name}
                  </option>
                ))}
              </select>
              
              <div
                className="w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-medium"
                style={{ backgroundColor: char?.color || '#6366f1' }}
              >
                {char?.name.charAt(0) || '?'}
              </div>
              
              <input
                type="text"
                value={line.text}
                onChange={(e) => updateLine(line.id, { text: e.target.value })}
                className="flex-1 px-3 py-1.5 rounded bg-white/10 border border-white/10 text-white text-sm placeholder-white/40 focus:outline-none focus:ring-1 focus:ring-violet-500"
                placeholder="台词内容..."
              />
              
              <button
                onClick={() => deleteLine(line.id)}
                className="p-1 text-white/30 hover:text-red-400 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          );
        })}

        {lines.length === 0 && (
          <div className="text-center py-4 text-white/40 text-sm">
            点击"添加台词"开始编辑对话
          </div>
        )}
      </div>
    </div>
  );
}