from app.services.entity_extraction_service import extract_story_entities


def _names_by_type(entities):
    grouped = {}
    for entity in entities:
        grouped.setdefault(entity["entity_type"], set()).add(entity["name"])
    return grouped


def test_deterministic_extraction_classifies_characters_scenes_and_props():
    text = "沈月璃在青阳宗外门石屋醒来，旧铜钩悬在门梁上。外门弟子们围在门口，王执事低声道：“别碰铜钩。”"

    entities = extract_story_entities(text, {"character", "scene", "prop"})

    by_type = _names_by_type(entities)
    assert {"沈月璃", "王执事"}.issubset(by_type.get("character", set()))
    assert "青阳宗外门石屋" in by_type.get("scene", set())
    assert "旧铜钩" in by_type.get("prop", set())
    assert "外门弟子们" not in by_type.get("character", set())
    assert "青阳宗外门石屋" not in by_type.get("character", set())
    assert "旧铜钩" not in by_type.get("character", set())


def test_ai_entity_json_is_normalized_before_persistence():
    from app.api.v1.endpoints.story_bible import _parse_entity_json

    content = """
    [
      {"entity_type": "character", "name": "青阳宗外门石屋", "description": "沈月璃醒来的地点"},
      {"entity_type": "scene", "name": "沈月璃", "description": "少女主角，在石屋醒来并行动"},
      {"entity_type": "character", "name": "外门弟子们", "description": "围在门口的群体背景"},
      {"entity_type": "prop", "name": "王执事", "description": "低声说话的执事"},
      {"entity_type": "scene", "name": "旧铜钩", "description": "悬在门梁上的旧铜钩"}
    ]
    """

    entities = _parse_entity_json(content)

    by_type = _names_by_type(entities)
    assert "沈月璃" in by_type.get("character", set())
    assert "王执事" in by_type.get("character", set())
    assert "青阳宗外门石屋" in by_type.get("scene", set())
    assert "旧铜钩" in by_type.get("prop", set())
    assert "外门弟子们" not in by_type.get("character", set())


def test_extraction_filters_composite_groups_and_action_phrases():
    text = (
        "角色：孙剑（逆天至尊）、外门弟子们。"
        "场景：青阳宗广场。"
        "道具：孙剑背负古剑、裂纹令牌。"
        "事件：孙剑发现令牌裂开。"
    )

    entities = extract_story_entities(text, {"character", "scene", "prop", "event"})

    by_type = _names_by_type(entities)
    assert "孙剑" in by_type.get("character", set())
    assert "外门弟子们" not in by_type.get("character", set())
    assert "孙剑（逆天至尊）" not in by_type.get("character", set())
    assert "青阳宗广场" in by_type.get("scene", set())
    assert "古剑" in by_type.get("prop", set())
    assert "裂纹令牌" in by_type.get("prop", set())
    assert "孙剑背负古剑" not in by_type.get("prop", set())
    assert "孙剑发现令牌裂开" in by_type.get("event", set())


def test_extraction_does_not_split_production_copy_into_fake_characters():
    text = (
        "林澈：\"我们只剩四秒。\" 阿岚：\"别停，我来稳住轨道。\" "
        "画面必须保证人物造型、道具状态和事件因果与小说一致。"
        "字幕要点：保留关键对白并标注说话人。"
    )

    entities = extract_story_entities(text, {"character"})

    names = _names_by_type(entities).get("character", set())
    assert {"林澈", "阿岚"}.issubset(names)
    assert "因果" not in names
    assert "因果与小" not in names
    assert "白并标注" not in names


def test_extraction_does_not_promote_production_copy_into_fake_props():
    text = (
        "列车维修舱红灯成为本场视觉钩子。"
        "开场钩子要强，形成下一集钩子，并保留最后一句钩子。"
        "镜头序列：推镜、拉镜。"
    )

    entities = extract_story_entities(text, {"prop"})

    names = _names_by_type(entities).get("prop", set())
    assert "列车维修舱红灯" in names
    assert "成为本场视觉钩" not in names
    assert "开场钩" not in names
    assert "形成下一集钩" not in names
    assert "保留最后一句钩" not in names
    assert "推镜" not in names
    assert "拉镜" not in names
    assert "镜" not in names


def test_extraction_does_not_promote_shot_prompt_copy_into_fake_scene_or_prop():
    text = (
        "地点：暗巷。"
        "镜头先交代暗巷的空间和氛围，再把注意力推向林澈与铜铃芯。"
        "上一章留下的线索，在这一刻重新指向林澈发现回声会模仿他们的声音。"
    )

    entities = extract_story_entities(text, {"scene", "prop"})

    by_type = _names_by_type(entities)
    assert "暗巷" in by_type.get("scene", set())
    assert "这一刻重新指向林" not in by_type.get("scene", set())
    assert "推向林澈与铜铃" not in by_type.get("prop", set())


