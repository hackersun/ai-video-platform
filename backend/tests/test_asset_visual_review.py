from app.services.asset_visual_review import review_asset_against_contract, retry_prompt_advice


def test_scene_review_flags_missing_lighting_direction_and_color_palette() -> None:
    contract = {
        "id": "visual-contract-old-post-office",
        "entity_type": "scene",
        "entity_name": "旧邮局",
        "continuity_axes": {
            "lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯",
            "color_palette": "冷蓝雨光与暖黄钨丝灯",
        },
        "spatial_layout": {"fixed_elements": ["左侧正门", "右侧木柜台"]},
    }
    prompt = "旧邮局建立镜头，空间里保留左侧正门和右侧木柜台，雨夜电影感。"

    review = review_asset_against_contract(contract, "establishing", prompt)

    assert review["status"] == "needs_retry"
    missing_fields = {issue["field"] for issue in review["issues"]}
    assert {"lighting_direction", "color_palette"} <= missing_fields
    assert any(issue["expected"] == "门外冷蓝雨光，室内右上方暖黄灯" for issue in review["issues"])
    assert any(issue["expected"] == "冷蓝雨光与暖黄钨丝灯" for issue in review["issues"])


def test_retry_advice_for_lighting_direction_and_spatial_layout() -> None:
    contract = {
        "continuity_axes": {"lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯"},
        "spatial_layout": {"fixed_elements": ["右侧木柜台"]},
    }
    issues = [
        {
            "field": "lighting_direction",
            "category": "continuity_axes",
            "expected": "门外冷蓝雨光，室内右上方暖黄灯",
        },
        {"field": "spatial_layout", "category": "spatial_layout", "expected": "右侧木柜台"},
    ]

    advice = retry_prompt_advice(issues, contract)

    assert "必须保持光源方向" in advice
    assert "右侧木柜台" in advice
