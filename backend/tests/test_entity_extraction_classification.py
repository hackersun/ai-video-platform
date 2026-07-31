from app.services.entity_extraction_service import extract_story_entities


def test_character_costume_is_extracted_from_explicit_wearing_phrase():
    entities = extract_story_entities(
        "沈砚穿着深蓝旧呢大衣抵达雾港。沈砚说：“我会查清船队的去向。”",
        {"character"},
    )

    character = next(item for item in entities if item["name"] == "沈砚")

    assert character["attributes"]["visual_dna"]["costume"] == "深蓝旧呢大衣"


def test_chapter_owned_extraction_emits_stable_story_lock_evidence_contract():
    content = "沈砚抵达雾港，拿起铜铃。"
    entities = extract_story_entities(
        content, {"character", "scene", "prop"},
        source_chapter_id="chapter-1", source_chapter_index=1,
    )

    assert entities
    for entity in entities:
        contract = entity["attributes"]["evidence_contract"]
        start, end = contract["source_span"]
        assert contract["status"] == "verified"
        assert contract["chapter_id"] == "chapter-1"
        assert content[start:end]
        assert len(contract["content_hash"]) == 64
        assert contract["parser_version"] == "deterministic-extraction-v2"


def test_rule_character_boilerplate_is_evidence_not_identity_description():
    entities = extract_story_entities("沈砚抵达雾港。沈砚说：立刻撤离。", {"character"})
    shen_yan = next(item for item in entities if item["name"] == "沈砚")
    assert shen_yan["description"] is None
    assert shen_yan["attributes"]["extraction_notes"]
    assert shen_yan["evidence"]


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


def test_action_character_rules_reject_time_place_and_action_fragments():
    text = (
        "灯塔地下室是一座环形机械厅。季衡伸手说：把星钥给我。"
        "林澈站在警戒线外回答：用记忆换来的光，不是守护。"
        "午夜前把星钥送到车站，陆遥说这可能是陷阱。"
        "阿七把记录投向控制台，蓝雾退向海面。"
    )

    names = _names_by_type(extract_story_entities(text, {"character"})).get("character", set())

    assert {"季衡", "林澈", "陆遥", "阿七"}.issubset(names)
    assert not {"塔地下室", "季衡伸手", "警戒线外", "午夜前", "这可能", "蓝雾退"}.intersection(names)


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


def test_explicit_scene_label_wins_over_long_context_noise():
    text = "主角追查一封来自旧邮局的密信。角色：沈砚。场景：旧邮局。道具：铜铃。沈砚在旧邮局听见铜铃声。"

    entities = extract_story_entities(text, {"scene"})

    names = _names_by_type(entities).get("scene", set())
    assert "旧邮局" in names
    assert "角追查一封来自旧邮局" not in names


def test_subject_predicate_fragment_is_not_promoted_to_prop():
    entities = extract_story_entities(
        "沈砚在废弃灯塔里发现旧铜铃。沈砚在废弃灯下停住脚步。",
        {"prop"},
    )

    names = _names_by_type(entities).get("prop", set())
    assert "旧铜铃" in names
    assert "沈砚在废弃灯" not in names
    assert all(not name.startswith("沈砚在") for name in names)


def test_explicit_prop_label_is_kept_for_review_even_when_name_looks_like_phrase():
    entities = extract_story_entities("道具：爱在黎明破晓前海报。", {"prop"})

    assert "爱在黎明破晓前海报" in _names_by_type(entities).get("prop", set())


def test_extracted_event_has_actor_action_object_outcome_and_provenance():
    entities = extract_story_entities(
        "事件：沈砚打开旧铜铃，密门因此显现。",
        {"event"},
        source_chapter_id="chapter-2",
        source_chapter_index=2,
    )

    event = next(item for item in entities if item["entity_type"] == "event")
    assert event["actor"] == "沈砚"
    assert event["action"] == "打开"
    assert event["object"] == "旧铜铃"
    assert event["outcome"] == "密门因此显现"
    assert event["evidence_span"] == "沈砚打开旧铜铃，密门因此显现"
    assert event["source_chapter_id"] == "chapter-2"
    assert event["source_chapter_index"] == 2


def test_every_extracted_event_keeps_complete_event_shape():
    events = extract_story_entities("事件：宗门试炼开启。远处钟声响起。", {"event"})

    assert events
    for event in events:
        assert all(event[field] for field in ("actor", "action", "object", "outcome"))