def test_fog_port_story_extracts_production_entities_without_dialogue_fragments():
    text = (
        "雾港在夜里突然停电，潮水把旧码头的铜铃推得一声接一声。"
        "江屿是十六岁的修表师，穿着深蓝夹克，背着银色工具包，"
        "他在父亲留下的修表铺里听见星锚罗盘发出蓝光。"
        "巡港员许澜戴着红围巾赶来，手里举着同一枚星锚罗盘的旧图纸。"
        "她低声说：“江屿，罗盘指向灯塔，不是指向海。”"
        "钟楼机房里挂满停摆的海潮钟。"
        "江屿和许澜沿蓝色轨道登上灯塔。"
        "灯塔星锚室里，巨大的星锚悬在玻璃穹顶下，蓝焰灯芯从罗盘中飞出。"
        "影潮使从穹顶阴影里出现，想夺走银色工具包里的铜钥匙。"
    )

    entities = extract_story_entities(text, {"character", "scene", "prop", "event"})

    by_type = _names_by_type(entities)
    assert {"江屿", "许澜", "影潮使"}.issubset(by_type.get("character", set()))
    assert {"雾港", "旧码头", "钟楼机房", "灯塔星锚室", "修表铺"}.issubset(by_type.get("scene", set()))
    assert {"星锚罗盘", "蓝焰灯芯", "银色工具包", "铜钥匙", "红围巾"}.issubset(by_type.get("prop", set()))
    fake_characters = {"她低声说", "不是指", "罗盘指", "芯只在他", "紧红围巾", "而是", "潮水", "星锚不"}
    assert fake_characters.isdisjoint(by_type.get("character", set()))
    fake_props = {
        "不要让灯",
        "如果灯",
        "升起一条通往灯",
        "蓝色轨道登上灯",
        "他们用铜钥匙",
        "蓝焰灯芯装进罗盘",
        "铜钥匙插进星锚",
        "选择让星锚",
        "机房找第一段星锚",
        "许澜握紧红围巾",
    }
    assert fake_props.isdisjoint(by_type.get("prop", set()))


def test_four_chapter_acceptance_story_does_not_promote_environment_words_to_characters():
    text = (
        "第一章 雨夜旧码头\n"
        "角色：许澜、秦砚\n"
        "场景：雨夜旧码头\n"
        "道具：银色工具包、海潮钟\n"
        "许澜披着灰蓝外套，系着红围巾，提着银色工具包赶到雨夜旧码头。"
        "秦砚守在灯塔阴影里，提醒她海潮钟已经倒转三次。"
        "许澜说：别让钟声越过第三道防线。秦砚回答：如果它响第四次，整座港都会忘记今天。"
        "第二章 星锚室蓝光\n"
        "角色：许澜、秦砚、沈听白\n"
        "场景：灯塔地下星锚室\n"
        "道具：银色工具包、星锚罗盘、蓝焰灯芯\n"
        "沈听白从控制台后出现，要求许澜交出银色工具包。星锚罗盘启动，指针指向一批失踪档案。"
        "第三章 档案中的自己\n"
        "秦砚说：如果我已经消失过，现在站在这里的我是什么？许澜回答：是我们要救回来的人。"
        "第四章 第四次钟声\n"
        "三人冲上灯塔顶层钟室，暴雨打在圆形玻璃窗上。钟声停在最后一秒。"
    )

    entities = extract_story_entities(text, {"character", "scene", "prop", "event"})

    names = _names_by_type(entities).get("character", set())
    assert {"许澜", "秦砚", "沈听白"}.issubset(names)
    fake_characters = {"秦砚守", "指针", "现在", "暴雨", "钟声", "这里的我", "三人"}
    assert fake_characters.isdisjoint(names)


def test_yundeng_acceptance_story_extracts_core_entities_without_action_noise():
    text = (
        "黄昏的云灯集市漂在山城屋顶上，十二岁的林岚穿着蓝白邮差斗篷，"
        "银蓝短发被晚风吹起，琥珀色眼睛一直盯着胸前的铜铃星灯。"
        "星灯猫阿绒蹲在她肩上，尾巴发出柔和的金光。"
        "林岚接到第一封没有地址的信，信纸上只写着“送到雨会唱歌的巷口”。"
        "她轻轻摇响铜铃星灯，星光在摊位之间铺成一条窄路。"
        "林岚说：“阿绒，我们只送真正被惦记的愿望。”"
        "阿绒小声回答：“那就先记住铃声，别让它变调。”"
        "夜雨落下，雨巷的青石路反射着蓝金色灯光。"
        "一枚破旧的星形纽扣从信封里滑出，指向巷尾的旧伞铺。"
        "店门口站着沉默的女孩黎夏，她认出纽扣来自失踪的哥哥。"
        "林岚把信递过去说：“它不是丢了，只是在等你愿意打开。”"
        "云层裂开，一座由星砂搭成的桥悬在雨巷上方。"
        "林岚、阿绒和黎夏一起走上星桥，铜铃星灯的铃声让桥面稳定下来。"
        "桥中央出现三扇门：一扇通向云灯集市，一扇通向旧伞铺，一扇通向黎明邮局。"
        "林岚坚定地说：“我们走去黎明邮局，那里才会盖下真正的邮戳。”"
        "黎明邮局坐落在山城最高的钟楼里，窗外晨光穿过云海。"
        "林岚微笑说：“这封信已经送达，愿望也该回家了。”"
        "黎夏握住星形纽扣说：“谢谢你，林岚邮差。”"
    )

    entities = extract_story_entities(text, {"character", "scene", "prop", "event"})

    by_type = _names_by_type(entities)
    assert {"林岚", "阿绒", "黎夏"}.issubset(by_type.get("character", set()))
    assert {"云灯集市", "雨巷", "旧伞铺", "星桥", "黎明邮局", "山城", "钟楼"}.issubset(
        by_type.get("scene", set())
    )
    assert {"铜铃星灯", "星形纽扣", "信封"}.issubset(by_type.get("prop", set()))
    fake_characters = {
        "林岚微笑",
        "阿绒小声",
        "信递过去",
        "星光",
        "星形纽扣",
        "只是",
        "一扇通",
        "留下的不",
    }
    assert fake_characters.isdisjoint(by_type.get("character", set()))
    fake_props = {"她轻轻摇响铜铃", "一扇通向云灯", "反射着蓝金色灯", "那就先记住铃"}
    assert fake_props.isdisjoint(by_type.get("prop", set()))


