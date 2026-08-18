"""Built-in Prompt skills for the full novel-to-video creation flow."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromptSkill

SYSTEM_PROMPT_SKILL_USER_ID = "system"


def _skill(
    *,
    task: str,
    skill_id: str | None = None,
    name: str,
    description: str,
    stage: str,
    content: str,
    priority: int,
    variables: Dict[str, Any],
    version: int = 1,
) -> Dict[str, Any]:
    return {
        "id": skill_id or f"builtin-{task}-standard",
        "user_id": SYSTEM_PROMPT_SKILL_USER_ID,
        "name": name,
        "description": description,
        "task": task,
        "stage": stage,
        "content": content.strip(),
        "variables": variables,
        "priority": priority,
        "inject_position": "before_constraints",
        "version": version,
        "is_active": True,
        "is_builtin": True,
        "tags": ["标准", "内置", "全流程"],
    }


STANDARD_PROMPT_SKILLS: List[Dict[str, Any]] = [
    _skill(
        task="novel_generation",
        name="标准小说创建技能",
        description="从题材、受众和短剧化目标生成可持续拆章的小说设定。",
        stage="content",
        priority=10,
        variables={"genre": "国风幻想", "audience": "短剧观众", "episode_count": "12"},
        content="""
标准小说创建技能：围绕「{genre}」题材，为「{audience}」创作适合后续动画短剧改编的小说。
必须输出核心卖点、世界观、主角目标、主要矛盾、角色关系、章节走向和可视化风格提示。
故事结构要便于拆分为约 {episode_count} 集，每章结尾保留清晰钩子，避免只写散文式气氛。
""",
    ),
    _skill(
        task="chapter_writing",
        name="标准章节创建技能",
        description="承接前后章节、状态机和 Story Bible 写出可分镜章节。",
        stage="content",
        priority=20,
        variables={"chapter_goal": "推进主线冲突", "tone": "电影感动漫"},
        content="""
标准章节创建技能：本章目标是「{chapter_goal}」，语气保持「{tone}」。
章节必须包含明确场景、出场角色、行动目标、冲突升级、关键道具或线索、结尾悬念。
写作时保留可视化动作和对白信息，避免大段内心独白导致后续剧本和分镜无法执行。
""",
    ),
    _skill(
        task="script_generation",
        name="标准剧本创建技能",
        description="把章节改编成适合分镜、配音、字幕和视频生成的短剧剧本。",
        stage="content",
        priority=30,
        variables={"format": "分场剧本", "duration": "60-90秒"},
        content="""
标准剧本创建技能：将章节改编为「{format}」，单集目标时长约 {duration}。
剧本必须按场次组织，包含场景、人物、动作、对白、旁白、情绪节奏和转场提示。
每段对白要短、可配音、可生成字幕；每个动作要能转成镜头，不写无法拍摄的抽象描述。
""",
    ),
    _skill(
        task="storyboard_generation",
        name="标准分镜创建技能",
        description="把剧本拆成镜头、对白、运镜、字幕和生产字段。",
        stage="content",
        priority=40,
        variables={"shot_count": "6-10", "style": "电影感动漫"},
        content="""
标准分镜创建技能：基于剧本生成 {shot_count} 个连续镜头，整体风格为「{style}」。
每个镜头必须包含景别、机位、运镜、主体动作、视觉焦点、情绪、光影、色彩、对白/旁白和字幕草稿。
镜头之间要保持角色、场景、道具和事件状态连续，避免突然换装、换场或跳过关键动作。
""",
    ),
    _skill(
        task="entity_extraction",
        name="标准实体/资产抽取技能",
        description="从小说、章节或剧本中抽取可用于资产和分镜生产的角色、场景、道具和事件。",
        stage="analysis",
        priority=45,
        version=2,
        variables={"entity_types": "character、scene、prop、event", "output_format": "JSON 数组"},
        content="""
标准实体/资产抽取技能：只抽取原文中有明确证据、后续能用于分镜、资产或视频一致性的对象。
允许的实体类型为：{entity_types}，输出格式必须是「{output_format}」。
角色必须是可持续追踪的单一个体，至少满足明确姓名/稳定称谓，并具备动作、对白、身份或关系证据。
群体背景、情绪词、身体部位、动作短语、时间短语和地点片段不能当作角色。
尤其禁止把“地下室、警戒线外、午夜前、这可能、蓝雾退、某人伸手”等空间/时间/判断/动作片段识别为角色。
姓名与动作相邻时只保留姓名主体，例如“季衡伸手”应抽取“季衡”；虚构身份个体（如“影潮使”）有持续行动证据时可以保留。
场景必须是可复用空间；道具必须是可见且需要前后一致的物件；事件必须是剧情变化，不要和人物、场景、道具混淆。
每个实体都要带 evidence 和 confidence；没有证据就不要凭题材臆造资产。
""",
    ),
    _skill(
        task="entity_extraction",
        skill_id="builtin-entity-extraction-character-standard",
        name="标准角色提取技能",
        description="从小说与章节中提取有原文证据、可跨章追踪的真实角色。",
        stage="character",
        priority=46,
        version=1,
        variables={"minimum_confidence": "0.72"},
        content="""
