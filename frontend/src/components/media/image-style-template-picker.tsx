'use client';

import { Badge } from '@/components/ui/badge';

export type ImageStyleTemplate = {
  style: string;
  label: string;
  description?: string;
  sample_url?: string;
  aspect_ratios?: string[];
  recommended_for?: string[];
  prompt?: string;
};

const styleTemplate = (
  style: string,
  label: string,
  description: string,
  prompt: string,
  aspect_ratios: string[] = ['16:9', '9:16'],
): ImageStyleTemplate => ({
  style,
  label,
  description,
  sample_url: `/static/starter/style-${style}-reference.png`,
  aspect_ratios,
  recommended_for: ['character', 'scene', 'prop', 'cover', 'avatar', 'shot'],
  prompt,
});

export const DEFAULT_IMAGE_STYLE_TEMPLATES: ImageStyleTemplate[] = [
  styleTemplate('realistic', '真人写实', '真实演员质感、自然皮肤、电影镜头和现实光影。', '真人写实电影质感，真实演员外观，自然皮肤纹理，真实服装材质，电影级布光和景深，保持同一视觉设定。'),
  styleTemplate('xianxia', '修仙仙侠', '东方修仙、灵气、法器、仙门服饰和秘境氛围。', '东方修仙动画设定图，灵气氛围，飘逸服饰，仙侠质感，统一世界观。'),
  styleTemplate('wuxia', '武侠江湖', '江湖、刀剑、客栈、竹林，低饱和电影感。', '武侠动画设定图，江湖质感，利落服饰，电影感构图，统一世界观。'),
  styleTemplate('fantasy', '东方玄幻', '秘境、遗迹、符文、史诗感和强视觉奇观。', '东方玄幻动画设定图，史诗感，细节丰富，统一美术风格。'),
  styleTemplate('urban', '现代都市', '现代短剧、城市环境、现实光影和清晰人物造型。', '现代都市动画设定图，清晰造型，现实光影，统一美术风格。'),
  styleTemplate('anime', '2D动画', '干净线稿、稳定上色，适合通用动漫短剧。', '2D日系动画设定图，干净线稿，高质量上色，清晰角色轮廓，统一角色设定。'),
  styleTemplate('cartoon', '卡通明快', '轮廓清晰、色彩明快，适合轻松日常或轻喜剧。', '动画卡通设定图，轮廓清晰，色彩明快，易于后续复用。'),
  styleTemplate('realistic-ancient', '真人古装', '古装实拍短剧质感，服化道和场景更接近真人剧。', '真人古装影视质感，古代服饰、发冠、布料和道具真实可信，电影布光。'),
  styleTemplate('xianxia-3d', '3D玄幻', '3D角色、玄幻世界、体积光和奇观场景。', '3D东方玄幻动画，精致角色建模，体积光，云海秘境，法器灵光，材质统一。'),
  styleTemplate('realistic-3d', '3D写实', '3D写实角色和真实材质，适合偏电影化画面。', '3D写实动画，真实材质和皮肤细节，电影级灯光，景深明确。'),
  styleTemplate('cinematic-2d', '2D电影', '2D动画电影感，强调构图、光影和情绪氛围。', '2D动画电影质感，精致背景，美术分层明确，电影构图，统一光影和色调。'),
  styleTemplate('blockbuster', '好莱坞大片', '高对比电影光、强冲突、动作大片气质。', '商业大片电影质感，高对比光影，强透视构图，动作张力，真实烟尘和氛围。'),
  styleTemplate('q-3d', '3DQ版', '3D大头比例、圆润可爱、适合轻松向短剧。', '3D Q版动画，大头比例，圆润造型，清晰可爱表情，材质柔和。', ['1:1', '9:16', '16:9']),
  styleTemplate('korean-2d', '2D韩式动画', '柔和线条、清爽人物、现代浪漫短剧感。', '韩式2D动画风格，柔和人物线条，干净上色，清爽现代光影。'),
  styleTemplate('fantasy-2d', '2D奇幻动画', '2D奇幻场景、魔法光效、适合玄幻冒险。', '2D奇幻动画，魔法光效，层次丰富的背景，清晰角色轮廓。'),
  styleTemplate('retro-wuxia', '真人复古武侠', '复古武侠实拍感，胶片色、竹林、客栈和江湖氛围。', '真人复古武侠电影质感，胶片颗粒，低饱和色彩，竹林客栈江湖氛围。'),
  styleTemplate('japanese-3d-2d', '日式3D渲染2D', '3D模型加2D描边，适合动作和连续镜头。', '日式3D转2D渲染，toon shading，清晰描边，动画角色比例。'),
  styleTemplate('retro-hongkong', '真人复古港片', '霓虹街景、胶片颗粒、复古港片色彩。', '真人复古港片质感，霓虹街景，胶片颗粒，暖色街灯，高反差夜景。'),
  styleTemplate('hotblood-2d', '2D热血动画', '强动作线、鲜明色彩、适合战斗和爽点镜头。', '2D热血少年动画，强动作线，鲜明色彩，高能战斗构图。'),
  styleTemplate('yokai-urban', '2D灵怪都市', '都市夜景、灵异光效、怪谈和超自然气氛。', '2D灵怪都市动画，夜景霓虹，超自然青绿光效，阴影层次。'),
  styleTemplate('warm-healing-2d', '2D暖系动画', '暖色、自然、治愈感，适合日常和成长线。', '2D暖系治愈动画，柔和自然光，温暖色彩，细腻背景。'),
  styleTemplate('toon-3d-2d', '3D渲染2D', '3D体积和2D描边结合，稳定适合多镜头。', '3D模型2D化渲染，清晰描边，柔和卡通材质，稳定角色轮廓。'),
  styleTemplate('q-2d', '2DQ版', '2D大头比例、表情可爱、适合轻喜剧和口播短剧。', '2D Q版动画，大头比例，表情清楚，线条干净，色彩明快。', ['1:1', '9:16', '16:9']),
  styleTemplate('dark-fantasy-2d', '2D暗黑奇幻', '暗色调、阴影、怪物和压迫感氛围。', '2D暗黑奇幻动画，低明度色彩，强阴影，怪物或秘境压迫感。'),
  styleTemplate('american-3d', '3D美式', '美式3D动画，夸张表情、圆润造型、清晰动作。', '美式3D动画风格，夸张但清晰的表情，圆润建模，明亮材质。'),
  styleTemplate('retro-2d', '2D复古动画', '胶片颗粒、复古配色、老动画质感。', '2D复古动画风格，胶片颗粒，复古配色，简洁背景。'),
  styleTemplate('american-2d', '2D美式动画', '美式2D动画，形体夸张、色块清晰。', '美式2D动画，粗细分明的线条，色块清楚，动作夸张。'),
  styleTemplate('retro-girl-2d', '2D复古少女', '复古少女漫画感，柔和表情、梦幻色彩。', '2D复古少女漫画风格，柔和五官，梦幻色彩，细腻头发和眼睛。', ['3:4', '9:16', '16:9']),
  styleTemplate('manga-hotblood-2d', '2D热血漫画', '漫画分镜感、速度线、强冲突动作。', '2D热血漫画风，速度线，夸张透视，强冲突动作。'),
  styleTemplate('retro-family-2d', '2D复古名作', '经典家庭向动画质感，温和、清楚、低门槛。', '经典复古家庭向2D动画，简洁线条，温和配色，人物表情清楚。'),
  styleTemplate('ink-manga-2d', '2D黑白墨线', '黑白漫画线稿、强阴影，适合悬疑和情绪镜头。', '2D黑白墨线漫画风，强线条和网点阴影，画面对比清晰。'),
  styleTemplate('flamboyant-2d', '2D强风格漫画', '高饱和、强姿态、夸张构图和戏剧化光影。', '2D强风格漫画，高饱和色彩，戏剧化姿态，强构图。'),
  styleTemplate('detective-2d', '2D日式侦探', '城市、推理、冷色调，适合悬疑推理线。', '2D日式侦探动画，城市街巷，冷色调，推理悬疑氛围。'),
  styleTemplate('sports-2d', '2D运动少年', '校园运动、动态姿势、汗水和热血氛围。', '2D运动少年动画，动态姿势，清晰运动服，汗水和场馆光影。'),
  styleTemplate('vintage-master-2d', '2D昭和复古', '早期手绘动画质感，朴素线条、复古纸面色。', '昭和复古2D手绘动画，朴素线条，纸面质感，低饱和配色。'),
  styleTemplate('thick-line-2d', '2D粗线条', '粗黑轮廓、强色块、适合喜剧和夸张动作。', '2D粗线条动画，强黑色轮廓，大色块，夸张动作。'),
  styleTemplate('lowpoly-3d', '3D块面', '低多边形块面、清晰材质、轻量游戏感。', '低多边形3D块面风格，清晰几何切面，简洁材质。'),
  styleTemplate('voxel-3d', '3D方块世界', '方块体素世界，适合轻松、游戏化内容。', '3D方块体素世界，方块角色和场景，清晰几何结构，明亮配色。'),
  styleTemplate('mobile-game-3d', '3D手游', '手游角色展示感，发光特效、清晰装备和战斗气氛。', '3D手游宣传动画风格，角色装备清晰，技能光效，场景层次明确。'),
  styleTemplate('limited-animation', '定格动画', '有限帧手作感，材质明显，适合实验和童话风。', '定格动画质感，手作材质，有限帧运动感，微小不完美纹理。'),
  styleTemplate('figure-stopmotion', '手办定格动画', '手办模型、微缩布景、真实灯光。', '手办定格动画，微缩布景，真实模型材质，手办关节和服装细节清楚。'),
  styleTemplate('clay-stopmotion', '粘土定格动画', '粘土人物和道具，软质手工纹理。', '粘土定格动画，软质粘土纹理，手工塑形痕迹。'),
  styleTemplate('brick-stopmotion', '积木定格动画', '积木人物和积木场景，轻松玩具感。', '积木定格动画，积木人偶和模块化场景，玩具材质。'),
  styleTemplate('thread-stopmotion', '手线定格动画', '线稿加手作拼贴，粗糙、有趣、实验感。', '手线定格动画，手绘线条与拼贴材质，轻微抖动感。'),
  styleTemplate('rubberhose-2d', '2D橡皮管动画', '复古橡皮管四肢、黑白卡通、弹性动作。', '2D橡皮管复古动画，弹性四肢，圆眼表情，黑白或少量点缀色。'),
  styleTemplate('pixel-2d', '2D像素', '像素角色、方格场景，适合游戏化短片。', '2D像素动画，清晰像素网格，有限调色板，角色和道具像素轮廓保持一致。', ['1:1', '16:9', '9:16']),
  styleTemplate('gongbi-2d', '2D工笔风', '国风工笔线条、细腻衣纹、淡雅色彩。', '2D国风工笔画风，细腻线条，淡雅设色，服饰纹样和场景器物清楚。', ['16:9', '9:16', '3:4']),
  styleTemplate('sketch-2d', '2D简笔画', '草图式线条，快速、轻量、适合概念预演。', '2D简笔草图风，少量线条表达人物和场景，画面干净。'),
  styleTemplate('watercolor-2d', '2D水彩', '水彩晕染、柔和边缘、适合情绪和文艺内容。', '2D水彩动画风格，柔和晕染，透明色层，温柔光影。', ['16:9', '9:16', '3:4']),
  styleTemplate('simple-line-2d', '2D简单线条', '极简线条、少色块，适合低成本解释和轻叙事。', '2D简单线条动画，极简轮廓，少量色块，构图清楚。'),
  styleTemplate('comic-us-2d', '2D美式漫画', '漫画分格、粗阴影、强对比和英雄感。', '2D美式漫画风，粗阴影，高对比，分格感构图。'),
  styleTemplate('shoujo-2d', '2D少女漫画', '柔光、细腻五官、恋爱和青春氛围。', '2D少女漫画风，柔光，细腻五官，明亮眼睛，青春氛围。', ['3:4', '9:16', '16:9']),
  styleTemplate('horror-ink-2d', '2D诡异惊悚', '黑白阴影、压迫感、适合惊悚悬疑。', '2D诡异惊悚漫画风，黑白强阴影，压迫构图，粗糙墨线。'),
];

