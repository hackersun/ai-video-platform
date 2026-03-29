/**
 * 分镜模板系统
 * 提供预定义的分镜模板，包含标准镜头序列
 */

export interface ShotTemplate {
  shot_number: number;
  duration: number;
  camera_angle: string;
  dialogue?: string;
  visual_description: string;
  effect?: string;
}

export interface StoryboardTemplate {
  id: string;
  name: string;
  description: string;
  genre: string;
  shots: ShotTemplate[];
}

export const STORYBOARD_TEMPLATES: StoryboardTemplate[] = [
  {
    id: 'anime-dialogue',
    name: '动画-对话场景',
    description: '两人对话场景，包含正反打镜头，适合角色互动剧情',
    genre: '动画',
    shots: [
      { shot_number: 1, duration: 4, camera_angle: '全景', visual_description: '场景全景，展现环境氛围，室内咖啡厅', effect: '无' },
      { shot_number: 2, duration: 4, camera_angle: '近景', visual_description: '角色A正面特写，表情温和', effect: '光晕' },
      { shot_number: 3, duration: 3, camera_angle: '特写', visual_description: '角色A面部表情变化，微微皱眉', effect: '无' },
      { shot_number: 4, duration: 4, camera_angle: '中景', visual_description: '角色B反应镜头，手持咖啡杯', effect: '暗光' },
      { shot_number: 5, duration: 4, camera_angle: '近景', visual_description: '角色B正面特写，点头回应', effect: '光晕' },
      { shot_number: 6, duration: 5, camera_angle: '远景', visual_description: '场景全景，暗示气氛变化，窗外夕阳', effect: '渐变' },
    ]
  },
  {
    id: 'action-sequence',
    name: '动作场景',
    description: '战斗/追逐等高强度动作场景，快节奏镜头切换',
    genre: '动作',
    shots: [
      { shot_number: 1, duration: 3, camera_angle: '全景', visual_description: '场景开场全景，城市屋顶，黄昏时分', effect: '闪烁' },
      { shot_number: 2, duration: 4, camera_angle: '跟拍', visual_description: '跟拍主角快速移动，翻越障碍', effect: '无' },
      { shot_number: 3, duration: 2, camera_angle: '特写', visual_description: '关键动作瞬间特写，拳头挥出击中目标', effect: '虚化' },
      { shot_number: 4, duration: 3, camera_angle: '摇镜头', visual_description: '快速摇过场景，追逐双方', effect: '旋转' },
      { shot_number: 5, duration: 5, camera_angle: '远景', visual_description: '高潮动作全景，主角跃下高楼', effect: '粒子' },
    ]
  },
  {
    id: 'emotional-scene',
    name: '情感场景',
    description: '抒情/回忆/情感表达场景，慢节奏氛围营造',
    genre: '情感',
    shots: [
      { shot_number: 1, duration: 5, camera_angle: '全景', visual_description: '空旷场景，营造孤独感，海边黄昏', effect: '虚化' },
      { shot_number: 2, duration: 6, camera_angle: '近景', visual_description: '主角面部，情感流露，眼含泪光', effect: '光晕' },
      { shot_number: 3, duration: 4, camera_angle: '特写', visual_description: '手部动作特写，紧握旧照片', effect: '无' },
      { shot_number: 4, duration: 8, camera_angle: '远景', visual_description: '主角独自站立，背影面对大海', effect: '暗光' },
    ]
  },
  {
    id: 'montage',
    name: '蒙太奇',
    description: '快速切换的蒙太奇镜头序列，展示时间流逝或快速信息',
    genre: '通用',
    shots: [
      { shot_number: 1, duration: 2, camera_angle: '特写', visual_description: '镜头1：清晨阳光洒入窗户', effect: '闪烁' },
      { shot_number: 2, duration: 2, camera_angle: '特写', visual_description: '镜头2：时钟指针快速转动', effect: '闪烁' },
      { shot_number: 3, duration: 2, camera_angle: '特写', visual_description: '镜头3：咖啡杯冒着热气', effect: '闪烁' },
      { shot_number: 4, duration: 2, camera_angle: '特写', visual_description: '镜头4：窗外风景快速变换', effect: '闪烁' },
      { shot_number: 5, duration: 3, camera_angle: '全景', visual_description: '蒙太奇结尾全景，夜晚城市灯光', effect: '渐变' },
    ]
  },
  {
    id: 'nature-walk',
    name: '自然风光',
    description: '展示自然风光的慢节奏场景，旅行纪录片风格',
    genre: '风景',
    shots: [
      { shot_number: 1, duration: 6, camera_angle: '远景', visual_description: '壮阔山峦，云雾缭绕，晨光穿透云层', effect: '无' },
      { shot_number: 2, duration: 5, camera_angle: '全景', visual_description: '森林全景，晨光洒落，露珠闪烁', effect: '光晕' },
      { shot_number: 3, duration: 4, camera_angle: '中景', visual_description: '溪流特写，水波粼粼，潺潺流水', effect: '无' },
      { shot_number: 4, duration: 5, camera_angle: '特写', visual_description: '花朵特写，露珠晶莹，蝴蝶飞舞', effect: '暗光' },
      { shot_number: 5, duration: 8, camera_angle: '远景', visual_description: '日落余晖，天际线壮丽，晚霞满天', effect: '渐变' },
    ]
  },
  {
    id: 'anime-opening',
    name: '动画开场',
    description: '标准动画OP开场序列，包含标题和角色展示',
    genre: '动画',
    shots: [
      { shot_number: 1, duration: 3, camera_angle: '远景', visual_description: '黑场渐入，天空云层涌动', effect: '渐变' },
      { shot_number: 2, duration: 4, camera_angle: '全景', visual_description: '城市全景，朝阳升起', effect: '光晕' },
      { shot_number: 3, duration: 3, camera_angle: '中景', visual_description: '主角剪影，站在高处眺望', effect: '暗光' },
      { shot_number: 4, duration: 2, camera_angle: '特写', visual_description: '标题文字出现，风格化字体', effect: '闪烁' },
      { shot_number: 5, duration: 4, camera_angle: '近景', visual_description: '角色A微笑特写，头发飘动', effect: '光晕' },
      { shot_number: 6, duration: 4, camera_angle: '近景', visual_description: '角色B严肃表情特写', effect: '无' },
      { shot_number: 7, duration: 5, camera_angle: '远景', visual_description: '所有角色集合，远景展示', effect: '渐变' },
    ]
  },
  {
    id: 'sci-fi-corridor',
    name: '科幻走廊',
    description: '太空站/科技基地走廊场景，科幻氛围',
    genre: '科幻',
    shots: [
      { shot_number: 1, duration: 4, camera_angle: '全景', visual_description: '走廊全景，金属墙壁，蓝色灯光', effect: '无' },
      { shot_number: 2, duration: 3, camera_angle: '跟拍', visual_description: '跟拍角色快步走过，脚步声回荡', effect: '无' },
      { shot_number: 3, duration: 2, camera_angle: '特写', visual_description: '控制面板特写，屏幕闪烁', effect: '闪烁' },
      { shot_number: 4, duration: 3, camera_angle: '中景', visual_description: '角色看向窗外，星空背景', effect: '暗光' },
      { shot_number: 5, duration: 4, camera_angle: '远景', visual_description: '走廊尽头，光芒闪烁', effect: '光晕' },
    ]
  },
  {
    id: 'cozy-home',
    name: '温馨家居',
    description: '家庭/室内温馨场景，日常生活的美好',
    genre: '生活',
    shots: [
      { shot_number: 1, duration: 5, camera_angle: '全景', visual_description: '客厅全景，暖色调灯光，窗外夜色', effect: '无' },
      { shot_number: 2, duration: 4, camera_angle: '中景', visual_description: '父母和孩子在沙发上阅读', effect: '光晕' },
      { shot_number: 3, duration: 3, camera_angle: '特写', visual_description: '孩子手中的绘本，翻到精彩页面', effect: '无' },
      { shot_number: 4, duration: 4, camera_angle: '近景', visual_description: '父亲微笑看着孩子', effect: '光晕' },
      { shot_number: 5, duration: 5, camera_angle: '远景', visual_description: '窗外圣诞灯饰闪烁，屋内温暖', effect: '闪烁' },
    ]
  },
];

// 根据类型获取模板
export const getTemplatesByGenre = (genre: string): StoryboardTemplate[] => {
  return STORYBOARD_TEMPLATES.filter(t => t.genre === genre);
};

// 根据ID获取模板
export const getTemplateById = (id: string): StoryboardTemplate | undefined => {
  return STORYBOARD_TEMPLATES.find(t => t.id === id);
};

// 获取所有类型
export const getAllGenres = (): string[] => {
  return Array.from(new Set(STORYBOARD_TEMPLATES.map(t => t.genre)));
};
