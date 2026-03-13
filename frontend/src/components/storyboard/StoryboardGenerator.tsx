'use client';

import { useState } from 'react';
import { 
  Sparkles, 
  Wand2, 
  Loader2, 
  Copy, 
  Check, 
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Zap
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { storyboardApi } from '@/lib/api';
import { 
  CameraMovementType, 
  ShotAngle, 
  ShotType,
  CAMERA_MOVEMENT_SUGGESTIONS,
  SHOT_ANGLES,
  SHOT_TYPES
} from '@/types/storyboard';

interface StoryboardGeneratorProps {
  sceneDescription: string;
  onShotsGenerated?: (shots: any[]) => void;
  isGenerating?: boolean;
  setIsGenerating?: (val: boolean) => void;
  style?: string;
}

interface PromptResult {
  description: string;
  prompt: string;
  camera_movement: CameraMovementType;
  camera_angle: ShotAngle;
  shot_type: ShotType;
  duration: number;
}

export function StoryboardGenerator({
  sceneDescription,
  onShotsGenerated,
  style = '写实',
  isGenerating: externalIsGenerating,
  setIsGenerating: externalSetIsGenerating,
}: StoryboardGeneratorProps) {
  const [localIsGenerating, setLocalIsGenerating] = useState(false);
  const [promptResults, setPromptResults] = useState<PromptResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const [cameraMovement, setCameraMovement] = useState<CameraMovementType>('推');
  const [cameraAngle, setCameraAngle] = useState<ShotAngle>('中景');
  const [shotType, setShotType] = useState<ShotType>('动作镜头');

  const isGenerating = externalIsGenerating ?? localIsGenerating;
  const setIsGenerating = externalSetIsGenerating ?? setLocalIsGenerating;

  const handleGeneratePrompts = async () => {
    if (!sceneDescription.trim()) {
      setError('请输入场景描述');
      return;
    }

    setError(null);
    setIsGenerating(true);

    try {
      const response = await storyboardApi.convertToPrompt({
        scene_description: sceneDescription,
        camera_movement: cameraMovement,
        camera_angle: cameraAngle,
        shot_type: shotType,
        style: style,
      });
      
      const data = response.data;
      if (Array.isArray(data)) {
        setPromptResults(data);
        onShotsGenerated?.(data);
      } else if (data.suggestions) {
        setPromptResults(data.suggestions);
        onShotsGenerated?.(data.suggestions);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '生成失败，请重试');
    } finally {
      setIsGenerating(false);
    }
  };

  const copyPrompt = async (prompt: string, index: number) => {
    await navigator.clipboard.writeText(prompt);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`;
  };

  return (
    <div className="space-y-6">
      <div className="bg-white/5 rounded-2xl border border-white/10 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <Sparkles className="w-5 h-5 text-violet-400" />
            场景描述 → 分镜提示词
          </h3>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-sm text-white/60 hover:text-white transition-colors"
          >
            {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            高级选项
          </button>
        </div>

        {showAdvanced && (
          <div className="grid grid-cols-3 gap-4 mb-4 p-4 bg-white/5 rounded-xl">
            <div>
              <label className="block text-sm text-white/60 mb-2">镜头运动</label>
              <select
                value={cameraMovement}
                onChange={(e) => setCameraMovement(e.target.value as CameraMovementType)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                {CAMERA_MOVEMENT_SUGGESTIONS.map((item) => (
                  <option key={item.type} value={item.type} className="bg-slate-800">
                    {item.type} - {item.description}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-2">镜头角度</label>
              <select
                value={cameraAngle}
                onChange={(e) => setCameraAngle(e.target.value as ShotAngle)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                {SHOT_ANGLES.map((item) => (
                  <option key={item.value} value={item.value} className="bg-slate-800">
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-2">镜头类型</label>
              <select
                value={shotType}
                onChange={(e) => setShotType(e.target.value as ShotType)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                {SHOT_TYPES.map((item) => (
                  <option key={item.value} value={item.value} className="bg-slate-800">
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        <button
          onClick={handleGeneratePrompts}
          disabled={isGenerating || !sceneDescription.trim()}
          className={cn(
            'w-full flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all',
            'bg-gradient-to-r from-violet-600 to-purple-600 text-white',
            'hover:from-violet-500 hover:to-purple-500',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'shadow-lg shadow-violet-500/25'
          )}
        >
          {isGenerating ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Wand2 className="w-5 h-5" />
          )}
          {isGenerating ? 'AI 正在转换...' : '转换为分镜提示词'}
        </button>

        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}
      </div>

      {promptResults.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-white font-medium">生成的提示词</h4>
            <span className="text-white/40 text-sm">{promptResults.length} 个分镜</span>
          </div>

          <div className="space-y-3">
            {promptResults.map((result, index) => (
              <div
                key={index}
                className="bg-white/5 rounded-xl border border-white/10 overflow-hidden"
              >
                <div 
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => setExpandedIndex(expandedIndex === index ? null : index)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-violet-600/30 flex items-center justify-center text-violet-300 text-sm font-medium">
                      {index + 1}
                    </div>
                    <div>
                      <p className="text-white font-medium text-sm">{result.description.slice(0, 50)}...</p>
                      <p className="text-white/40 text-xs">
                        {result.camera_movement} · {result.camera_angle} · {result.shot_type} · {formatDuration(result.duration)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        copyPrompt(result.prompt, index);
                      }}
                      className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                    >
                      {copiedIndex === index ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </button>
                    {expandedIndex === index ? (
                      <ChevronUp className="w-4 h-4 text-white/40" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-white/40" />
                    )}
                  </div>
                </div>

                {expandedIndex === index && (
                  <div className="px-4 pb-4 border-t border-white/10">
                    <div className="mt-4 space-y-3">
                      <div>
                        <label className="block text-xs text-white/40 mb-1">提示词</label>
                        <div className="p-3 bg-slate-800/50 rounded-lg text-white/80 text-sm font-mono">
                          {result.prompt}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className="px-2 py-1 bg-violet-500/20 text-violet-300 rounded text-xs">
                          {result.camera_movement}
                        </span>
                        <span className="px-2 py-1 bg-cyan-500/20 text-cyan-300 rounded text-xs">
                          {result.camera_angle}
                        </span>
                        <span className="px-2 py-1 bg-pink-500/20 text-pink-300 rounded text-xs">
                          {result.shot_type}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}