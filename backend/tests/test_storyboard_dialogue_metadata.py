from app.api.v1.endpoints.storyboards import (
    apply_script_scene_beats_to_template_shots,
    build_dialogue_metadata,
    dedupe_repeated_shot_dialogues,
    ensure_shot_dialogue_subtitle,
    extract_dialogue_speaker,
    extract_script_scene_beats,
    split_multi_speaker_dialogue_shots,
    strip_dialogue_speaker,
)
from app.services.storyboard_template_service import build_template_shots


def test_extract_dialogue_speaker_and_spoken_text():
    dialogue = "林澈：这道光，在回应我。"

    assert extract_dialogue_speaker(dialogue) == "林澈"
    assert strip_dialogue_speaker(dialogue) == "这道光，在回应我。"


def test_build_dialogue_metadata_resolves_character_ref():
    metadata = build_dialogue_metadata(
        {"dialogue": "林澈：这道光，在回应我。"},
        [{"name": "林澈", "entity_id": "entity-1", "character_id": "char-1", "voice": "voice-a"}],
        dialogue_source="script",
    )

    assert metadata["dialogue_speaker"] == "林澈"
    assert metadata["dialogue_spoken_text"] == "这道光，在回应我。"
    assert metadata["dialogue_source"] == "script"
    assert metadata["speaker_entity_id"] == "entity-1"
    assert metadata["speaker_character_id"] == "char-1"
    assert metadata["speaker_voice"] == "voice-a"


def test_template_shots_include_dialogue_metadata():
    template = {
        "id": "dialogue-template",
        "name": "对白模板",
        "description": "测试模板",
        "shots": [
            {
                "duration": 4,
                "shot_type": "dialogue",
                "camera_angle": "medium",
                "camera_movement": "static",
                "emotion": "tense",
                "lighting": "natural",
                "color_grading": "cinematic",
                "visual_focus": "主角确认线索",
                "dialogue_role": "角色",
            }
        ],
    }

    shots = build_template_shots(
        template=template,
        source_title="第一章",
        source_content="林澈在雨夜发现铜铃异常。",
        story_context={"characters": [{"name": "林澈"}], "props": [{"name": "铜铃"}]},
    )

    assert shots[0]["dialogue"].startswith("林澈：")
    assert shots[0]["extra_data"]["dialogue_speaker"] == "林澈"
    assert shots[0]["extra_data"]["dialogue_source"] == "template_story_beat"


def test_extract_script_scene_beats_supports_plain_producer_script_format():
    content = """第1场
场景类型：外景
时长：15秒
地点：旧车站站台，雨夜
人物：孙剑；沈岚
戏剧核心：铜铃无风自鸣，制造异常开端
画面描述：孙剑站在雨夜旧车站，手中旧铜铃突然响了三下。
对话/旁白：
旁白：铜铃在无人触碰的情况下，自己响了三下。
沈岚：【低声、平稳】别急，先看这份记录。
镜头序列：
1. 特写：旧铜铃被孙剑攥紧的手指微颤
2. 近景：孙剑猛然抬眼
音效/音乐提示：三声清脆铜铃声
字幕要点：铜铃自鸣 / 三声
"""

    scenes = extract_script_scene_beats(content)

    assert len(scenes) == 1
    assert scenes[0]["people"] == "孙剑；沈岚"
    assert scenes[0]["visual"] == "孙剑站在雨夜旧车站，手中旧铜铃突然响了三下"
    assert scenes[0]["dialogues"] == [
        "旁白：铜铃在无人触碰的情况下，自己响了三下。",
        "沈岚：别急，先看这份记录。",
    ]
    assert "镜头序列" not in scenes[0]["beat"]
    assert "字幕要点" not in scenes[0]["beat"]


