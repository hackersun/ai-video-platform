from app.features.model_config.certification_execution import CertificationTarget, _context
from app.models.model_center import ModelConnection, ModelProfile, ModelProfileVersion, ModelProvider


def test_certification_context_routes_generic_cloud_provider_by_provider_code(monkeypatch) -> None:
    provider = ModelProvider(
        id="agent-plan-provider",
        code="volcano-agent-plan",
        display_name="火山方舟 Agent Plan",
        provider_family="cloud",
        enabled=True,
    )
    profile = ModelProfile(
        id="agent-plan-profile",
        provider_id=provider.id,
        profile_key="ark-code-latest",
        display_name="Ark Code Latest",
        enabled=True,
    )
    version = ModelProfileVersion(
        id="agent-plan-version",
        model_id=profile.id,
        version=1,
        api_model_id="ark-code-latest",
        driver_key="legacy_text_v1",
        capabilities=["text_generation"],
        input_contract={},
        output_contract={},
        parameter_schema={},
        default_params={},
        limits={},
        pricing={},
        contract_version="v1",
        status="published",
        checksum="a" * 64,
    )
    connection = ModelConnection(
        id="agent-plan-connection",
        user_id="user-1",
        provider_id=provider.id,
        name="Agent Plan",
        endpoint_overrides={"base_url": "https://ark.cn-beijing.volces.com/api/coding/v3"},
        connection_params={},
        status="draft",
    )
    monkeypatch.setattr(ModelConnection, "get_api_key_decrypted", lambda _row: "secret")
    monkeypatch.setattr(ModelConnection, "get_api_secret_decrypted", lambda _row: "")

    context = _context(CertificationTarget(version, profile, provider, connection))

    assert context.connection_params["provider_name"] == "volcano_agent_plan"
    assert context.base_url == "https://ark.cn-beijing.volces.com/api/coding/v3"
