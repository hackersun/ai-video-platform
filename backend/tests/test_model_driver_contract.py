import json
import traceback

import pytest

from app.features.model_config import ModelProfileContract
from app.features.model_drivers import (
    DriverCapabilityError,
    DriverContext,
    DriverContextError,
    DriverExecutionError,
    DriverLimitError,
    DriverParameterError,
    DriverRegistrationError,
    DriverRegistry,
    DriverSchemaError,
    DriverSubmission,
    DriverTestResult,
    DriverUnavailableError,
    ImageCommand,
    TextCommand,
    execute_connection_test,
    execute_generation,
    execute_poll,
)
from app.features.model_drivers import registry as driver_registry


def profile(
    *,
    capabilities=frozenset({"text_generation"}),
    parameter_schema=None,
    limits=None,
    driver_key="echo_text_v1",
) -> ModelProfileContract:
    return ModelProfileContract(
        profile_version_id="profile-v1",
        provider_id="echo",
        api_model_id="echo-text",
        driver_key=driver_key,
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


def context(*, driver_key="echo_text_v1", profile_driver_key=None, **profile_options) -> DriverContext:
    return DriverContext(
        profile=profile(driver_key=profile_driver_key or driver_key, **profile_options),
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


class SecretBearingObject:
    def __repr__(self):
        return "SecretBearingObject(top-secret)"


class ChangingReprObject:
    def __init__(self):
        self.calls = 0

    def __repr__(self):
        self.calls += 1
        return f"ChangingReprObject({self.calls}:top-secret)"


SecretNamedObject = type("top-secret", (), {"__module__": __name__})


def unsupported_marker(value):
    qualified_type = f"{type(value).__module__}.{type(value).__qualname__}"
    return f"<unsupported:{qualified_type.replace('top-secret', '***')}>"


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
async def test_connection_evidence_is_recursively_sanitized_and_json_safe():
    class ComplexEvidenceDriver(EchoTextDriver):
        async def test_connection(self, driver_context):
            return DriverTestResult(
                status="connection_verified",
                message="ok",
                sanitized_evidence={
                    "top-secret-key": {
                        "set": {"safe", "top-secret"},
                        "tuple": ("top-secret", SecretBearingObject()),
                        "custom": SecretBearingObject(),
                    },
                },
            )

    result = await execute_connection_test(
        DriverRegistry([ComplexEvidenceDriver()]), "echo_text_v1", context()
    )
    evidence = result.sanitized_evidence
    encoded = json.dumps(evidence, sort_keys=True, allow_nan=False)

    assert "top-secret" not in encoded
    assert evidence["***-key"]["set"] == ["***", "safe"]
    assert evidence["***-key"]["tuple"] == ["***", unsupported_marker(SecretBearingObject())]
    assert evidence["***-key"]["custom"] == unsupported_marker(SecretBearingObject())


@pytest.mark.asyncio
async def test_unknown_objects_and_nonfinite_numbers_have_deterministic_strict_json_markers():
    changing = ChangingReprObject()
    default_object = object()
    secret_named = SecretNamedObject()
    raw_evidence = {
        "changing": changing,
        "default": default_object,
        "typed_object": secret_named,
        "nonfinite": [float("nan"), float("inf"), float("-inf")],
        "finite": [0, -3, 1.5, True, None],
    }

    class DeterministicEvidenceDriver(EchoTextDriver):
        async def test_connection(self, driver_context):
            return DriverTestResult("connection_verified", "ok", raw_evidence)

    registry = DriverRegistry([DeterministicEvidenceDriver()])
    first = (await execute_connection_test(registry, "echo_text_v1", context())).sanitized_evidence
    second = (await execute_connection_test(registry, "echo_text_v1", context())).sanitized_evidence

    assert first == second
    assert changing.calls == 0
    assert first["changing"] == unsupported_marker(changing)
    assert first["default"] == "<unsupported:builtins.object>"
    assert first["typed_object"] == unsupported_marker(secret_named)
    assert first["nonfinite"] == ["<non-finite:nan>", "<non-finite:+inf>", "<non-finite:-inf>"]
    assert first["finite"] == [0, -3, 1.5, True, None]
    json.dumps(first, sort_keys=True, allow_nan=False)


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


@pytest.mark.asyncio
async def test_connection_test_rejects_explicit_driver_key_that_disagrees_with_context():
    with pytest.raises(DriverContextError):
        await execute_connection_test(
            DriverRegistry([EchoTextDriver()]), "other_driver", context(driver_key="echo_text_v1")
        )


@pytest.mark.asyncio
async def test_generation_rejects_context_driver_key_that_disagrees_with_profile():
    with pytest.raises(DriverContextError):
        await execute_generation(
            DriverRegistry([EchoTextDriver()]),
            TextCommand(prompt="hello"),
            context(driver_key="other_driver", profile_driver_key="echo_text_v1"),
        )


def test_text_command_capability_cannot_be_forged_by_constructor():
    with pytest.raises(TypeError):
        TextCommand(capability="video_generation")


@pytest.mark.asyncio
async def test_generation_rejects_mutated_text_command_capability():
    command = TextCommand(prompt="hello")
    object.__setattr__(command, "capability", "video_generation")

    with pytest.raises(DriverCapabilityError):
        await execute_generation(DriverRegistry([EchoTextDriver()]), command, context())


def test_registry_rejects_duplicate_driver_keys():
    with pytest.raises(DriverRegistrationError, match="registered more than once"):
        DriverRegistry([EchoTextDriver(), EchoTextDriver()])


@pytest.mark.parametrize(
    ("driver_key", "capability"),
    [
        ("minimax_text_v2", "text_generation"),
        ("minimax_image_v1", "image_generation"),
        ("minimax_speech_v2", "speech_generation"),
        ("volcano_ark_image_v3", "image_generation"),
        ("volcano_ark_video_v3", "video_generation"),
        ("volcano_openspeech_v3", "speech_generation"),
        ("dashscope_video_v1", "video_generation"),
        ("local_ffmpeg_v1", "media_render"),
        ("qiniu_kodo_v1", "object_storage"),
    ],
)
def test_builtin_driver_registry_has_current_production_drivers(driver_key, capability):
    driver = driver_registry.build_builtin_driver_registry().require(driver_key)

    assert capability in driver.capabilities


def test_driver_context_repr_excludes_decrypted_secrets():
    assert "top-secret" not in repr(context())


def test_driver_context_exposes_provider_connection_inputs_without_secret_repr():
    driver_context = DriverContext(
        profile=profile(driver_key="minimax_text_v2"),
        driver_key="minimax_text_v2",
        connection_id="connection-1",
        secrets={"api_key": "top-secret", "api_secret": "second-secret"},
        base_url="https://provider.example.test/v1",
        connection_params={"region": "cn"},
    )

    assert driver_context.api_key == "top-secret"
    assert driver_context.api_secret == "second-secret"
    assert driver_context.base_url == "https://provider.example.test/v1"
    assert driver_context.connection_params == {"region": "cn"}
    assert "top-secret" not in repr(driver_context)
    assert "second-secret" not in repr(driver_context)


@pytest.mark.asyncio
async def test_numeric_bounds_on_string_parameter_schema_fail_closed():
    with pytest.raises(DriverSchemaError):
        await execute_generation(
            DriverRegistry([EchoTextDriver()]),
            TextCommand(prompt="hello", params={"style": "formal"}),
            context(parameter_schema={
                "type": "object",
                "properties": {"style": {"type": "string", "minimum": 1}},
                "additionalProperties": False,
            }),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["connection", "generation", "poll"])
async def test_driver_exceptions_are_secret_safe_without_raw_cause(operation):
    class ProviderError(RuntimeError):
        def __init__(self):
            super().__init__("provider returned top-secret")
            self.evidence = {
                "top-secret-key": {
                    "set": {"safe", "top-secret"},
                    "tuple": ("top-secret", SecretBearingObject()),
                    "custom": SecretBearingObject(),
                }
            }

    class ExplodingDriver(EchoTextDriver):
        async def test_connection(self, driver_context):
            raise ProviderError()

        async def submit(self, command, driver_context):
            raise ProviderError()

        async def poll(self, provider_task_id, driver_context):
            raise ProviderError()

    registry = DriverRegistry([ExplodingDriver()])
    with pytest.raises(DriverExecutionError) as raised:
        if operation == "connection":
            await execute_connection_test(registry, "echo_text_v1", context())
        elif operation == "generation":
            await execute_generation(registry, TextCommand(prompt="hello"), context())
        else:
            await execute_poll(registry, "provider-job-1", context())

    error = raised.value
    formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    encoded_evidence = json.dumps(error.sanitized_evidence, sort_keys=True, allow_nan=False)

    assert "top-secret" not in str(error)
    assert "top-secret" not in repr(error)
    assert "top-secret" not in formatted
    assert "top-secret" not in encoded_evidence
    assert error.__cause__ is None
    provider_evidence = error.sanitized_evidence["provider_evidence"]["***-key"]
    assert provider_evidence["set"] == ["***", "safe"]
    assert provider_evidence["tuple"] == ["***", unsupported_marker(SecretBearingObject())]
    assert provider_evidence["custom"] == unsupported_marker(SecretBearingObject())
