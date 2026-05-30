export type SelectOption = {
  value: string;
  label: string;
};

export const CAMERA_ANGLE_OPTIONS: SelectOption[] = [
  { value: 'wide', label: '全景' },
  { value: 'long-shot', label: '远景' },
  { value: 'medium', label: '中景' },
  { value: 'medium-shot', label: '中景' },
  { value: 'close-up', label: '近景' },
  { value: 'extreme-close-up', label: '特写' },
  { value: 'over-shoulder', label: '过肩镜头' },
  { value: 'dutch', label: '倾斜镜头' },
  { value: 'two-shot', label: '双人镜头' },
  { value: 'pov', label: '主观镜头' },
  { value: 'birds-eye', label: '鸟瞰' },
  { value: 'aerial', label: '航拍' },
  { value: 'worms-eye', label: '仰视' },
  { value: 'tracking', label: '跟拍' },
  { value: 'pan', label: '摇镜头' },
  { value: 'push-in', label: '推镜头' },
  { value: 'high-angle', label: '俯拍' },
  { value: 'low-angle', label: '仰拍' },
  { value: '全景', label: '全景' },
  { value: '远景', label: '远景' },
  { value: '中景', label: '中景' },
  { value: '近景', label: '近景' },
  { value: '特写', label: '特写' },
  { value: '跟拍', label: '跟拍' },
  { value: '摇镜头', label: '摇镜头' },
  { value: '推镜头', label: '推镜头' },
  { value: '俯拍', label: '俯拍' },
  { value: '仰拍', label: '仰拍' },
];

export const CAMERA_MOVEMENT_OPTIONS: SelectOption[] = [
  { value: 'static', label: '固定镜头' },
  { value: 'pan_left', label: '向左摇' },
  { value: 'pan_right', label: '向右摇' },
  { value: 'tilt_up', label: '向上摇' },
  { value: 'tilt_down', label: '向下摇' },
  { value: 'zoom_in', label: '推近' },
  { value: 'zoom_out', label: '拉远' },
  { value: 'dolly', label: '轨道移动' },
  { value: 'crane', label: '升降镜头' },
  { value: 'handheld', label: '手持镜头' },
];

export const EMOTION_OPTIONS: SelectOption[] = [
  { value: 'neutral', label: '平静' },
  { value: 'happy', label: '开心' },
  { value: 'sad', label: '悲伤' },
  { value: 'angry', label: '愤怒' },
  { value: 'surprised', label: '惊讶' },
  { value: 'tense', label: '紧张' },
  { value: 'relaxed', label: '放松' },
  { value: 'excited', label: '兴奋' },
];

export const LIGHTING_OPTIONS: SelectOption[] = [
  { value: 'natural', label: '自然光' },
  { value: 'dramatic', label: '戏剧光' },
  { value: 'soft', label: '柔光' },
  { value: 'rim', label: '轮廓光' },
  { value: 'back', label: '逆光' },
  { value: 'neon', label: '霓虹光' },
  { value: 'moonlight', label: '月光' },
  { value: 'golden_hour', label: '黄金时刻' },
];

export const COLOR_GRADING_OPTIONS: SelectOption[] = [
  { value: 'warm', label: '暖色调' },
  { value: 'cool', label: '冷色调' },
  { value: 'desaturated', label: '低饱和' },
  { value: 'vibrant', label: '高饱和' },
  { value: 'vintage', label: '复古色调' },
  { value: 'cinematic', label: '电影感' },
  { value: 'noir', label: '黑色电影' },
];

export const STORYBOARD_STYLE_OPTIONS: SelectOption[] = [
  { value: 'anime', label: '动漫' },
  { value: 'xianxia', label: '修仙/仙侠' },
  { value: 'wuxia', label: '武侠江湖' },
  { value: 'xuanhuan', label: '玄幻冒险' },
  { value: 'urban-fantasy', label: '都市异能' },
  { value: 'oriental-fantasy', label: '东方幻想' },
  { value: 'modern-city', label: '现代都市' },
  { value: 'realistic', label: '写实' },
  { value: 'cartoon', label: '卡通' },
  { value: 'noir', label: '黑色电影' },
  { value: 'fantasy', label: '奇幻' },
  { value: 'sci-fi', label: '科幻' },
];

const makeLabelMap = (options: SelectOption[]) =>
  Object.fromEntries(options.map(option => [option.value, option.label]));

export const CAMERA_ANGLE_LABELS: Record<string, string> = makeLabelMap(CAMERA_ANGLE_OPTIONS);
export const CAMERA_MOVEMENT_LABELS: Record<string, string> = makeLabelMap(CAMERA_MOVEMENT_OPTIONS);
export const EMOTION_LABELS: Record<string, string> = makeLabelMap(EMOTION_OPTIONS);
export const LIGHTING_LABELS: Record<string, string> = makeLabelMap(LIGHTING_OPTIONS);
export const COLOR_GRADING_LABELS: Record<string, string> = makeLabelMap(COLOR_GRADING_OPTIONS);
export const STORYBOARD_STYLE_LABELS: Record<string, string> = makeLabelMap(STORYBOARD_STYLE_OPTIONS);

export function getShotAttributeLabel(labels: Record<string, string>, value?: string | null, fallback = '未设置') {
  if (!value) return fallback;
  return labels[value] || value;
}
