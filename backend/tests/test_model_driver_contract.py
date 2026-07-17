import pytest

from app.features.model_config import ModelProfileContract
from app.features.model_drivers import (
    DriverCapabilityError,
    DriverContext,
    DriverLimitError,
    DriverParameterError,
    DriverRegistry,
    DriverSchemaError,
    DriverSubmission,
    DriverTestResult,
    DriverUnavailableError,
    ImageCommand,
    TextCommand,
    execute_connection_test,
    execute_generation,
)


def profile(
    *,
    capabilities=frozenset({"text_generation"}),
    parameter_schema=None,
    limits=None,
) -> ModelProfileContract:
    return ModelProfileContract(
        profile_version_id="profile-v1",
        provider_id="echo",
        api_model_id="echo-text",
        driver_key="echo_text_v1",
        capabilities=capabilities,
        input_contract={},
        output_contract={},
        parameter_schema=parameter_schema or {
            "type": "object",
            "properties": {"temperature": {"type": "number", "minimum": 0, "maximum": 1}},
            "additionalProperties": False,
        },
        default_params={},
        limits=limits or {"max_prompt_chars": 12},
        pricing={},
        prompt_profile_key=None,
        contract_version="v1",
    )


def context(*, driver_key="echo_text_v1", **profile_options) -> DriverContext:
    return DriverContext(
        profile=profile(**profile_options),
        driver_key=driver_key,
        connection_id="connection-1",
        secrets={"api_key": "top-secret"},
    )


class EchoTextDriver:
    key = "echo_text_v1"
    capabilities = frozenset({"text_generation"})

    async def test_connection(self, driver_context):
        return DriverTestResult(status="connection_verified", message="ok", sanitized_evidence={})

    async def submit(self, command, driver_context):
        return DriverSubmission(status="completed", provider_task_id=None, output={"text": command.prompt})

    async def poll(self, provider_task_id, driver_context):
        raise AssertionError("sync driver must not poll")


class QueuedTextDriver(EchoTextDriver):
    key = "queued_text_v1"

    async def submit(self, command, driver_context):
        return DriverSubmission(status="submitted", provider_task_id="provider-job-1", output={})


@pytest.mark.asyncio
async def test_same_registry_executes_connection_test_and_completed_generation():
    registry = DriverRegistry([EchoTextDriver()])

    tested = await execute_connection_test(registry, "echo_text_v1", context())
    generated = await execute_generation(registry, TextCommand(prompt="hello"), context())

    assert tested.status == "connection_verified"
    assert generated == DriverSubmission(status="completed", provider_task_id=None, output={"text": "hello"})


@pytest.mark.asyncio
async def test_generation_preserves_async_submission_without_polling():
    registry = DriverRegistry([QueuedTextDriver()])

    result = await execute_generation(registry, TextCommand(prompt="hello"), context(driver_key="queued_text_v1"))

    assert result.status == "submitted"
    assert result.provider_task_id == "provider-job-1"


@pytest.mark.asyncio
async def test_generation_rejects_driver_without_command_capability():
    with pytest.raises(DriverCapabilityError):
        await execute_generation(
            DriverRegistry([EchoTextDriver()]),
            ImageCommand(prompt="draw"),
            context(capabilities=frozenset({"image_generation"})),
        )


@pytest.mark.asyncio
async def test_unknown_driver_fails_closed():
    with pytest.raises(DriverUnavailableError):
        await execute_generation(DriverRegistry([]), TextCommand(prompt="hello"), context())


@pytest.mark.asyncio
async def test_connection_evidence_and_message_do_not_expose_decrypted_secret():
    class LeakyDriver(EchoTextDriver):
        async def test_connection(self, driver_context):
            secret = driver_context.secrets["api_key"]
            return DriverTestResult(
                status="connection_verified",
                message=f"used {secret}",
                sanitized_evidence={"authorization": secret, "nested": {"token": secret}},
            )

    result = await execute_connection_test(DriverRegistry([LeakyDriver()]), "echo_text_v1", context())

    assert "top-secret" not in result.message
    assert "top-secret" not in str(result.sanitized_evidence)
    assert result.sanitized_evidence == {"authorization": "***", "nested": {"token": "***"}}


@pytest.mark.asyncio
async def test_generation_rejects_undeclared_parameter():
    with pytest.raises(DriverParameterError):
        await execute_generation(
            DriverRegistry([EchoTextDriver()]), TextCommand(prompt="hello", params={"model": "unsafe"}), context()
        )


@pytest.mark.asyncio
async def test_generation_rejects_unknown_parameter_schema():
    with pytest.raises(DriverSchemaError):
        await execute_generation(
            DriverRegistry([EchoTextDriver()]),
            TextCommand(prompt="hello"),
            context(parameter_schema={"type": "object", "patternProperties": {}}),
        )


@pytest.mark.asyncio
async def test_generation_rejects_prompt_above_profile_limit():
    with pytest.raises(DriverLimitError):
        await execute_generation(DriverRegistry([EchoTextDriver()]), TextCommand(prompt="too many words"), context())


@pytest.mark.asyncio
async def test_generation_rejects_unknown_limit_configuration():
    with pytest.raises(DriverLimitError):
        await execute_generation(
            DriverRegistry([EchoTextDriver()]),
            TextCommand(prompt="hello"),
            context(limits={"max_prompt_chars": 12, "unrecognized": 1}),
        )
