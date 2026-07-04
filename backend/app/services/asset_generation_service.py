"""
资产生成服务
支持角色、场景、道具等资产的AI生成和版本管理
"""
from copy import deepcopy
from types import SimpleNamespace
from typing import Dict, List, Optional, Any
from uuid import uuid4
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_utils import create_image_generation_service, get_user_image_model_config
from app.core.dev_generation import dev_image_url, is_dev_mode
from app.core.time_utils import utc_now
from app.models.asset import Asset
from app.services.image_generation_pipeline import (
    call_image_generation_provider,
    missing_image_result_message,
    provider_task_id,
)
from app.services.asset_model_capabilities import decide_asset_generation_strategy
from app.services.image_prompt_policy import (
    CHARACTER_SINGLE_VIEW_CONSTRAINT,
    PROP_VIEW_CONSTRAINT,
    SCENE_VIEW_CONSTRAINT,
    append_global_image_constraints,
    build_visual_contract,
    entity_view_prompt,
    is_composite_character_name,
)
from app.services.asset_visual_contract import build_visual_contract_from_story
from app.services.asset_visual_review import review_asset_against_contract, retry_prompt_advice
from app.services.image_result_parser import extract_image_urls_from_provider_result
from app.services.media_persistence import persist_remote_media_url
from app.services.prompt_skill_service import apply_active_prompt_skill_template


