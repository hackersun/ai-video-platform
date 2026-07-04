from app.services.asset_model_capabilities import decide_asset_generation_strategy


def test_standard_mode_allows_text_model_with_warning():
    strategy = decide_asset_generation_strategy(
        consistency_mode="standard",
        provider_name="minimax",
        model_id="image-01",
        entity_type="scene",
        has_anchor=True,
        model_limits={"images": 0, "at_reference": False},
    )

    assert strategy["mode"] == "text_contract"
    assert strategy["strict_blocking"] is False
    assert "参考图不会作为模型输入" in strategy["warnings"][0]


def test_strict_mode_requires_reference_capable_model_when_anchor_exists():
    strategy = decide_asset_generation_strategy(
        consistency_mode="strict",
        provider_name="minimax",
        model_id="image-01",
        entity_type="scene",
        has_anchor=True,
        model_limits={"images": 0, "at_reference": False},
    )

    assert strategy["mode"] == "blocked"
    assert strategy["strict_blocking"] is True
    assert strategy["blocking_reason"] == "严格一致模式需要支持参考图输入的图像模型"


def test_strict_mode_accepts_reference_capable_model():
    strategy = decide_asset_generation_strategy(
        consistency_mode="strict",
        provider_name="volcano",
        model_id="doubao-image-reference",
        entity_type="character",
        has_anchor=True,
        model_limits={"images": 1, "at_reference": False},
    )

    assert strategy["mode"] == "reference_image_contract"
    assert strategy["strict_blocking"] is False


def test_off_mode_keeps_text_prompt_compatibility():
    strategy = decide_asset_generation_strategy(
        consistency_mode="off",
        provider_name="minimax",
        model_id="image-01",
        entity_type="prop",
        has_anchor=True,
        model_limits={"images": 0, "at_reference": False},
    )

    assert strategy["mode"] == "text_prompt"
    assert strategy["strict_blocking"] is False
