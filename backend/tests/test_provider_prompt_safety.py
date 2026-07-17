from app.services.novel_continuity import _scoped_state_machine_summary
from app.services.provider_prompt_safety import (
    build_provider_video_prompt_fallback,
    provider_text_safety_error_message,
    sanitize_provider_video_prompt,
)


def test_provider_video_prompt_rewrites_moderation_risky_story_terms() -> None:
    result = sanitize_provider_video_prompt("失踪档案被抹除，角色拒绝牺牲别人，画面出现血迹。")

    assert result["sanitized"] is True
    safe_prompt = result["prompt"]
    assert "失踪" not in safe_prompt
    assert "抹除" not in safe_prompt
    assert "牺牲" not in safe_prompt
    assert "血迹" not in safe_prompt
    assert "档案" not in safe_prompt
    assert "待查资料" in safe_prompt
    assert "隐藏" in safe_prompt
    assert "付出代价" in safe_prompt


def test_provider_video_prompt_strips_internal_story_timeline_blocks() -> None:
    result = sanitize_provider_video_prompt(
        "任务: shot_video\n"
        "事件时间线:\n"
        "- name: 星锚罗盘指向失踪档案\n"
        "- name: 许澜阻止第四次钟声\n"
        "Story Bible状态机: 人物3，场景4，事件40，后续生成必须继承当前状态。\n"
        "人物当前状态:\n"
        "- 许澜: 已登场\n"
        "当前镜头:\n"
        "- 镜头描述: 许澜发现海潮钟倒转，站在灯塔阴影里。\n"
        "补充要求:\n"
        "- 整部小说连续性锁: 【整部小说连续性锁】\n"
        "当前章节：秦砚翻开失踪档案，发现自己曾经被列入已抹除名单。\n"
        "下一章不可矛盾约束：第四次钟声不能提前。\n"
        "最近事件线：第4章 秦砚翻开失踪档案。\n"
        "- 小说级系列种子: 123\n"
    )

    safe_prompt = result["prompt"]
    assert "星锚罗盘指向" not in safe_prompt
    assert "下一章不可矛盾约束" not in safe_prompt
    assert "最近事件线" not in safe_prompt
    assert "失踪" not in safe_prompt
    assert "抹除" not in safe_prompt
    assert "第四次" not in safe_prompt
    assert "档案" not in safe_prompt
    assert "当前镜头" in safe_prompt
    assert "反向运转" in safe_prompt
    assert "整部小说连续性锁" in safe_prompt
    assert "保持角色外观" in safe_prompt


def test_provider_video_prompt_compacts_asset_locks_and_removes_local_paths() -> None:
    prompt = (
        "任务: shot_video\n"
        "故事风格: 连续动漫\n"
        "当前镜头:\n"
        "- 镜头描述: 许澈在钟楼旁举起铜灯，集市被云灯照亮。\n"
        "- 参考图: /static/generated/images/shot-e23f8d9c-f23a5eea5a6549a5ab16ab9d6cb487be.jpg\n"
        "- 资产版本锁: 许澈(character): /static/dev/image-asset-lock-a.png；"
        "钟楼(scene): /static/dev/image-asset-lock-b.png；"
        "钟楼(scene): /static/dev/image-asset-lock-c.png；"
        "铜灯(prop): /static/dev/image-asset-lock-d.png；"
        "铜灯(prop): /static/dev/image-asset-lock-e.png；"
        "是父亲(character): /static/dev/image-asset-lock-f.png；"
        "下室门后(character): /static/dev/image-asset-lock-g.png；"
        "说铜灯不(character): /static/dev/image-asset-lock-h.png\n"
        "视频一致性约束:\n"
        "- 角色视觉DNA锁: 保持发型服装一致。\n"
        "【锁定资产一致性约束】\n"
        "- character: 许澈, 严格保持外观与锁定资产一致\n"
        "- scene: 钟楼, 严格保持外观与锁定资产一致\n"
        "- scene: 钟楼, 严格保持外观与锁定资产一致\n"
        "- prop: 铜灯, 严格保持外观与锁定资产一致\n"
        "- prop: 铜灯, 严格保持外观与锁定资产一致\n"
        "- character: 是父亲, 严格保持外观与锁定资产一致\n"
        "- character: 下室门后, 严格保持外观与锁定资产一致\n"
        "对白同步约束（硬性）：说话人：说铜灯不；口型表演对应台词：『（旁白）集市又喧闹起来。』\n"
    )

    result = sanitize_provider_video_prompt(prompt)

    assert result["sanitized"] is True
    safe_prompt = result["prompt"]
    assert len(safe_prompt) < len(prompt)
    assert "/static/" not in safe_prompt
    assert "image-asset-lock" not in safe_prompt
    assert safe_prompt.count("钟楼") <= 3
    assert safe_prompt.count("铜灯") <= 3
    assert "许澈" in safe_prompt
    assert "钟楼" in safe_prompt
    assert "铜灯" in safe_prompt
    assert "是父亲" not in safe_prompt
    assert "下室门后" not in safe_prompt
    assert "说铜灯不" not in safe_prompt
    assert "说话人：旁白" in safe_prompt


def test_provider_text_safety_error_message_handles_volcano_invalid_content_text() -> None:
    error = Exception(
        "ContentGenerationError(message='One or more parameters specified in the request "
        "are not valid: Invalid content.text Request id: 0217834731512920.', code='InvalidParameter')"
    )

    message = provider_text_safety_error_message(error)

    assert message is not None
    assert "云端视频模型拒绝" in message


def test_provider_video_prompt_fallback_is_ultra_safe_visual_prompt() -> None:
    result = build_provider_video_prompt_fallback()

    prompt = result["prompt"]
    assert result["sanitized"] is True
    assert "reference image" in prompt
    assert "lip movement" in prompt
    for risky in ["失踪", "抹除", "档案", "第四次", "牺牲", "血"]:
        assert risky not in prompt


def test_scoped_state_machine_summary_excludes_future_chapter_events() -> None:
    summary = _scoped_state_machine_summary(
        {
            "event_timeline": [
                {"chapter_number": 1, "name": "许澜发现海潮钟倒转"},
                {"chapter_number": 3, "name": "秦砚确认自己曾被抹除"},
                {"chapter_number": 4, "name": "许澜阻止第四次钟声"},
            ],
        },
        current_snapshot={
            "chapter_id": "chapter-1",
            "chapter_number": 1,
            "title": "第一章",
            "events": [{"name": "许澜发现海潮钟倒转"}],
        },
        chapter_number=1,
    )

    assert "许澜发现海潮钟倒转" in summary
    assert "秦砚确认自己曾被抹除" not in summary
    assert "许澜阻止第四次钟声" not in summary