IMAGE_STYLE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "style": "realistic",
        "label": "真人写实",
        "description": "真实演员质感、自然皮肤、电影镜头和现实光影。",
        "sample_url": "/static/starter/style-realistic-reference.png",
        "aspect_ratios": ["16:9", "9:16", "3:4"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "真人写实电影质感，真实演员外观，自然皮肤纹理，真实服装材质，电影级布光和景深，保持同一视觉设定。",
    },
    {
        "style": "xianxia",
        "label": "修仙仙侠",
        "description": "东方修仙、灵气、法器、仙门服饰和秘境氛围。",
        "sample_url": "/static/starter/style-xianxia-reference.png",
        "aspect_ratios": ["9:16", "16:9"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "东方修仙动画设定图，灵气氛围，飘逸服饰，仙侠质感，统一世界观。",
    },
    {
        "style": "wuxia",
        "label": "武侠江湖",
        "description": "江湖、刀剑、客栈、竹林、低饱和电影感。",
        "sample_url": "/static/starter/style-wuxia-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "武侠动画设定图，江湖质感，利落服饰，电影感构图，统一世界观。",
    },
    {
        "style": "fantasy",
        "label": "东方玄幻",
        "description": "秘境、遗迹、符文、史诗感和强视觉奇观。",
        "sample_url": "/static/starter/style-fantasy-reference.png",
        "aspect_ratios": ["16:9", "21:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "东方玄幻动画设定图，史诗感，细节丰富，统一美术风格。",
    },
    {
        "style": "urban",
        "label": "现代都市",
        "description": "现代短剧、城市环境、现实光影和清晰人物造型。",
        "sample_url": "/static/starter/style-urban-reference.png",
        "aspect_ratios": ["9:16", "16:9", "3:4"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "现代都市动画设定图，清晰造型，现实光影，统一美术风格。",
    },
    {
        "style": "anime",
        "label": "2D动画",
        "description": "干净线稿、稳定上色、适合通用动漫短剧。",
        "sample_url": "/static/starter/style-anime-reference.png",
        "aspect_ratios": ["9:16", "16:9", "3:4"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "2D日系动画设定图，干净线稿，高质量上色，清晰角色轮廓，统一角色设定，适合动漫短剧制作。",
    },
    {
        "style": "cartoon",
        "label": "卡通明快",
        "description": "轮廓清晰、色彩明快，适合轻松日常或轻喜剧。",
        "sample_url": "/static/starter/style-cartoon-reference.png",
        "aspect_ratios": ["9:16", "1:1", "16:9"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "动画卡通设定图，轮廓清晰，色彩明快，易于后续复用，角色造型保持一致。",
    },
    {
        "style": "realistic-ancient",
        "label": "真人古装",
        "description": "古装实拍短剧质感，服化道和场景更接近真人剧。",
        "sample_url": "/static/starter/style-realistic-ancient-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "真人古装影视质感，古代服饰、发冠、布料和道具真实可信，电影布光，保持角色和场景连续性。",
    },
    {
        "style": "xianxia-3d",
        "label": "3D玄幻",
        "description": "3D角色、玄幻世界、体积光和奇观场景。",
        "sample_url": "/static/starter/style-xianxia-3d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "3D东方玄幻动画，精致角色建模，体积光，云海秘境，法器灵光，材质统一，适合连续动漫短剧。",
    },
    {
        "style": "realistic-3d",
        "label": "3D写实",
        "description": "3D写实角色和真实材质，适合偏电影化画面。",
        "sample_url": "/static/starter/style-realistic-3d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "3D写实动画，真实材质和皮肤细节，电影级灯光，景深明确，角色外观和环境设定保持一致。",
    },
    {
        "style": "cinematic-2d",
        "label": "2D电影",
        "description": "2D动画电影感，强调构图、光影和情绪氛围。",
        "sample_url": "/static/starter/style-cinematic-2d-reference.png",
        "aspect_ratios": ["16:9", "21:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "2D动画电影质感，精致背景，美术分层明确，电影构图，统一光影和色调，适合叙事镜头。",
    },
    {
        "style": "blockbuster",
        "label": "好莱坞大片",
        "description": "高对比电影光、强冲突、动作大片气质。",
        "sample_url": "/static/starter/style-blockbuster-reference.png",
        "aspect_ratios": ["16:9", "21:9", "9:16"],
        "recommended_for": ["scene", "prop", "cover", "shot"],
        "prompt": "商业大片电影质感，高对比光影，强透视构图，动作张力，真实烟尘和氛围，保持同一镜头语言。",
    },
    {
        "style": "q-3d",
        "label": "3DQ版",
        "description": "3D大头比例、圆润可爱、适合轻松向短剧。",
        "sample_url": "/static/starter/style-q-3d-reference.png",
        "aspect_ratios": ["1:1", "9:16", "16:9"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "3D Q版动画，大头比例，圆润造型，清晰可爱表情，材质柔和，角色服装和配色保持一致。",
    },
    {
        "style": "korean-2d",
        "label": "2D韩式动画",
        "description": "柔和线条、清爽人物、现代浪漫短剧感。",
        "sample_url": "/static/starter/style-korean-2d-reference.png",
        "aspect_ratios": ["9:16", "16:9", "3:4"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "韩式2D动画风格，柔和人物线条，干净上色，清爽现代光影，人物发型和服装保持一致。",
    },
    {
        "style": "fantasy-2d",
        "label": "2D奇幻动画",
        "description": "2D奇幻场景、魔法光效、适合玄幻冒险。",
        "sample_url": "/static/starter/style-fantasy-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "2D奇幻动画，魔法光效，层次丰富的背景，清晰角色轮廓，统一奇幻世界观和色彩体系。",
    },
    {
        "style": "retro-wuxia",
        "label": "真人复古武侠",
        "description": "复古武侠实拍感，胶片色、竹林、客栈和江湖氛围。",
        "sample_url": "/static/starter/style-retro-wuxia-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "真人复古武侠电影质感，胶片颗粒，低饱和色彩，竹林客栈江湖氛围，服化道保持连续。",
    },
    {
        "style": "japanese-3d-2d",
        "label": "日式3D渲染2D",
        "description": "3D模型加2D描边，适合动作和连续镜头。",
        "sample_url": "/static/starter/style-japanese-3d-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "日式3D转2D渲染，toon shading，清晰描边，动画角色比例，动作镜头稳定，角色服饰和配色一致。",
    },
    {
        "style": "retro-hongkong",
        "label": "真人复古港片",
        "description": "霓虹街景、胶片颗粒、复古港片色彩。",
        "sample_url": "/static/starter/style-retro-hongkong-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "真人复古港片质感，霓虹街景，胶片颗粒，暖色街灯，高反差夜景，角色造型保持连续。",
    },
    {
        "style": "hotblood-2d",
        "label": "2D热血动画",
        "description": "强动作线、鲜明色彩、适合战斗和爽点镜头。",
        "sample_url": "/static/starter/style-hotblood-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "2D热血少年动画，强动作线，鲜明色彩，高能战斗构图，表情夸张但角色设定保持一致。",
    },
    {
        "style": "yokai-urban",
        "label": "2D灵怪都市",
        "description": "都市夜景、灵异光效、怪谈和超自然气氛。",
        "sample_url": "/static/starter/style-yokai-urban-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "2D灵怪都市动画，夜景霓虹，超自然青绿光效，阴影层次，人物轮廓和怪谈氛围统一。",
    },
    {
        "style": "warm-healing-2d",
        "label": "2D暖系动画",
        "description": "暖色、自然、治愈感，适合日常和成长线。",
        "sample_url": "/static/starter/style-warm-healing-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D暖系治愈动画，柔和自然光，温暖色彩，细腻背景，人物表情自然，适合连续日常叙事。",
    },
    {
        "style": "toon-3d-2d",
        "label": "3D渲染2D",
        "description": "3D体积和2D描边结合，稳定适合多镜头。",
        "sample_url": "/static/starter/style-toon-3d-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "3D模型2D化渲染，清晰描边，柔和卡通材质，稳定角色轮廓和服装细节，便于多镜头复用。",
    },
    {
        "style": "q-2d",
        "label": "2DQ版",
        "description": "2D大头比例、表情可爱、适合轻喜剧和口播短剧。",
        "sample_url": "/static/starter/style-q-2d-reference.png",
        "aspect_ratios": ["1:1", "9:16", "16:9"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D Q版动画，大头比例，表情清楚，线条干净，色彩明快，角色服装和主要特征保持一致。",
    },
    {
        "style": "dark-fantasy-2d",
        "label": "2D暗黑奇幻",
        "description": "暗色调、阴影、怪物和压迫感氛围。",
        "sample_url": "/static/starter/style-dark-fantasy-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "2D暗黑奇幻动画，低明度色彩，强阴影，怪物或秘境压迫感，角色轮廓和关键道具清晰。",
    },
    {
        "style": "american-3d",
        "label": "3D美式",
        "description": "美式3D动画，夸张表情、圆润造型、清晰动作。",
        "sample_url": "/static/starter/style-american-3d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "美式3D动画风格，夸张但清晰的表情，圆润建模，明亮材质，角色外观稳定。",
    },
    {
        "style": "retro-2d",
        "label": "2D复古动画",
        "description": "胶片颗粒、复古配色、老动画质感。",
        "sample_url": "/static/starter/style-retro-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D复古动画风格，胶片颗粒，复古配色，简洁背景，角色线条稳定，保持老动画质感。",
    },
    {
        "style": "american-2d",
        "label": "2D美式动画",
        "description": "美式2D动画，形体夸张、色块清晰。",
        "sample_url": "/static/starter/style-american-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "美式2D动画，粗细分明的线条，色块清楚，动作夸张，人物轮廓和服装颜色保持一致。",
    },
    {
        "style": "retro-girl-2d",
        "label": "2D复古少女",
        "description": "复古少女漫画感，柔和表情、梦幻色彩。",
        "sample_url": "/static/starter/style-retro-girl-2d-reference.png",
        "aspect_ratios": ["3:4", "9:16", "16:9"],
        "recommended_for": ["character", "cover", "avatar", "shot"],
        "prompt": "2D复古少女漫画风格，柔和五官，梦幻色彩，细腻头发和眼睛，角色设定保持一致。",
    },
    {
        "style": "manga-hotblood-2d",
        "label": "2D热血漫画",
        "description": "漫画分镜感、速度线、强冲突动作。",
        "sample_url": "/static/starter/style-manga-hotblood-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "shot"],
        "prompt": "2D热血漫画风，速度线，夸张透视，强冲突动作，黑白和彩色阴影结合，角色特征保持一致。",
    },
    {
        "style": "retro-family-2d",
        "label": "2D复古名作",
        "description": "经典家庭向动画质感，温和、清楚、低门槛。",
        "sample_url": "/static/starter/style-retro-family-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "经典复古家庭向2D动画，简洁线条，温和配色，人物表情清楚，画面易读，保持连续性。",
    },
    {
        "style": "ink-manga-2d",
        "label": "2D黑白墨线",
        "description": "黑白漫画线稿、强阴影，适合悬疑和情绪镜头。",
        "sample_url": "/static/starter/style-ink-manga-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "2D黑白墨线漫画风，强线条和网点阴影，画面对比清晰，人物轮廓、道具和场景结构保持一致。",
    },
    {
        "style": "flamboyant-2d",
        "label": "2D强风格漫画",
        "description": "高饱和、强姿态、夸张构图和戏剧化光影。",
        "sample_url": "/static/starter/style-flamboyant-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D强风格漫画，高饱和色彩，戏剧化姿态，强构图，夸张表情但角色形象保持一致。",
    },
    {
        "style": "detective-2d",
        "label": "2D日式侦探",
        "description": "城市、推理、冷色调，适合悬疑推理线。",
        "sample_url": "/static/starter/style-detective-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "2D日式侦探动画，城市街巷，冷色调，推理悬疑氛围，人物服装和关键线索道具保持一致。",
    },
    {
        "style": "sports-2d",
        "label": "2D运动少年",
        "description": "校园运动、动态姿势、汗水和热血氛围。",
        "sample_url": "/static/starter/style-sports-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D运动少年动画，动态姿势，清晰运动服，汗水和场馆光影，角色体型和服装号码保持一致。",
    },
    {
        "style": "vintage-master-2d",
        "label": "2D昭和复古",
        "description": "早期手绘动画质感，朴素线条、复古纸面色。",
        "sample_url": "/static/starter/style-vintage-master-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "昭和复古2D手绘动画，朴素线条，纸面质感，低饱和配色，人物比例和场景元素保持一致。",
    },
    {
        "style": "thick-line-2d",
        "label": "2D粗线条",
        "description": "粗黑轮廓、强色块、适合喜剧和夸张动作。",
        "sample_url": "/static/starter/style-thick-line-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D粗线条动画，强黑色轮廓，大色块，夸张动作，画面易读，角色形状保持一致。",
    },
    {
        "style": "lowpoly-3d",
        "label": "3D块面",
        "description": "低多边形块面、清晰材质、轻量游戏感。",
        "sample_url": "/static/starter/style-lowpoly-3d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "低多边形3D块面风格，清晰几何切面，简洁材质，统一角色和场景造型，适合轻量动画。",
    },
    {
        "style": "voxel-3d",
        "label": "3D方块世界",
        "description": "方块体素世界，适合轻松、游戏化内容。",
        "sample_url": "/static/starter/style-voxel-3d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "3D方块体素世界，方块角色和场景，清晰几何结构，明亮配色，角色装备和场景方块规则一致。",
    },
    {
        "style": "mobile-game-3d",
        "label": "3D手游",
        "description": "手游角色展示感，发光特效、清晰装备和战斗气氛。",
        "sample_url": "/static/starter/style-mobile-game-3d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "3D手游宣传动画风格，角色装备清晰，技能光效，场景层次明确，适合玄幻战斗短剧。",
    },
    {
        "style": "limited-animation",
        "label": "定格动画",
        "description": "有限帧手作感，材质明显，适合实验和童话风。",
        "sample_url": "/static/starter/style-limited-animation-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "定格动画质感，手作材质，有限帧运动感，微小不完美纹理，角色和道具形状保持一致。",
    },
    {
        "style": "figure-stopmotion",
        "label": "手办定格动画",
        "description": "手办模型、微缩布景、真实灯光。",
        "sample_url": "/static/starter/style-figure-stopmotion-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "手办定格动画，微缩布景，真实模型材质，手办关节和服装细节清楚，灯光统一。",
    },
    {
        "style": "clay-stopmotion",
        "label": "粘土定格动画",
        "description": "粘土人物和道具，软质手工纹理。",
        "sample_url": "/static/starter/style-clay-stopmotion-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "粘土定格动画，软质粘土纹理，手工塑形痕迹，角色轮廓和颜色保持一致。",
    },
    {
        "style": "brick-stopmotion",
        "label": "积木定格动画",
        "description": "积木人物和积木场景，轻松玩具感。",
        "sample_url": "/static/starter/style-brick-stopmotion-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "积木定格动画，积木人偶和模块化场景，玩具材质，角色服装颜色和道具结构保持一致。",
    },
    {
        "style": "thread-stopmotion",
        "label": "手线定格动画",
        "description": "线稿加手作拼贴，粗糙、有趣、实验感。",
        "sample_url": "/static/starter/style-thread-stopmotion-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "手线定格动画，手绘线条与拼贴材质，轻微抖动感，角色轮廓和关键道具保持一致。",
    },
    {
        "style": "rubberhose-2d",
        "label": "2D橡皮管动画",
        "description": "复古橡皮管四肢、黑白卡通、弹性动作。",
        "sample_url": "/static/starter/style-rubberhose-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D橡皮管复古动画，弹性四肢，圆眼表情，黑白或少量点缀色，角色形状保持一致。",
    },
    {
        "style": "pixel-2d",
        "label": "2D像素",
        "description": "像素角色、方格场景，适合游戏化短片。",
        "sample_url": "/static/starter/style-pixel-2d-reference.png",
        "aspect_ratios": ["1:1", "16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "2D像素动画，清晰像素网格，有限调色板，角色和道具像素轮廓保持一致。",
    },
    {
        "style": "gongbi-2d",
        "label": "2D工笔风",
        "description": "国风工笔线条、细腻衣纹、淡雅色彩。",
        "sample_url": "/static/starter/style-gongbi-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "3:4"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "2D国风工笔画风，细腻线条，淡雅设色，服饰纹样和场景器物清楚，统一古典气质。",
    },
    {
        "style": "sketch-2d",
        "label": "2D简笔画",
        "description": "草图式线条，快速、轻量、适合概念预演。",
        "sample_url": "/static/starter/style-sketch-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "2D简笔草图风，少量线条表达人物和场景，画面干净，角色外观要素保持一致。",
    },
    {
        "style": "watercolor-2d",
        "label": "2D水彩",
        "description": "水彩晕染、柔和边缘、适合情绪和文艺内容。",
        "sample_url": "/static/starter/style-watercolor-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "3:4"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D水彩动画风格，柔和晕染，透明色层，温柔光影，人物造型和场景色调保持一致。",
    },
    {
        "style": "simple-line-2d",
        "label": "2D简单线条",
        "description": "极简线条、少色块，适合低成本解释和轻叙事。",
        "sample_url": "/static/starter/style-simple-line-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "recommended_for": ["character", "scene", "prop", "cover", "avatar", "shot"],
        "prompt": "2D简单线条动画，极简轮廓，少量色块，构图清楚，角色标志性特征保持一致。",
    },
    {
        "style": "comic-us-2d",
        "label": "2D美式漫画",
        "description": "漫画分格、粗阴影、强对比和英雄感。",
        "sample_url": "/static/starter/style-comic-us-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D美式漫画风，粗阴影，高对比，分格感构图，角色轮廓和服装色块保持一致。",
    },
    {
        "style": "shoujo-2d",
        "label": "2D少女漫画",
        "description": "柔光、细腻五官、恋爱和青春氛围。",
        "sample_url": "/static/starter/style-shoujo-2d-reference.png",
        "aspect_ratios": ["3:4", "9:16", "16:9"],
        "recommended_for": ["character", "scene", "cover", "avatar", "shot"],
        "prompt": "2D少女漫画风，柔光，细腻五官，明亮眼睛，青春氛围，角色发型和服饰保持一致。",
    },
    {
        "style": "horror-ink-2d",
        "label": "2D诡异惊悚",
        "description": "黑白阴影、压迫感、适合惊悚悬疑。",
        "sample_url": "/static/starter/style-horror-ink-2d-reference.png",
        "aspect_ratios": ["16:9", "9:16"],
        "recommended_for": ["character", "scene", "prop", "cover", "shot"],
        "prompt": "2D诡异惊悚漫画风，黑白强阴影，压迫构图，粗糙墨线，人物轮廓和关键场景元素保持一致。",
    },
]


def get_image_style_templates() -> List[Dict[str, Any]]:
    return deepcopy(IMAGE_STYLE_TEMPLATES)


def style_keywords_for(style: str) -> str:
    normalized = (style or "").strip()
    for template in IMAGE_STYLE_TEMPLATES:
        if template["style"] == normalized:
            return template["prompt"]
    for template in IMAGE_STYLE_TEMPLATES:
        if template["style"] == "anime":
            return template["prompt"]
    return IMAGE_STYLE_TEMPLATES[0]["prompt"]


ASSET_VIEW_PRESETS: Dict[str, Dict[str, Any]] = {
    "character": {
        "entity_type": "character",
        "category": "character",
        "title": "角色三视图",
        "description": "用于锁定角色外观、服装、发型和体型，后续镜头生成保持同一人物。",
        "recommended_aspect_ratios": ["9:16", "3:4", "1:1"],
        "style_examples": [
            {
                "style": "xianxia",
                "label": "修仙仙侠",
                "aspect_ratio": "9:16",
                "sample_url": "/static/starter/character-xianxia-reference.png",
                "prompt": "东方修仙动漫角色设定图，完整头身，仙门服饰，发型、法器、衣纹统一，干净线稿，高质量二次元。",
            },
            {
                "style": "wuxia",
                "label": "武侠江湖",
                "aspect_ratio": "9:16",
                "sample_url": "/static/starter/character-wuxia-reference.png",
                "prompt": "武侠江湖动漫角色三视图，劲装、佩剑、束发和身形比例清晰，低饱和电影感色彩。",
            },
            {
                "style": "urban",
                "label": "现代都市",
                "aspect_ratio": "9:16",
                "sample_url": "/static/starter/character-urban-reference.png",
                "prompt": "现代都市动漫角色设定图，日常服装、发型、表情和体型统一，适合短剧连续镜头。",
            },
        ],
        "views": [
            {
                "key": "front",
                "label": "正面",
                "aspect_ratio": "9:16",
                "size": "2k_w",
                "prompt_hint": "正面站姿，完整头身比例、发型、五官、服装和主要配饰清晰可见。",
            },
            {
                "key": "side",
                "label": "侧面",
                "aspect_ratio": "9:16",
                "size": "2k_w",
                "prompt_hint": "严格侧面站姿，保持同一人物五官、发型、体型和服装结构，只展示单侧轮廓与配饰位置。",
            },
            {
                "key": "back",
                "label": "背面",
                "aspect_ratio": "9:16",
                "size": "2k_w",
                "prompt_hint": "背对镜头的背面站姿，脸部不可见，保持同一套服装、发型、背部轮廓、武器或披风等背面细节。",
            },
        ],
    },
    "scene": {
        "entity_type": "scene",
        "category": "scene",
        "title": "场景四视图",
        "description": "用于固定空间结构、光影和关键区域，保证同一场景跨镜头连续。",
        "recommended_aspect_ratios": ["16:9", "21:9", "9:16"],
        "style_examples": [
            {
                "style": "xianxia",
                "label": "修仙仙侠",
                "aspect_ratio": "16:9",
                "sample_url": "/static/starter/scene-xianxia-reference.png",
                "prompt": "仙门山门场景设定，全景定场，云海、石阶、牌楼、灵光统一，适合修仙短剧镜头连续使用。",
            },
            {
                "style": "wuxia",
                "label": "武侠江湖",
                "aspect_ratio": "16:9",
                "sample_url": "/static/starter/scene-wuxia-reference.png",
                "prompt": "武侠客栈或竹林山道场景设定，空间入口、行动区、光影方向明确，江湖氛围浓厚。",
            },
            {
                "style": "fantasy",
                "label": "东方玄幻",
                "aspect_ratio": "16:9",
                "sample_url": "/static/starter/scene-fantasy-reference.png",
                "prompt": "东方玄幻秘境场景，巨石遗迹、符文、雾气和远景层次稳定，便于多镜头复用。",
            },
        ],
        "views": [
            {
                "key": "establishing",
                "label": "全景定场",
                "aspect_ratio": "16:9",
                "size": "3k",
                "prompt_hint": "远景或大全景，展示场景整体空间、入口、地标和环境氛围。",
            },
            {
                "key": "layout",
                "label": "空间布局",
                "aspect_ratio": "16:9",
                "size": "3k",
                "prompt_hint": "中景视角，明确主要行动区、人物站位区域、通道和遮挡关系。",
            },
            {
                "key": "detail",
                "label": "关键细节",
                "aspect_ratio": "16:9",
                "size": "2k",
                "prompt_hint": "近景细节，展示纹理、符号、陈设、门窗、地面或核心视觉记忆点。",
            },
            {
                "key": "lighting",
                "label": "光影氛围",
                "aspect_ratio": "16:9",
                "size": "2k",
                "prompt_hint": "同一场景的光线、天气、时间段和色调参考，供后续镜头统一氛围。",
            },
        ],
    },
    "prop": {
        "entity_type": "prop",
        "category": "prop",
        "title": "道具多视图",
        "description": "用于固定道具外观、比例、材质和使用状态，避免关键道具跨镜头变形。",
        "recommended_aspect_ratios": ["1:1", "4:3", "16:9"],
        "style_examples": [
            {
                "style": "xianxia",
                "label": "修仙仙侠",
                "aspect_ratio": "1:1",
                "sample_url": "/static/starter/prop-xianxia-reference.png",
                "prompt": "修仙法宝道具设定图，主视图、纹理、灵光、比例清晰，材质和符文保持一致。",
            },
            {
                "style": "wuxia",
                "label": "武侠江湖",
                "aspect_ratio": "1:1",
                "sample_url": "/static/starter/prop-wuxia-reference.png",
                "prompt": "武侠刀剑或令牌道具设定，金属质感、磨损、尺寸比例和使用状态统一。",
            },
            {
                "style": "urban",
                "label": "现代都市",
                "aspect_ratio": "1:1",
                "sample_url": "/static/starter/prop-urban-reference.png",
                "prompt": "现代都市关键道具设定，外形、品牌符号、材质和手持比例清楚，适合短剧连续镜头。",
            },
        ],
        "views": [
            {
                "key": "main",
                "label": "主视图",
                "aspect_ratio": "1:1",
                "size": "1k",
                "prompt_hint": "道具完整主视图，外形、颜色、材质、核心符号清晰。",
            },
            {
                "key": "detail",
                "label": "细节纹理",
                "aspect_ratio": "1:1",
                "size": "1k",
                "prompt_hint": "局部特写，展示纹理、刻印、磨损、材质和重要结构。",
            },
            {
                "key": "scale",
                "label": "比例参考",
                "aspect_ratio": "1:1",
                "size": "1k",
                "prompt_hint": "展示道具相对人物手部或身体的尺寸比例，便于镜头保持大小一致。",
            },
            {
                "key": "in_use",
                "label": "使用状态",
                "aspect_ratio": "1:1",
                "size": "1k",
                "prompt_hint": "道具被角色持有或正在发挥作用的状态，保持主视图外观不变。",
            },
        ],
    },
}


def get_asset_view_presets() -> List[Dict[str, Any]]:
    return [deepcopy(ASSET_VIEW_PRESETS[key]) for key in ("character", "scene", "prop")]


def _view_key(asset: Asset) -> Optional[str]:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    value = params.get("view_key") or params.get("asset_subtype")
    return str(value) if value else None


class AssetGenerationService:
    """资产生成服务"""

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self.image_service: Optional[Any] = None
        self.provider_name = ""
        self.model_id = ""
        self.last_generation_failures: List[Asset] = []

    @staticmethod
    def _prompt_skill_task_for_entity(entity_type: str) -> str:
        return {
            "character": "character_image",
            "scene": "scene_reference_image",
            "prop": "prop_image",
        }.get(entity_type, "character_image")

    async def _apply_prompt_skill(
        self,
        *,
        task: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        result = await apply_active_prompt_skill_template(
            self.db,
            self.user_id,
            task=task,
            internal_prompt=prompt,
            context=context or {},
        )
        return result["prompt"]

    async def configure_image_model(self, model_config_id: Optional[str] = None):
        """Use the user's configured image-generation model."""
        api_key, provider_name, model_id, base_url = await get_user_image_model_config(
            self.db,
            self.user_id,
            config_id=model_config_id,
        )
        self.image_service = create_image_generation_service(api_key or "", provider_name or "", base_url)
        self.provider_name = provider_name or ""
        self.model_id = model_id or ""

    async def _generate_asset_image_url(
        self,
        prompt: str,
        *,
        size: str,
        aspect_ratio: str,
        prefix: str,
    ) -> str:
        if not self.image_service:
            try:
                await self.configure_image_model()
            except Exception:
                if not is_dev_mode():
                    raise
                return dev_image_url(f"{prefix}-{uuid4().hex[:8]}", prompt[:24] or prefix)

        result = await call_image_generation_provider(
            self.image_service,
            provider_name=self.provider_name,
            model_id=self.model_id,
            prompt=prompt,
            num=1,
            size=size,
            aspect_ratio=aspect_ratio,
            openai_size="1024x1024",
        )
        image_urls = extract_image_urls_from_provider_result(result)
        image_url = image_urls[0] if image_urls else None
        if not image_url:
            task_id = provider_task_id(result, provider_name=self.provider_name)
            raise ValueError(missing_image_result_message(self.provider_name, task_id))

        return await persist_remote_media_url(
            image_url,
            media_type="image",
            subdir="images",
            prefix=prefix,
            max_bytes=20 * 1024 * 1024,
        ) or image_url

    async def generate_character_assets(
        self,
        character_id: str,
        character_name: str,
        character_description: str,
        style: str = "anime",
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Asset]:
        """
        生成角色资产：头像、全身、表情、姿态

        Returns:
            Dict包含 avatar(头像), full_body(全身), expressions(表情集), poses(姿态集)
        """
        results = {}
        base_context = {
            "entity_id": character_id,
            "entity_type": "character",
            "entity_name": character_name,
            "character_name": character_name,
            "description": character_description or "",
            "character_description": character_description or "",
            "style": style,
        }

        # 1. 生成头像
        avatar_prompt = self._build_avatar_prompt(character_name, character_description, style)
        avatar_prompt = await self._apply_prompt_skill(
            task="character_image",
            prompt=avatar_prompt,
            context={**base_context, "asset_subtype": "avatar", "view_label": "头像"},
        )
        avatar_url = await self._generate_asset_image_url(
            avatar_prompt,
            size="1k",
            aspect_ratio="1:1",
            prefix=f"asset-avatar-{character_id[:8]}",
        )

        if avatar_url:
            avatar_asset = await self._create_asset(
                name=f"{character_name} 头像",
                category="character",
                asset_type="image",
                url=avatar_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=avatar_prompt,
                generation_params={"asset_subtype": "avatar", "style": style},
            )
            results["avatar"] = avatar_asset

        # 2. 生成全身图
        full_body_prompt = self._build_fullbody_prompt(character_name, character_description, style)
        full_body_prompt = await self._apply_prompt_skill(
            task="character_image",
            prompt=full_body_prompt,
            context={**base_context, "asset_subtype": "full_body", "view_label": "全身图"},
        )
        full_body_url = await self._generate_asset_image_url(
            full_body_prompt,
            size="2k_w",
            aspect_ratio="9:16",
            prefix=f"asset-fullbody-{character_id[:8]}",
        )

        if full_body_url:
            full_body_asset = await self._create_asset(
                name=f"{character_name} 全身图",
                category="character",
                asset_type="image",
                url=full_body_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=full_body_prompt,
                generation_params={"asset_subtype": "full_body", "style": style},
            )
            results["full_body"] = full_body_asset

        # 3. 生成表情集（开心、愤怒、悲伤、惊讶等）
        expressions_prompt = self._build_expressions_prompt(character_name, character_description, style)
        expressions_prompt = await self._apply_prompt_skill(
            task="character_image",
            prompt=expressions_prompt,
            context={**base_context, "asset_subtype": "expressions", "view_label": "表情集"},
        )
        expressions_url = await self._generate_asset_image_url(
            expressions_prompt,
            size="1k",
            aspect_ratio="1:1",
            prefix=f"asset-expression-{character_id[:8]}",
        )

        if expressions_url:
            expressions_asset = await self._create_asset(
                name=f"{character_name} 表情集",
                category="character",
                asset_type="image",
                url=expressions_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=expressions_prompt,
                expressions=[
                    {"name": "happy", "description": "开心", "url": expressions_url},
                ],
                generation_params={"asset_subtype": "expressions", "style": style},
            )
            results["expressions"] = expressions_asset

        # 4. 生成姿态集
        poses_prompt = self._build_poses_prompt(character_name, character_description, style)
        poses_prompt = await self._apply_prompt_skill(
            task="character_image",
            prompt=poses_prompt,
            context={**base_context, "asset_subtype": "poses", "view_label": "姿态集"},
        )
        poses_url = await self._generate_asset_image_url(
            poses_prompt,
            size="2k_w",
            aspect_ratio="9:16",
            prefix=f"asset-pose-{character_id[:8]}",
        )

        if poses_url:
            poses_asset = await self._create_asset(
                name=f"{character_name} 姿态集",
                category="character",
                asset_type="image",
                url=poses_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=poses_prompt,
                poses=[
                    {"name": "standing", "description": "站立", "url": poses_url},
                ],
                generation_params={"asset_subtype": "poses", "style": style},
            )
            results["poses"] = poses_asset

        return results

    async def generate_scene_assets(
        self,
        scene_id: str,
        scene_name: str,
        scene_description: str,
        style: str = "anime",
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Asset]:
        """
        生成场景资产：主场景、细节图、特效层

        Returns:
            Dict包含 main_scene(主场景), detail(细节图), effect(特效层)
        """
        results = {}
        base_context = {
            "entity_id": scene_id,
            "entity_type": "scene",
            "entity_name": scene_name,
            "scene_name": scene_name,
            "description": scene_description or "",
            "scene_description": scene_description or "",
            "style": style,
        }

        # 1. 生成主场景
        main_prompt = self._build_scene_prompt(scene_name, scene_description, style)
        main_prompt = await self._apply_prompt_skill(
            task="scene_reference_image",
            prompt=main_prompt,
            context={**base_context, "asset_subtype": "main_scene", "view_label": "主场景"},
        )
        main_url = await self._generate_asset_image_url(
            main_prompt,
            size="3k",
            aspect_ratio="16:9",
            prefix=f"asset-scene-{scene_id[:8]}",
        )

        if main_url:
            main_asset = await self._create_asset(
                name=f"{scene_name} 主场景",
                category="scene",
                asset_type="image",
                url=main_url,
                entity_id=scene_id,
                entity_type="scene",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=main_prompt,
                generation_params={"asset_subtype": "main_scene", "style": style},
            )
            results["main_scene"] = main_asset

        # 2. 生成细节图
        detail_prompt = self._build_scene_detail_prompt(scene_name, scene_description, style)
        detail_prompt = await self._apply_prompt_skill(
            task="scene_reference_image",
            prompt=detail_prompt,
            context={**base_context, "asset_subtype": "detail", "view_label": "细节图"},
        )
        detail_url = await self._generate_asset_image_url(
            detail_prompt,
            size="2k",
            aspect_ratio="16:9",
            prefix=f"asset-scene-detail-{scene_id[:8]}",
        )

        if detail_url:
            detail_asset = await self._create_asset(
                name=f"{scene_name} 细节图",
                category="scene",
                asset_type="image",
                url=detail_url,
                entity_id=scene_id,
                entity_type="scene",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=detail_prompt,
                generation_params={"asset_subtype": "detail", "style": style},
            )
            results["detail"] = detail_asset

        return results

    async def generate_prop_assets(
        self,
        prop_id: str,
        prop_name: str,
        prop_description: str,
        style: str = "anime",
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Asset]:
        """
        生成道具资产：道具主图、细节图

        Returns:
            Dict包含 main(道具主图), detail(细节图)
        """
        results = {}
        base_context = {
            "entity_id": prop_id,
            "entity_type": "prop",
            "entity_name": prop_name,
            "prop_name": prop_name,
            "description": prop_description or "",
            "prop_description": prop_description or "",
            "style": style,
        }

        # 1. 生成道具主图
        main_prompt = self._build_prop_prompt(prop_name, prop_description, style)
        main_prompt = await self._apply_prompt_skill(
            task="prop_image",
            prompt=main_prompt,
            context={**base_context, "asset_subtype": "main", "view_label": "主图"},
        )
        main_url = await self._generate_asset_image_url(
            main_prompt,
            size="1k",
            aspect_ratio="1:1",
            prefix=f"asset-prop-{prop_id[:8]}",
        )

        if main_url:
            main_asset = await self._create_asset(
                name=f"{prop_name} 主图",
                category="prop",
                asset_type="image",
                url=main_url,
                entity_id=prop_id,
                entity_type="prop",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=main_prompt,
                generation_params={"asset_subtype": "main", "style": style},
            )
            results["main"] = main_asset

        return results

    async def generate_entity_view_assets(
        self,
        *,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        entity_description: str,
        style: str = "anime",
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        script_id: Optional[str] = None,
        character_id: Optional[str] = None,
        view_keys: Optional[List[str]] = None,
        consistency_mode: str = "standard",
        force_contract_refresh: bool = False,
        anchor_view_key: Optional[str] = None,
    ) -> Dict[str, Asset]:
        """Generate creator-facing multi-view assets for one story entity."""
        self.last_generation_failures = []
        preset = ASSET_VIEW_PRESETS.get(entity_type)
        if not preset:
            raise ValueError("仅支持角色、场景、道具的多视图资产生成")
        if entity_type == "character" and is_composite_character_name(entity_name):
            raise ValueError("角色三视图只能用于单一角色；当前对象像是群体/复合角色，请先拆分或选择具体角色")

        all_views = {view["key"]: view for view in preset["views"]}
        requested_keys = list(view_keys or list(all_views.keys()))
        unknown = [key for key in requested_keys if key not in all_views]
        if unknown:
            raise ValueError(f"不支持的视图: {', '.join(unknown)}")

        style_keywords = self._style_keywords(style)
        normalized_mode = (consistency_mode or "off").strip().lower()
        if normalized_mode in {"standard", "strict"}:
            visual_contract = await build_visual_contract_from_story(
                self.db,
                self.user_id,
                entity=SimpleNamespace(
                    id=entity_id,
                    entity_type=entity_type,
                    name=entity_name,
                    description=entity_description,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    script_id=script_id,
                ),
                style=style,
                chapter_id=chapter_id,
                script_id=script_id,
                force_refresh=force_contract_refresh,
            )
        else:
            visual_contract = build_visual_contract(
                entity_id=entity_id,
                entity_type=entity_type,
                name=entity_name,
                description=entity_description,
                style=style,
            )
        results: Dict[str, Asset] = {}
        reference_asset: Optional[Asset] = None
        reference_view_key: Optional[str] = None
        default_anchor_view_key = {"character": "front", "scene": "establishing", "prop": "main"}.get(entity_type)
        resolved_anchor_view_key = anchor_view_key or default_anchor_view_key
        if resolved_anchor_view_key and resolved_anchor_view_key not in all_views:
            raise ValueError(f"不支持的锚点视图: {resolved_anchor_view_key}")
        if resolved_anchor_view_key in requested_keys:
            requested_keys = [resolved_anchor_view_key] + [key for key in requested_keys if key != resolved_anchor_view_key]
        elif resolved_anchor_view_key:
            reference_asset = await self._find_entity_view_asset(entity_type, entity_id, resolved_anchor_view_key)
            if reference_asset:
                reference_view_key = resolved_anchor_view_key
        prompt_skill_task = self._prompt_skill_task_for_entity(entity_type)
        for key in requested_keys:
            view = all_views[key]
            active_reference_asset = None if key == resolved_anchor_view_key else reference_asset
            active_reference_view_key = None if key == resolved_anchor_view_key else reference_view_key
            has_anchor = bool(active_reference_asset or (key != resolved_anchor_view_key and resolved_anchor_view_key))
            if not self.image_service:
                try:
                    await self.configure_image_model()
                except Exception:
                    if not is_dev_mode():
                        raise
            strategy = decide_asset_generation_strategy(
                consistency_mode=normalized_mode,
                provider_name=self.provider_name,
                model_id=self.model_id,
                entity_type=entity_type,
                has_anchor=has_anchor,
            )
            if strategy.get("strict_blocking"):
                raise ValueError(strategy["blocking_reason"])
            prompt = self._build_entity_view_prompt(
                entity_type=entity_type,
                name=entity_name,
                description=entity_description,
                style=style,
                view_label=view["label"],
                view_key=key,
                prompt_hint=view["prompt_hint"],
                visual_contract=visual_contract,
                style_keywords=style_keywords,
                reference_asset=active_reference_asset,
            )
            prompt = await self._apply_prompt_skill(
                task=prompt_skill_task,
                prompt=prompt,
                context={
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "entity_name": entity_name,
                    "character_name": entity_name if entity_type == "character" else "",
                    "scene_name": entity_name if entity_type == "scene" else "",
                    "prop_name": entity_name if entity_type == "prop" else "",
                    "description": entity_description or "",
                    "entity_description": entity_description or "",
                    "style": style,
                    "view_label": view["label"],
                    "view_key": key,
                    "prompt_hint": view["prompt_hint"],
                },
            )
            try:
                image_url = await self._generate_asset_image_url(
                    prompt,
                    size=view.get("size") or "1k",
                    aspect_ratio=view.get("aspect_ratio") or "1:1",
                    prefix=f"asset-{entity_type}-{key}-{entity_id[:8]}",
                )
                provider_metadata = {
                    "provider_name": self.provider_name,
                    "model_id": self.model_id,
                    "model_strategy": strategy,
                }
                visual_review = review_asset_against_contract(
                    visual_contract,
                    key,
                    prompt,
                    provider_result_metadata=provider_metadata,
                )
                generation_params = {
                    "source": "entity_multiview",
                    "status": "succeeded",
                    "view_key": key,
                    "view_angle": key,
                    "reference_role": "character_multiview" if entity_type == "character" else f"{entity_type}_multiview",
                    "view_label": view["label"],
                    "view_title": preset["title"],
                    "entity_type": entity_type,
                    "style": style,
                    "consistency_mode": normalized_mode,
                    "aspect_ratio": view.get("aspect_ratio"),
                    "prompt_hint": view.get("prompt_hint"),
                    "visual_contract": visual_contract,
                    "model_strategy": strategy,
                    "provider_name": self.provider_name,
                    "model_id": self.model_id,
                    "anchor_view_key": resolved_anchor_view_key,
                    "reference_view_key": active_reference_view_key,
                    "reference_asset_id": getattr(active_reference_asset, "id", None) if active_reference_asset else None,
                    "reference_asset_url": getattr(active_reference_asset, "url", None) if active_reference_asset else None,
                    "visual_consistency": visual_review,
                    "novel_id": novel_id,
                    "chapter_id": chapter_id,
                    "script_id": script_id,
                    "character_id": character_id if entity_type == "character" else None,
                }
                if visual_review.get("status") != "passed" or visual_review.get("issues"):
                    generation_params["retry_prompt_advice"] = retry_prompt_advice(
                        visual_review.get("issues") or [],
                        visual_contract,
                    )
                asset = await self._create_asset(
                    name=f"{entity_name} · {view['label']}",
                    category=preset["category"],
                    asset_type="image",
                    url=image_url,
                    character_id=character_id if entity_type == "character" else None,
                    entity_id=entity_id,
                    entity_type=entity_type,
                    project_id=project_id,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    script_id=script_id,
                    source_prompt=prompt,
                    generation_params=generation_params,
                )
                results[key] = asset
                if not reference_asset and key == resolved_anchor_view_key:
                    reference_asset = asset
                    reference_view_key = key
            except Exception as exc:
                failure = await self._create_asset(
                    name=f"{entity_name} · {view['label']}生成失败",
                    category=preset["category"],
                    asset_type="text",
                    url="",
                    character_id=character_id if entity_type == "character" else None,
                    entity_id=entity_id,
                    entity_type=entity_type,
                    project_id=project_id,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    script_id=script_id,
                    source_prompt=prompt,
                    generation_params={
                        "source": "entity_multiview",
                        "status": "failed",
                        "view_key": key,
                        "view_angle": key,
                        "reference_role": "character_multiview" if entity_type == "character" else f"{entity_type}_multiview",
                        "view_label": view["label"],
                        "view_title": preset["title"],
                        "entity_type": entity_type,
                        "style": style,
                        "consistency_mode": normalized_mode,
                        "aspect_ratio": view.get("aspect_ratio"),
                        "prompt_hint": view.get("prompt_hint"),
                        "visual_contract": visual_contract,
                        "model_strategy": strategy,
                        "provider_name": self.provider_name,
                        "model_id": self.model_id,
                        "anchor_view_key": resolved_anchor_view_key,
                        "reference_view_key": active_reference_view_key,
                        "reference_asset_id": getattr(active_reference_asset, "id", None) if active_reference_asset else None,
                        "reference_asset_url": getattr(active_reference_asset, "url", None) if active_reference_asset else None,
                        "error_message": str(exc),
                        "retryable": True,
                        "attempted_at": utc_now().isoformat(),
                        "novel_id": novel_id,
                        "chapter_id": chapter_id,
                        "script_id": script_id,
                        "character_id": character_id if entity_type == "character" else None,
                    },
                )
                self.last_generation_failures.append(failure)

        return results

    async def lock_asset_version(self, asset_id: str) -> Asset:
        """
        锁定资产版本

        1. 如果该实体已有其他锁定版本，自动解锁
        2. 将当前资产设为锁定状态
        3. 如果有之前的定稿，将之前的定稿替换为当前版本
        """
        result = await self.db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")

        entity_type = getattr(asset, "entity_type", None) if hasattr(asset, "entity_type") else None
        entity_id = asset.entity_id

        asset_view_key = _view_key(asset)

        # 如果有实体关联，解锁同实体、同视图的其他锁定资产。
        # 三视图/四视图需要同时锁定多个视图，不能锁正面时把侧面解锁。
        if entity_type and entity_id:
            existing_locked = await self.db.execute(
                select(Asset).where(
                    and_(
                        Asset.entity_id == entity_id,
                        Asset.entity_type == entity_type,
                        Asset.is_locked == True,
                        Asset.id != asset_id,
                    )
                )
            )
            for locked_asset in existing_locked.scalars().all():
                locked_view_key = _view_key(locked_asset)
                if asset_view_key:
                    if locked_view_key != asset_view_key:
                        continue
                elif locked_view_key:
                    continue
                locked_asset.is_locked = False
                locked_asset.is_final = False
                locked_asset.replaced_by_id = asset_id

        # 设置当前资产为锁定
        asset.is_locked = True
        asset.locked_at = utc_now()
        asset.locked_by = self.user_id
        asset.is_final = True

        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def unlock_asset(self, asset_id: str) -> Asset:
        """解锁资产版本"""
        result = await self.db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")

        asset.is_locked = False
        asset.is_final = False

        # 如果有被这个资产替代的版本，恢复其定稿状态
        if asset.replaced_by_id:
            replaced_result = await self.db.execute(select(Asset).where(Asset.id == asset.replaced_by_id))
            replaced_asset = replaced_result.scalar_one_or_none()
            if replaced_asset:
                replaced_asset.is_locked = True
                replaced_asset.is_final = True
                asset.replaced_by_id = None

        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_entity_locked_assets(self, entity_type: str, entity_id: str) -> List[Asset]:
        """获取实体的锁定资产"""
        result = await self.db.execute(
            select(Asset).where(
                and_(
                    Asset.entity_id == entity_id,
                    Asset.entity_type == entity_type,
                    Asset.is_locked == True,
                )
            )
        )
        return list(result.scalars().all())

    async def get_entity_asset_versions(self, entity_type: str, entity_id: str) -> List[Asset]:
        """获取实体的所有资产版本（按version排序）"""
        result = await self.db.execute(
            select(Asset)
            .where(
                and_(
                    Asset.entity_id == entity_id,
                    Asset.entity_type == entity_type,
                )
            )
            .order_by(Asset.version.desc())
        )
        return list(result.scalars().all())

    async def _find_entity_view_asset(self, entity_type: str, entity_id: str, view_key: str) -> Optional[Asset]:
        """Find the best existing entity view asset to use as generation lineage."""
        result = await self.db.execute(
            select(Asset)
            .where(
                and_(
                    Asset.entity_id == entity_id,
                    Asset.entity_type == entity_type,
                    Asset.is_active == True,
                    Asset.url.is_not(None),
                )
            )
            .order_by(Asset.is_final.desc(), Asset.is_locked.desc(), Asset.version.desc(), Asset.updated_at.desc())
        )
        for asset in result.scalars().all():
            params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
            asset_view_key = params.get("view_key") or params.get("asset_subtype")
            if asset_view_key == view_key:
                return asset
        return None

    async def _create_asset(
        self,
        name: str,
        category: str,
        asset_type: str,
        url: str,
        character_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        script_id: Optional[str] = None,
        source_prompt: Optional[str] = None,
        expressions: Optional[List[Dict]] = None,
        poses: Optional[List[Dict]] = None,
        generation_params: Optional[Dict] = None,
    ) -> Asset:
        """创建资产记录"""
        asset = Asset(
            id=str(uuid4()),
            user_id=self.user_id,
            name=name,
            category=category,
            asset_type=asset_type,
            url=url,
            thumbnail_url=url,
            character_id=character_id,
            entity_id=entity_id,
            entity_type=entity_type,
            project_id=project_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
            source_prompt=source_prompt,
            expressions=expressions,
            poses=poses,
            generation_params=generation_params,
        )
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    def _build_avatar_prompt(self, name: str, description: str, style: str) -> str:
        """构建头像生成提示词"""
        prompt = "\n".join(
            [
                self._style_keywords(style),
                f"生成角色「{name}」头像参考图，头像和肩部清晰可见。",
                f"角色设定：{description or '严格依据小说角色设定'}。",
                "头像要求：单人正面或轻微三分之二视角，五官、发型、服饰领口和标志配饰清晰。",
                CHARACTER_SINGLE_VIEW_CONSTRAINT,
            ]
        )
        return append_global_image_constraints(prompt)

    def _build_fullbody_prompt(self, name: str, description: str, style: str) -> str:
        """构建全身图生成提示词"""
        prompt = "\n".join(
            [
                self._style_keywords(style),
                f"生成角色「{name}」完整头身立绘参考图。",
                f"角色设定：{description or '严格依据小说角色设定'}。",
                "全身要求：自然站姿，头发、脸型、体型、服装层次、鞋履和标志道具完整可见。",
                CHARACTER_SINGLE_VIEW_CONSTRAINT,
            ]
        )
        return append_global_image_constraints(prompt)

    def _build_expressions_prompt(self, name: str, description: str, style: str) -> str:
        """构建表情集生成提示词"""
        return "\n".join(
            [
                self._style_keywords(style),
                f"生成角色「{name}」表情参考图。",
                f"角色设定：{description or '严格依据小说角色设定'}。",
                "表情要求：同一角色、同一发型和服饰，展示开心、愤怒、悲伤、惊讶四种基础表情；允许表情宫格，但每格必须是同一个人物。",
                "禁止改变性别、年龄感、脸型、发型、服装和标志配饰。",
            ]
        )

    def _build_poses_prompt(self, name: str, description: str, style: str) -> str:
        """构建姿态集生成提示词"""
        return "\n".join(
            [
                self._style_keywords(style),
                f"生成角色「{name}」动作姿态参考图。",
                f"角色设定：{description or '严格依据小说角色设定'}。",
                "姿态要求：同一角色、同一服装和标志道具，展示站立、行走、转身、挥手或持物动作；允许动作参考表，但每个姿态必须保持同一个人物。",
                "禁止改变性别、年龄感、脸型、发型、体型、服装和标志配饰。",
            ]
        )

    def _build_scene_prompt(self, name: str, description: str, style: str) -> str:
        """构建场景生成提示词"""
        prompt = "\n".join(
            [
                self._style_keywords(style),
                f"生成场景「{name}」主参考图。",
                f"场景设定：{description or '严格依据小说和剧本场景设定'}。",
                "场景要求：大全景或远景，展示空间结构、入口、地标、行动区域、光线方向和整体氛围，便于后续多镜头复用。",
                SCENE_VIEW_CONSTRAINT,
            ]
        )
        return append_global_image_constraints(prompt)

    def _build_scene_detail_prompt(self, name: str, description: str, style: str) -> str:
        """构建场景细节图提示词"""
        prompt = "\n".join(
            [
                self._style_keywords(style),
                f"生成场景「{name}」局部细节参考图。",
                f"场景设定：{description or '严格依据小说和剧本场景设定'}。",
                "细节要求：聚焦一个关键地标、入口、道具摆放或光影区域，必须属于同一连续空间，不要生成多个地点拼贴。",
                SCENE_VIEW_CONSTRAINT,
            ]
        )
        return append_global_image_constraints(prompt)

    def _build_prop_prompt(self, name: str, description: str, style: str) -> str:
        """构建道具生成提示词"""
        prompt = "\n".join(
            [
                self._style_keywords(style),
                f"生成道具「{name}」主参考图。",
                f"道具设定：{description or '严格依据小说和剧本道具设定'}。",
                "道具要求：单个核心道具，轮廓、材质、纹路、发光颜色、破损状态和比例清晰，浅色干净背景。",
                PROP_VIEW_CONSTRAINT,
            ]
        )
        return append_global_image_constraints(prompt)

    def _style_keywords(self, style: str) -> str:
        return style_keywords_for(style)

    def _build_entity_view_prompt(
        self,
        *,
        entity_type: str,
        name: str,
        description: str,
        style: str,
        view_label: str,
        view_key: str,
        prompt_hint: str,
        visual_contract: Dict[str, Any],
        style_keywords: str,
        reference_asset: Optional[Asset] = None,
    ) -> str:
        """Build a Chinese-first prompt for creator-facing entity view generation."""
        reference_label = None
        reference_url = None
        if reference_asset:
            params = reference_asset.generation_params if isinstance(reference_asset.generation_params, dict) else {}
            reference_label = params.get("view_label") or "正面参考图"
            reference_url = reference_asset.url
        return entity_view_prompt(
            entity_type=entity_type,
            name=name,
            description=description,
            style_keywords=style_keywords,
            view_label=view_label,
            view_key=view_key,
            prompt_hint=prompt_hint,
            contract=visual_contract,
            reference_view_label=reference_label,
            reference_url=reference_url,
        )