def test_script_scene_beats_replace_template_guidance_in_shot_prompts():
    shots = [
        {
            "shot_number": 1,
            "duration": 4,
            "prompt": "第一章，镜头序列：1. 特写，服饰、发型、随身道具和视觉 DNA",
            "dialogue": None,
            "visual_description": "服饰、发型、随身道具和视觉 DNA。",
            "extra_data": {},
        }
    ]
    scenes = [
        {
            "title": "第1场",
            "people": "孙剑；沈岚",
            "visual": "孙剑站在雨夜旧车站，手中旧铜铃突然响了三下",
            "dialogues": ["沈岚：别急，先看这份记录。"],
            "beat": "第1场。人物：孙剑；沈岚。画面：孙剑站在雨夜旧车站，手中旧铜铃突然响了三下。对白：沈岚：别急，先看这份记录。",
        }
    ]

    updated = apply_script_scene_beats_to_template_shots(shots, scenes, source_title="第一章 雨巷铜铃")

    assert "镜头序列" not in updated[0]["prompt"]
    assert "服饰、发型、随身道具和视觉 DNA" not in updated[0]["prompt"]
    assert updated[0]["prompt"] == "第一章 雨巷铜铃，第1场，孙剑站在雨夜旧车站，手中旧铜铃突然响了三下"
    assert updated[0]["dialogue"] == "沈岚：别急，先看这份记录。"
    assert updated[0]["extra_data"]["dialogue_source"] == "script_scene_dialogue"


def test_split_multi_speaker_dialogue_shots_groups_by_speaker():
    shots = [
        {
            "shot_number": 6,
            "duration": 4,
            "prompt": "双人中景，沈岚劝阻，孙剑回应。",
            "dialogue": "沈岚：别急，先看这份记录。\n孙剑：我来确认出口。\n孙剑：你守住信号灯。",
            "visual_description": "沈岚与孙剑在雨夜站台交谈。",
            "extra_data": {"dialogue_source": "script_scene_dialogue"},
        }
    ]

    split = split_multi_speaker_dialogue_shots(shots)

    assert len(split) == 2
    assert [shot["shot_number"] for shot in split] == [1, 2]
    assert split[0]["dialogue"] == "沈岚：别急，先看这份记录。"
    assert split[1]["dialogue"] == "孙剑：我来确认出口。你守住信号灯。"
    assert split[0]["duration"] == 3
    assert split[1]["duration"] == 3
    assert split[0]["extra_data"]["dialogue_segment_count"] == 2
    assert split[1]["extra_data"]["dialogue_segment_index"] == 2


def test_dedupe_repeated_shot_dialogues_uses_shot_specific_context():
    shots = [
        {
            "shot_number": 1,
            "prompt": "无人列车从雨雾中滑出。",
            "dialogue": "旁白：这一夜，所有离站的列车都没有司机。",
            "extra_data": {"source_beat": "无人列车驶出雨雾"},
        },
        {
            "shot_number": 2,
            "prompt": "驾驶室漆黑一片，空无一人。",
            "dialogue": "旁白：这一夜，所有离站的列车都没有司机。",
            "extra_data": {"source_beat": "驾驶室空无一人"},
        },
    ]

    updated = dedupe_repeated_shot_dialogues(shots)

    assert updated[0]["dialogue"] == "旁白：这一夜，所有离站的列车都没有司机。"
    assert updated[1]["dialogue"] == "（旁白）驾驶室空无一人。"
    assert updated[1]["extra_data"]["subtitle_text"] == "（旁白）驾驶室空无一人。"
    assert updated[1]["extra_data"]["dialogue_rewritten_reason"] == "duplicate_dialogue"


def test_ensure_shot_dialogue_subtitle_adds_narration_fallback():
    shot = {
        "prompt": "第一章，林澈发现星灯，钩子开场",
        "visual_description": "旧邮局里蓝色星灯亮起。",
        "extra_data": {"source_beat": "林澈看见写着安禾名字的银色信封"},
    }

    ensure_shot_dialogue_subtitle(shot)

    assert shot["dialogue"] == "（旁白）林澈看见写着安禾名字的银色信封"
    assert shot["extra_data"]["subtitle_text"] == shot["dialogue"]
    assert shot["extra_data"]["dialogue_speaker"] == "旁白"
    assert shot["extra_data"]["dialogue_source"] == "story_beat_narration_fallback"


def test_ensure_shot_dialogue_subtitle_preserves_existing_dialogue():
    shot = {
        "dialogue": "林澈：我们只剩三分钟。",
        "extra_data": {"source_beat": "林澈发现星灯"},
    }

    ensure_shot_dialogue_subtitle(shot)

    assert shot["dialogue"] == "林澈：我们只剩三分钟。"
    assert shot["extra_data"]["subtitle_text"] == "林澈：我们只剩三分钟。"
    assert shot["extra_data"].get("dialogue_source") is None