type ImageStyleTemplatePickerProps = {
  templates: ImageStyleTemplate[];
  value: string;
  onChange: (style: string) => void;
  toMediaUrl?: (url?: string) => string;
  recommendedFor?: string;
  title?: string;
  compact?: boolean;
  layout?: 'grid' | 'inline';
};

const defaultToMediaUrl = (url?: string) => {
  if (!url) return '';
  if (/^https?:\/\//.test(url)) return url;
  const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1$/, '');
  return `${base}${url.startsWith('/') ? url : `/${url}`}`;
};

export function ImageStyleTemplatePicker({
  templates,
  value,
  onChange,
  toMediaUrl = defaultToMediaUrl,
  recommendedFor,
  title = '画面风格样例',
  compact = false,
  layout = 'grid',
}: ImageStyleTemplatePickerProps) {
  const filtered = recommendedFor
    ? templates.filter((template) => !template.recommended_for?.length || template.recommended_for.includes(recommendedFor))
    : templates;
  const visibleTemplates = filtered.length ? filtered : templates;

  if (!visibleTemplates.length) return null;

  const selectedTemplate = visibleTemplates.find((template) => template.style === value) || visibleTemplates[0];

  if (layout === 'inline') {
    const preferredStyles = [
      'anime',
      'xianxia',
      'wuxia',
      'fantasy',
      'urban',
      'cinematic-2d',
      'xianxia-3d',
      'realistic-3d',
    ];
    const quickTemplates = [
      ...preferredStyles
        .map((style) => visibleTemplates.find((template) => template.style === style))
        .filter(Boolean),
      selectedTemplate,
      ...visibleTemplates,
    ].reduce<ImageStyleTemplate[]>((items, template) => {
      if (!template || items.some((item) => item.style === template.style) || items.length >= 8) {
        return items;
      }
      return [...items, template];
    }, []);

    return (
      <div data-testid="image-style-template-inline" className="rounded-lg border border-white/10 bg-black/20 p-3">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-white">{title}</div>
              <div className="mt-1 max-w-2xl text-xs leading-5 text-white/45">
                选择后会把风格提示词带入参考图生成，优先保证同一小说、角色、场景和道具的画风统一。
              </div>
            </div>
            <Badge
              data-testid="image-style-template-current"
              variant="outline"
              className="border-violet-300/35 bg-violet-500/10 text-violet-50"
            >
              当前：{selectedTemplate?.label || value}
            </Badge>
          </div>

          <div className="space-y-3">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <div className="flex items-start gap-3">
                {selectedTemplate?.sample_url && (
                  <img
                    src={toMediaUrl(selectedTemplate.sample_url)}
                    alt={`${selectedTemplate.label}样例`}
                    className="h-16 w-24 shrink-0 rounded-md border border-white/10 object-cover"
                    loading="eager"
                  />
                )}
                <div className="min-w-0">
                  <div className="text-sm font-medium text-white">{selectedTemplate?.label || value}</div>
                  {selectedTemplate?.description && (
                    <div className="mt-1 line-clamp-2 text-xs leading-5 text-white/55">{selectedTemplate.description}</div>
                  )}
                  {selectedTemplate?.prompt && (
                    <div className="mt-1 line-clamp-1 text-[11px] leading-5 text-white/35">{selectedTemplate.prompt}</div>
                  )}
                </div>
              </div>
            </div>

            <label className="space-y-1 text-xs text-white/55">
              <span>更多风格</span>
              <select
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              >
                {visibleTemplates.map((template) => (
                  <option key={template.style} value={template.style} className="bg-slate-950">
                    {template.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            {quickTemplates.map((template) => {
              const selected = template.style === value;
              const sampleUrl = toMediaUrl(template.sample_url);
              return (
                <button
                  key={template.style}
                  type="button"
                  data-testid="image-style-template"
                  aria-pressed={selected}
                  onClick={() => onChange(template.style)}
                  className={`flex min-h-10 items-center gap-2 rounded-full border py-1 pl-1 pr-3 text-sm transition ${
                    selected
                      ? 'border-violet-300 bg-violet-500/25 text-white shadow-[0_0_0_1px_rgba(196,181,253,0.3)]'
                      : 'border-white/10 bg-white/[0.04] text-white/70 hover:border-white/25 hover:bg-white/[0.08] hover:text-white'
                  }`}
                >
                  {sampleUrl ? (
                    <img
                      src={sampleUrl}
                      alt={`${template.label}样例`}
                      className="h-8 w-10 rounded-full object-cover"
                      loading="eager"
                    />
                  ) : (
                    <span className="flex h-8 w-10 items-center justify-center rounded-full bg-white/5 text-[10px] text-white/35">
                      样例
                    </span>
                  )}
                  <span>{template.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-white">{title}</div>
          <div className="mt-0.5 text-xs text-white/45">选择后会把对应风格提示词带入 AI 生图，保持封面、角色、场景和道具画风统一。</div>
        </div>
        <Badge variant="outline" className="border-violet-300/30 text-violet-100">
          当前：{selectedTemplate?.label || value}
        </Badge>
      </div>
      <div className={`grid grid-cols-2 gap-3 ${compact ? 'md:grid-cols-3 xl:grid-cols-5' : 'md:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-6'}`}>
        {visibleTemplates.map((template) => {
          const selected = template.style === value;
          const sampleUrl = toMediaUrl(template.sample_url);
          return (
            <button
              key={template.style}
              type="button"
              data-testid="image-style-template"
              aria-pressed={selected}
              onClick={() => onChange(template.style)}
              className={`group overflow-hidden rounded-xl border text-left transition ${
                selected
                  ? 'border-violet-300 bg-violet-500/15 shadow-[0_0_0_1px_rgba(196,181,253,0.4)]'
                  : 'border-white/10 bg-white/[0.04] hover:border-white/25 hover:bg-white/[0.07]'
              }`}
            >
              <div className={`relative overflow-hidden bg-white/5 ${compact ? 'aspect-[4/3]' : 'aspect-[16/10]'}`}>
                <div className="absolute left-0 top-0 z-10 rounded-br-md bg-orange-500 px-1.5 py-0.5 text-[11px] font-medium text-white">
                  精选
                </div>
                <div className="h-full w-full">
                  {sampleUrl ? (
                    <img
                      src={sampleUrl}
                      alt={`${template.label}样例`}
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                      loading="eager"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-xs text-white/30">样例</div>
                  )}
                </div>
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/55 to-transparent px-2 pb-2 pt-8">
                  <div className="flex items-center justify-between gap-1">
                    <span className="truncate text-sm font-medium text-white">{template.label}</span>
                    {selected && (
                      <Badge variant="outline" className="shrink-0 border-violet-200/60 bg-violet-500/25 text-[10px] text-violet-50">
                        已选
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
              {!compact && (
                <div className="space-y-1 p-2">
                  {template.description && <div className="line-clamp-2 text-xs leading-5 text-white/55">{template.description}</div>}
                  {template.prompt && <div className="line-clamp-2 text-[11px] leading-5 text-white/35">{template.prompt}</div>}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