def test_rain_station_story_extracts_dialogue_characters_scenes_and_props_without_noise():
    text = (
        "第一章 雨巷铜铃\n"
        "主角：孙剑，二十七岁，黑色短发，深灰风衣，随身携带旧铜铃。"
        "配角：沈岚，三十岁，白发女医生，冷静温柔。"
        "旁白：雨夜的旧车站像被水雾封住，霓虹在积水里碎成蓝色光斑。"
        "孙剑站在站台边，铜铃突然自己响了三下。"
        "沈岚合上病历，低声说：“别急，先看这份记录。”"
        "孙剑握紧铜铃说：“我来确认出口，你守住信号灯。”"
        "远处广告屏闪过一行倒计时，站台尽头传来孩子的哭声。"
        "第二章 无人列车\n"
        "无人列车从雾里滑出，车门打开时没有风，却吹灭了整排路灯。"
        "沈岚把白色药箱放在脚边，对孙剑说：“如果铃声再响，说明车里有人在求救。”"
        "孙剑抬头看向空荡车厢，说：“我先进去，你听见第三声就关门。”"
        "车厢中央挂着同样的铜铃，铃舌上刻着孙剑童年的名字。"
        "旁白：他终于明白，今晚追来的不是怪物，而是一段被他遗忘的求救。"
    )

    entities = extract_story_entities(text, {"character", "scene", "prop", "event"})

    by_type = _names_by_type(entities)
    assert {"孙剑", "沈岚"}.issubset(by_type.get("character", set()))
    assert {"旧车站", "站台", "无人列车", "车厢"}.issubset(by_type.get("scene", set()))
    assert {"旧铜铃", "白色药箱", "信号灯"}.issubset(by_type.get("prop", set()))
    assert any("求救" in name or "铜铃" in name for name in by_type.get("event", set()))
    fake_characters = {"霓虹", "无人列车", "追来的不", "对孙剑"}
    assert fake_characters.isdisjoint(by_type.get("character", set()))
    fake_props = {"紧铜铃", "对孙剑", "铃舌上刻着孙剑", "白色药", "吹灭了整排路灯", "整排路灯", "你守住信号灯"}
    assert fake_props.isdisjoint(by_type.get("prop", set()))


def test_consistency_context_filters_persisted_shot_prompt_noise_entities():
    from app.models import StoryEntity
    from app.services.consistency_context import _is_noise_story_entity

    assert _is_noise_story_entity(StoryEntity(entity_type="scene", name="这一刻重新指向林"))
    assert _is_noise_story_entity(StoryEntity(entity_type="prop", name="推向林澈与铜铃"))
    assert not _is_noise_story_entity(StoryEntity(entity_type="scene", name="暗巷"))
    assert not _is_noise_story_entity(StoryEntity(entity_type="prop", name="铜铃芯"))


def test_shot_response_sanitizes_persisted_entity_ref_noise():
    from app.api.v1.endpoints.shots import _sanitize_shot_extra_data_for_response

    extra_data = {
        "entity_refs": {
            "characters": [{"name": "林澈"}],
            "scenes": [{"name": "暗巷"}, {"name": "这一刻重新指向林"}],
            "props": [{"name": "铜铃"}, {"name": "推向林澈与铜铃"}],
            "events": [{"name": "回声模仿声音"}],
        },
        "scene_refs": [{"name": "暗巷"}, {"name": "这一刻重新指向林"}],
        "prop_refs": [{"name": "铜铃"}, {"name": "推向林澈与铜铃"}],
    }

    sanitized = _sanitize_shot_extra_data_for_response(extra_data)

    scene_names = {ref["name"] for ref in sanitized["scene_refs"]}
    prop_names = {ref["name"] for ref in sanitized["prop_refs"]}
    assert scene_names == {"暗巷"}
    assert prop_names == {"铜铃"}
    assert "这一刻重新指向林" not in sanitized["environment_context"]
    assert "推向林澈与铜铃" not in sanitized["environment_context"]
