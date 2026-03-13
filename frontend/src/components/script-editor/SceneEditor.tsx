'use client';

import { Scene, Character } from './SceneCard';
import { DialogueEditor } from './DialogueEditor';
import { 
  Image as ImageIcon, 
  Film, 
  Volume2, 
  Clock, 
  Users,
  Camera,
  Sparkles,
} from 'lucide-react';

interface SceneEditorProps {
  scene: Scene;
  characters: Character[];
  isGenerating: boolean;
  onUpdate: (updates: Partial<Scene>) => void;
  onGenerateVideo: () => void;
  onGenerateImage: () => void;
  onGenerateAudio: () => void;
}

export function SceneEditor({
  scene,
  characters,
  isGenerating,
  onUpdate,
  onGenerateVideo,
  onGenerateImage,
  onGenerateAudio,
}: SceneEditorProps) {
  const sceneCharacters = scene.characters
    .map((charId) => characters.find((c) => c.id === charId))
    .filter(Boolean) as Character[];

  const handleDurationChange = (minutes: number, seconds: number) => {
    onUpdate({ duration: minutes * 60 + seconds });
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return { minutes: 0, seconds: 0 };
    return {
      minutes: Math.floor(seconds / 60),
      seconds: seconds % 60,
    };
  };

  const duration = formatDuration(scene.duration);

  return (
    <div className="flex flex-col h-full">
      <div className="mb-6">
        <input
          type="text"
          value={scene.title}
          onChange={(e) => onUpdate({ title: e.target.value })}
          className="w-full text-2xl font-bold text-white bg-transparent border-none focus:outline-none focus:ring-0 placeholder-white/40"
          placeholder="场景标题"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="flex items-center gap-2 text-sm text-white/60 mb-2">
                <Users className="w-4 h-4" />
                地点
              </label>
              <input
                type="text"
                value={scene.location}
                onChange={(e) => onUpdate({ location: e.target.value })}
                className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="例如：客厅"
              />
            </div>
            <div>
              <label className="flex items-center gap-2 text-sm text-white/60 mb-2">
                <Clock className="w-4 h-4" />
                时间
              </label>
              <select
                value={scene.time_of_day}
                onChange={(e) => onUpdate({ time_of_day: e.target.value })}
                className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                <option value="白天">白天</option>
                <option value="夜晚">夜晚</option>
                <option value="清晨">清晨</option>
                <option value="黄昏">黄昏</option>
                <option value="午夜">午夜</option>
              </select>
            </div>
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm text-white/60 mb-2">
              <Camera className="w-4 h-4" />
              时长
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                value={duration.minutes}
                onChange={(e) => handleDurationChange(Number(e.target.value), duration.seconds)}
                className="w-20 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-center focus:outline-none focus:ring-2 focus:ring-violet-500"
              />
              <span className="text-white/60">分</span>
              <input
                type="number"
                min={0}
                max={59}
                value={duration.seconds}
                onChange={(e) => handleDurationChange(duration.minutes, Number(e.target.value))}
                className="w-20 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-center focus:outline-none focus:ring-2 focus:ring-violet-500"
              />
              <span className="text-white/60">秒</span>
            </div>
          </div>

          <div>
            <label className="block text-sm text-white/60 mb-2">场景描述</label>
            <textarea
              value={scene.description}
              onChange={(e) => onUpdate({ description: e.target.value })}
              className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
              rows={3}
              placeholder="描述这个场景..."
            />
          </div>

          <div>
            <label className="block text-sm text-white/60 mb-2">动作描述</label>
            <textarea
              value={scene.action_description}
              onChange={(e) => onUpdate({ action_description: e.target.value })}
              className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
              rows={2}
              placeholder="角色的动作..."
            />
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm text-white/60 mb-2">
              <Camera className="w-4 h-4" />
              镜头指示
            </label>
            <input
              type="text"
              value={scene.camera_direction}
              onChange={(e) => onUpdate({ camera_direction: e.target.value })}
              className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500"
              placeholder="例如：特写、全景、推拉镜头..."
            />
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="flex items-center gap-2 text-sm text-white/60 mb-2">
              <Sparkles className="w-4 h-4" />
              角色分配
            </label>
            <div className="flex flex-wrap gap-2">
              {characters.map((char) => (
                <button
                  key={char.id}
                  onClick={() => {
                    const hasChar = scene.characters.includes(char.id);
                    const newCharacters = hasChar
                      ? scene.characters.filter((c) => c !== char.id)
                      : [...scene.characters, char.id];
                    onUpdate({ characters: newCharacters });
                  }}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
                    scene.characters.includes(char.id)
                      ? 'border-violet-500 bg-violet-500/20 text-white'
                      : 'border-white/10 bg-white/5 text-white/60 hover:border-white/30'
                  }`}
                >
                  <div
                    className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium"
                    style={{ backgroundColor: char.color || '#6366f1' }}
                  >
                    {char.name.charAt(0)}
                  </div>
                  <span className="text-sm">{char.name}</span>
                </button>
              ))}
              {characters.length === 0 && (
                <p className="text-white/40 text-sm">暂无角色，请先创建角色</p>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm text-white/60 mb-2">预览图</label>
            <div className="aspect-video rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden">
              {scene.preview_image ? (
                <img
                  src={scene.preview_image}
                  alt="预览"
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="text-center">
                  <ImageIcon className="w-12 h-12 text-white/20 mx-auto mb-2" />
                  <p className="text-white/40 text-sm">点击生成预览图</p>
                </div>
              )}
            </div>
          </div>

          {sceneCharacters.length > 0 && (
            <DialogueEditor
              dialogue={scene.dialogue}
              characters={sceneCharacters}
              onChange={(dialogue) => onUpdate({ dialogue })}
            />
          )}
        </div>
      </div>

      <div className="border-t border-white/10 pt-6 mt-auto">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
          <Sparkles className="w-5 h-5 text-violet-400" />
          AI 生成
        </h3>
        
        <div className="grid grid-cols-3 gap-4">
          <button
            onClick={onGenerateVideo}
            disabled={isGenerating}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/50 transition-all disabled:opacity-50"
          >
            <Film className="w-8 h-8 text-violet-400" />
            <span className="text-white text-sm">生成视频</span>
          </button>
          
          <button
            onClick={onGenerateImage}
            disabled={isGenerating}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-cyan-500/50 transition-all disabled:opacity-50"
          >
            <ImageIcon className="w-8 h-8 text-cyan-400" />
            <span className="text-white text-sm">生成图片</span>
          </button>
          
          <button
            onClick={onGenerateAudio}
            disabled={isGenerating}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-pink-500/50 transition-all disabled:opacity-50"
          >
            <Volume2 className="w-8 h-8 text-pink-400" />
            <span className="text-white text-sm">生成配音</span>
          </button>
        </div>
      </div>
    </div>
  );
}