标准角色提取技能：从当前小说、章节或剧本中识别需要跨章保持一致的角色。
只输出 JSON 数组，不要输出 Markdown、解释文字或代码块；没有合格角色时输出空数组。
每个角色必须包含规范名称、别名、原文证据、身份/关系、外观线索、性格与行动证据、置信度。
仅保留明确姓名、稳定称谓或具有持续行动和对白证据的单一个体，置信度不得低于 {minimum_confidence}。
合并同一角色的别名和不同称呼，不得重复创建；无法确认时保留证据并降低置信度，不要编造设定。
禁止把群体背景、身体部位、动作短语、地点、时间、情绪、判断句或无持续证据的泛称识别为角色。
输出前逐项核对：名称能在原文定位、证据与名称一致、类型只能是 character、后续可用于角色定稿图和镜头一致性。
""",
    ),
    _skill(
        task="entity_extraction",
        skill_id="builtin-entity-extraction-scene-prop-standard",
        name="标准场景/道具提取技能",
        description="从小说与章节中区分可复用场景和需要连续追踪的关键道具。",
        stage="scene_prop",
        priority=47,
        version=1,
        variables={"minimum_confidence": "0.70"},
        content="""
标准场景/道具提取技能：从当前小说、章节或剧本中分别识别可复用场景与关键道具。
只输出 JSON 数组，不要输出 Markdown、解释文字或代码块；没有合格对象时输出空数组。
场景必须是角色能够进入、停留或发生动作的连续空间，并包含规范名称、别名、原文证据、时代/空间结构、光线天气和置信度。
道具必须是画面可见、参与剧情或需要前后保持状态一致的物件，并包含规范名称、别名、原文证据、材质外观、持有人/位置、状态变化和置信度。
置信度不得低于 {minimum_confidence}；同一地点或物件的不同称呼必须合并，状态变化记录到同一对象，不得重复创建。
禁止把人物、动作、情绪、时间短语、抽象概念、普通背景杂物或没有原文证据的题材想象识别为场景/道具。
输出前逐项核对：类型只能是 scene 或 prop、证据可定位、场景可复用、道具确有连续性价值，不能凭空补全。
""",
    ),
    _skill(
        task="shot_prompt",
        name="标准镜头创建技能",
        description="把分镜字段整理为可进入图像/视频模型的镜头提示词。",
        stage="generation",
        priority=50,
        variables={"tone": "冷蓝月光", "aspect_ratio": "9:16"},
        content="""
标准镜头创建技能：将当前镜头整理为 {aspect_ratio} 竖屏短剧提示词，主色调「{tone}」。
提示词要明确主体、动作、场景、镜头运动、光线、构图、情绪、字幕和禁止变化项。
必须继承已锁定角色与资产视觉 DNA，不得新增未声明角色、无关道具或改变时代背景。
""",
    ),
    _skill(
        task="shot_video",
        name="标准镜头视频技能",
        description="生成单镜头视频时保持角色、资产、镜头运动和时长一致。",
        stage="generation",
        priority=60,
        variables={"motion": "轻微推进", "duration": "4秒"},
        content="""
标准镜头视频技能：生成约 {duration} 的单镜头视频，运镜以「{motion}」为主。
严格保持角色脸型、发型、服装、道具、场景结构、光影方向和色彩基调。
视频只表现当前镜头动作，不跳切、不换人、不改变年龄和身份，不加入文字水印或无关镜头。
""",
    ),
    _skill(
        task="character_image",
        name="标准头像/角色图技能",
        description="生成头像、角色定稿图和多视图时锁定角色视觉 DNA。",
        stage="asset",
        priority=70,
        variables={"view": "头像", "style": "电影感动漫"},
        content="""
标准头像/角色图技能：生成「{view}」角色资产，画风为「{style}」。
只生成一个角色，保持性别、年龄感、脸型、发型、服装、标志道具和气质一致。
背景保持简洁，不要生成多人、拼贴、多宫格、文字、水印或与小说无关的饰物。
""",
    ),
    _skill(
        task="scene_reference_image",
        name="标准场景图技能",
        description="生成单一连续空间的场景设定图。",
        stage="asset",
        priority=80,
        variables={"scene_type": "主场景", "lighting": "自然光"},
        content="""
标准场景图技能：生成「{scene_type}」参考图，光线为「{lighting}」。
画面必须是一个连续空间，明确时代、建筑结构、天气、光源方向、色彩基调和可行动区域。
        不要拼接多个地点，不要出现无关人物特写，后续镜头必须继承该场景空间结构。