def test_dialogue_intention_is_not_promoted_to_story_event():
    entities = extract_story_entities(
        "事件：关闭星门。林澈说：“这一次由我决定它的去向。”",
        {"event"},
    )

    names = _names_by_type(entities).get("event", set())
    assert "关闭星门" in names
    assert all("林澈说" not in name for name in names)


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


def test_chapter_dialogue_actions_do_not_become_fake_characters():
    text = (
        '影潮使低声说：“星灯一亮，我的影潮就会消失。”'
        '苏澜举起六棱密钥回答：“那就让雾海看见黎明。”'
        '顾言接回能量核心，喊道：“能源接通，转动密钥！”'
        '阿曜跃上控制台。'
    )

    entities = extract_story_entities(text, {"character", "prop"})
    by_type = _names_by_type(entities)

    assert {"影潮使", "苏澜", "顾言", "阿曜"}.issubset(by_type.get("character", set()))
    assert {"潮使", "密钥", "喊道", "顾言答"}.isdisjoint(by_type.get("character", set()))
    assert "六棱密钥" in by_type.get("prop", set())


def test_xianxia_continuity_copy_keeps_names_and_rejects_action_props():
    text = (
        "沈岚仍保持黑色高马尾、白蓝银纹长袍、玄霜玉佩和青霄剑的固定造型。"
        "在悬空云台上，沈岚面对师兄陆衡。陆衡质问她为何私入秘境。"
        "沈岚握紧同一枚玄霜玉佩回答：‘封印正在崩裂。’"
        "她以青霄剑斩断幻象，玉佩成为稳定剑阵的核心。"
    )

    entities = extract_story_entities(text, {"character", "prop"})
    by_type = _names_by_type(entities)

    assert {"沈岚", "陆衡"}.issubset(by_type.get("character", set()))
    assert {"沈岚仍", "陆衡质"}.isdisjoint(by_type.get("character", set()))
    assert {"玄霜玉佩", "青霄剑"}.issubset(by_type.get("prop", set()))
    assert {"她以青霄剑", "玉佩成为稳定剑"}.isdisjoint(by_type.get("prop", set()))


def test_five_chapter_xianxia_assets_exclude_costume_and_dialogue_fragments():
    chapters = [
        "二十二岁的女剑修沈岚，腰佩玄霜玉佩，背负青霄剑。她在暮雪中的太玄山门前立誓。",
        "沈岚进入蓝色灵雾缭绕的寒潭秘境，玉佩映出失落剑阵。她没有更换衣物。",
        "在悬空云台上，沈岚以青霄剑面对师兄陆衡。陆衡质问她为何私入秘境。",
        "沈岚在赤金剑阵中承受心魔。她以青霄剑斩断幻象，玉佩成为稳定剑阵的核心。",
        "北境霜河上空，沈岚将玉佩嵌入封印并挥剑。沈岚说：‘此剑封天，只为后来者仍能看见人间灯火。’",
    ]

    entities = [item for chapter in chapters for item in extract_story_entities(chapter)]
    by_type = _names_by_type(entities)

    assert {"沈岚", "陆衡"}.issubset(by_type.get("character", set()))
    assert {"太玄山门", "寒潭秘境", "悬空云台", "赤金剑阵", "北境霜河"}.issubset(
        by_type.get("scene", set())
    )
    assert {"玄霜玉佩", "青霄剑"}.issubset(by_type.get("prop", set()))
    assert {
        "腰佩玄霜玉佩", "女剑", "她没有更换衣", "她在赤金剑",
        "嵌入封印并挥剑", "此剑", "仍能看见人间灯",
    }.isdisjoint(by_type.get("prop", set()))


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


def test_narrated_dialogue_adverbs_do_not_become_character_entities():
    text = (
        "顾清霜抬起左腕。她低声说：“灯不是自然熄灭的。”"
        "顾清霜握紧霜衡剑。她对着黑暗清晰说道：“我会把真相带回人间。”"
        "顾清霜闭上眼睛。她睁眼说道：“回声只能困住过去。”"
        "顾清霜仰望穹顶，平静地说：“我会先完成阵法。”"
    )

    entities = extract_story_entities(text, {"character"})

    assert _names_by_type(entities).get("character", set()) == {"顾清霜"}


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
