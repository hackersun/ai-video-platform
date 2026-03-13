'use client';

import Image from 'next/image';

export type CameraMovementType = 
  | '推' | '拉' | '摇' | '移' | '跟' | '升' | '降' | '俯' | '仰' 
  | '变焦' | '固定' | '环绕' | '升降' | '轨道' | '斯坦尼康';

export type ShotAngle = 
  | '特写' | '近景' | '中景' | '中近景' | '全景' | '远景' | '大远景' | '主观镜头' | '过肩镜头';

export type ShotType = 
  | '建立镜头' | '动作镜头' | '对话镜头' | '反应镜头' | '插入镜头' | '转场镜头' | '空镜头' | '特写镜头';

export type ShotStatus = '草稿' | '生成中' | '已完成' | '已审核';

export interface Shot {
  id: string;
  shot_number: number;
  title: string;
  description: string;
  prompt: string;
  negative_prompt?: string;
  camera_movement: CameraMovementType;
  camera_angle: ShotAngle;
  shot_type: ShotType;
  duration: number;
  characters: string[];
  location: string;
  time_of_day: string;
  dialogue?: string;
  status: ShotStatus;
  generated_image?: string;
  generated_image_prompt?: string;
  notes?: string;
  order: number;
}

export interface Storyboard {
  id: string;
  title: string;
  description?: string;
  script_id: string;
  scene_id?: string;
  shots: Shot[];
  total_duration: number;
  status: '草稿' | '生成中' | '已完成';
  created_at: string;
  updated_at: string;
}

export interface AIShotSuggestion {
  description: string;
  prompt: string;
  camera_movement: CameraMovementType;
  camera_angle: ShotAngle;
  shot_type: ShotType;
  duration: number;
}

export interface ExportOptions {
  format: 'pdf' | 'images' | 'both';
  includePrompt: boolean;
  includeCameraInfo: boolean;
  imageQuality: 'low' | 'medium' | 'high';
}

export interface StoryboardGenerationConfig {
  sceneDescription: string;
  numShots: number;
  style?: string;
  aspectRatio?: '16:9' | '9:16' | '4:3' | '1:1';
  includeCameraMovement: boolean;
}

export interface CameraMovementSuggestion {
  type: CameraMovementType;
  description: string;
  visual_example?: string;
  recommended_for: string[];
}

export const CAMERA_MOVEMENT_SUGGESTIONS: CameraMovementSuggestion[] = [
  { type: '推', description: '镜头向前推进，接近目标', recommended_for: ['突出细节', '强调重要性', '制造紧张感'] },
  { type: '拉', description: '镜头向后拉远，展示环境', recommended_for: ['展示全貌', '情节转折', '情绪舒缓'] },
  { type: '摇', description: '水平或垂直摇动镜头', recommended_for: ['展示空间', '跟随目标', 'PAN效果'] },
  { type: '移', description: '横向移动拍摄', recommended_for: ['平行动作', '展示长镜头', '营造氛围'] },
  { type: '跟', description: '跟随移动的目标拍摄', recommended_for: ['追逐场景', '动态对话', '跟踪情节'] },
  { type: '升', description: '镜头向上移动', recommended_for: ['展现高度', '象征升华', '场景转换'] },
  { type: '降', description: '镜头向下移动', recommended_for: ['降落场景', '压抑情绪', '视角转换'] },
  { type: '俯', description: '从高处向下拍摄', recommended_for: ['展示全貌', '地图视角', '宏观表达'] },
  { type: '仰', description: '从低处向上拍摄', recommended_for: ['突出高大', '仰视英雄', '压迫感'] },
  { type: '固定', description: '固定机位不移动', recommended_for: ['对话场景', '静态情节', '特写'] },
  { type: '环绕', description: '围绕目标旋转拍摄', recommended_for: ['展示物体', '强调神秘', '360度展示'] },
  { type: '升降', description: '同时进行升降运动', recommended_for: ['复杂场景', '大场面的开始或结束'] },
  { type: '轨道', description: '使用轨道设备平滑移动', recommended_for: ['专业制作', '长镜头', '平滑跟随'] },
  { type: '斯坦尼康', description: '使用稳定器拍摄', recommended_for: ['手持效果', '行走跟拍', '自然过渡'] },
];

export const SHOT_ANGLES: { value: ShotAngle; label: string; description: string }[] = [
  { value: '特写', label: '特写', description: '聚焦人物面部或物体细节' },
  { value: '近景', label: '近景', description: '展示人物上半身' },
  { value: '中近景', label: '中近景', description: '展示人物腰部以上' },
  { value: '中景', label: '中景', description: '展示人物全身或场景局部' },
  { value: '全景', label: '全景', description: '展示人物全身及周围环境' },
  { value: '远景', label: '远景', description: '展示广阔的场景' },
  { value: '大远景', label: '大远景', description: '极远距离拍摄，展示宏观场景' },
  { value: '主观镜头', label: '主观镜头', description: 'POV视角，观众代入感强' },
  { value: '过肩镜头', label: '过肩镜头', description: '两人对话常用视角' },
];

export const SHOT_TYPES: { value: ShotType; label: string; description: string }[] = [
  { value: '建立镜头', label: '建立镜头', description: '开场建立场景' },
  { value: '动作镜头', label: '动作镜头', description: '展示动作场景' },
  { value: '对话镜头', label: '对话镜头', description: '人物对话' },
  { value: '反应镜头', label: '反应镜头', description: '展示人物反应' },
  { value: '插入镜头', label: '插入镜头', description: '细节补充' },
  { value: '转场镜头', label: '转场镜头', description: '场景过渡' },
  { value: '空镜头', label: '空镜头', description: '无人物的环境镜头' },
  { value: '特写镜头', label: '特写镜头', description: '强调细节' },
];