from __future__ import annotations

import argparse
import json
from typing import Any, Dict


def build_fixture_payload(stamp: str | None = None) -> Dict[str, Any]:
    suffix = stamp or "dry-run"
    title = f"Series Studio Acceptance - 星轨少年 - {suffix}"
    return {
        "novel": {
            "title": title,
            "genre": "连续动漫",
            "description": "少年林澈在废城天台发现星轨罗盘，三集内完成觉醒、追踪与第一次对决。",
            "tags": ["series-studio-acceptance", "anime", "multi-episode"],
        },
        "chapters": [
            {
                "ref": "chapter-1",
                "title": "第一章 天台星轨",
                "chapter_number": 1,
                "content": "林澈在雨后的废城天台捡到星轨罗盘，罗盘投出蓝金色星线。",
            },
            {
                "ref": "chapter-2",
                "title": "第二章 旧站追光",
                "chapter_number": 2,
                "content": "林澈带着罗盘穿过旧地铁站，发现反派留下的黑色星尘。",
            },
            {
                "ref": "chapter-3",
                "title": "第三章 月台初战",
                "chapter_number": 3,
                "content": "林澈在月台保护同伴，第一次用星轨罗盘展开护盾。",
            },
        ],
        "story_bible": {
            "title": f"{title} Production Bible",
            "style": "蓝金赛璐璐二维动漫，干净线条，废城冷色和星轨暖光稳定对比。",
            "worldview": "星轨罗盘能读取城市遗留的能量路线。",
            "character_rules": [
                {
                    "name": "林澈",
                    "role": "主角",
                    "appearance": "黑发少年，蓝色短外套，左手腕戴星轨罗盘。",
                    "voice": "male-qn-qingse",
                },
                {
                    "name": "许眠",
                    "role": "同伴",
                    "appearance": "短发少女，橙色雨衣，携带旧相机。",
                    "voice": "female-shaonv",
                },
            ],
            "scene_rules": [
                {"name": "废城天台", "visual": "雨后积水、蓝灰楼群、远处霓虹残光。"},
                {"name": "旧地铁站", "visual": "废弃月台、断裂灯箱、黑色星尘。"},
            ],
            "prop_rules": [
                {"name": "星轨罗盘", "visual": "腕带式蓝金罗盘，展开时有环形星线。"},
            ],
        },
        "entities": [
            {"ref": "character-main", "entity_type": "character", "name": "林澈"},
            {"ref": "character-support", "entity_type": "character", "name": "许眠"},
            {"ref": "scene-rooftop", "entity_type": "scene", "name": "废城天台"},
            {"ref": "prop-compass", "entity_type": "prop", "name": "星轨罗盘"},
        ],
        "assets": [
            {"entity_ref": "character-main", "view_key": "front", "name": "林澈正面定稿"},
            {"entity_ref": "character-main", "view_key": "side", "name": "林澈侧面定稿"},
            {"entity_ref": "scene-rooftop", "view_key": "establishing", "name": "废城天台全景定稿"},
            {"entity_ref": "prop-compass", "view_key": "main", "name": "星轨罗盘主视图"},
        ],
        "series_plan": {
            "target_episode_count": 3,
            "chapters_per_episode": 1,
            "target_duration_seconds": 45,
            "style": "蓝金赛璐璐二维动漫",
            "persist": True,
        },
        "workflow": {
            "title": f"{title} Episode 1",
            "novel_id_ref": "novel",
            "chapter_id_ref": "chapter-1",
        },
        "shots": [
            {
                "shot_number": 1,
                "duration": 4,
                "prompt": "林澈站在雨后废城天台，星轨罗盘发出蓝金光。",
                "dialogue": "林澈：这条光线在指路。",
                "entity_refs": {
                    "characters": [{"ref": "character-main", "name": "林澈"}],
                    "scenes": [{"ref": "scene-rooftop", "name": "废城天台"}],
                    "props": [{"ref": "prop-compass", "name": "星轨罗盘"}],
                },
            }
        ],
        "acceptance_urls": [
            "/novels/{novel_id}",
            "/studio?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
            "/studio/cards?novel_id={novel_id}",
            "/studio/continuity-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
            "/studio/shot-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stamp", default=None)
    args = parser.parse_args()
    payload = build_fixture_payload(args.stamp)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