""",
    ),
    _skill(
        task="series_reference_board",
        name="标准系列复合参考设定板技能",
        description="生成同时绑定多角色视觉规范和全局风格的单一复合参考图。",
        stage="asset",
        priority=85,
        variables={"characters": "主角", "style": "电影感动漫", "layout": "左角色、右风格板"},
        content="""
标准系列复合参考设定板技能：为角色「{characters}」生成单一复合参考图，整体风格为「{style}」。
布局必须遵循「{layout}」：每名角色提供可辨认的正面、四分之三侧面和全身规范视图，另设独立全局风格、色板、线条与光影区域。
同一角色的脸型、发型、服装和标志道具必须一致；禁止遗漏已声明角色、拆成多个文件、生成无关人物、文字或水印。
""",
    ),
    _skill(
        task="prop_image",
        name="标准道具图技能",
        description="生成核心道具设定图并稳定材质、比例和特殊状态。",
        stage="asset",
        priority=90,
        variables={"material": "金属与玉石", "state": "轻微发光"},
        content="""
标准道具图技能：生成单个核心道具，材质为「{material}」，状态为「{state}」。
必须清楚呈现外形、纹理、比例、破损、发光颜色和使用方式。
不要把多个无关物品拼在一起，不要生成文字、水印或与剧情无关的装饰。
""",
    ),
    _skill(
        task="novel_cover",
        name="标准封面图技能",
        description="根据小说题材、主角、世界观和卖点生成封面提示词。",
        stage="asset",
        priority=100,
        variables={"title": "未命名作品", "genre": "幻想冒险", "style": "电影感动漫"},
        content="""
标准封面图技能：为《{title}》生成「{genre}」封面，整体画风为「{style}」。
封面必须突出主角、核心冲突、世界观符号和商业可读性，构图适合竖版封面。
不要生成真实文字、logo、水印、杂乱拼贴或与作品设定矛盾的人物和场景。
""",
    ),
    _skill(
        task="tts_dialogue",
        name="标准角色配音技能",
        description="把对白整理成适合 TTS 的短句、情绪和停顿。",
        stage="production",
        priority=110,
        variables={"voice_style": "清晰自然", "emotion": "克制紧张"},
        content="""
标准角色配音技能：对白使用「{voice_style}」声音风格，情绪为「{emotion}」。
每句台词要短、口语化、适合字幕显示；标注说话人、情绪、停顿和重音。
保持角色音色、人设和关系一致，不把旁白、动作描述和角色台词混在同一句里。
""",
    ),
    _skill(
        task="shot_audio_video",
        name="标准音视频直生技能",
        description="用于支持有声视频模型的一体化镜头生成约束。",
        stage="production",
        priority=120,
        variables={"duration": "4秒", "audio_mode": "对白优先"},
        content="""
标准音视频直生技能：生成约 {duration} 的有声镜头，音频策略为「{audio_mode}」。
画面、对白、口型、字幕节奏和动作必须同步；不得让角色口型与台词错位。
保持已锁定角色、场景、道具和故事状态，不插入无关镜头、旁白噪声或背景音乐喧宾夺主。
""",
    ),
    _skill(
        task="consistency_review",
        name="标准一致性审查技能",
        description="检查生成链路中的人物、场景、道具、剧情和生产约束。",
        stage="review",
        priority=130,
        variables={"risk_focus": "角色漂移、资产缺失、剧情断裂"},
        content="""
标准一致性审查技能：重点检查「{risk_focus}」。
审查必须指出问题位置、影响、阻断级别、是否可测试跳过，以及明确修复入口。
生产模式下不得放行缺失资产锁、公网引用图、模型配置或镜头媒体的关键阻断项。
""",
    ),
    _skill(
        task="repair_suggestion",
        name="标准返修建议技能",
        description="把审查问题转成可执行返修动作和快捷入口。",
        stage="review",
        priority=140,
        variables={"repair_depth": "最小可行修复"},
        content="""
标准返修建议技能：按「{repair_depth}」原则给出返修路径。
每条建议必须包含修复目标、推荐动作、影响范围、快捷入口和验证方式。
优先使用安全动作：补齐实体引用、应用资产锁、刷新生产合约、质量检查、媒体审计。
""",
    ),
]


async def ensure_standard_prompt_skills(
    db: AsyncSession, *, commit: bool = True,
) -> None:
    """Create or refresh built-in Prompt skills without touching user clones."""
    expected_ids = [item["id"] for item in STANDARD_PROMPT_SKILLS]
    result = await db.execute(select(PromptSkill).where(PromptSkill.id.in_(expected_ids)))
    existing = {skill.id: skill for skill in result.scalars().all()}
    changed = False

    for definition in STANDARD_PROMPT_SKILLS:
        skill = existing.get(definition["id"])
        if skill is None:
            db.add(PromptSkill(**definition))
            changed = True
            continue
        for key, value in definition.items():
            if getattr(skill, key) != value:
                setattr(skill, key, value)
                changed = True

    if changed and commit:
        await db.commit()
    elif changed:
        await db.flush()
