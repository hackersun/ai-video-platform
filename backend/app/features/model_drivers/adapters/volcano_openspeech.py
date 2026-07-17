"""Volcano OpenSpeech driver using the production V3 request and parser path."""

from app.features.model_drivers.adapters._shared import completed_output, connection_test, unsupported_poll
from app.features.model_drivers.domain import SpeechCommand


class VolcanoOpenSpeechDriver:
    key = "volcano_openspeech_v3"
    capabilities = frozenset({"speech_generation"})

    async def test_connection(self, context):
        return await connection_test(
            lambda: self.submit(SpeechCommand(text="模型中心连接测试"), context),
            "豆包语音 V3 连接成功",
        )

    async def submit(self, command, context):
        from app.services.volcano_speech_tts import configure_volcano_speech_endpoint, synthesize_volcano_speech_v3

        params = dict(command.params)
        result = await synthesize_volcano_speech_v3(
            access_token=context.api_key,
            base_url=configure_volcano_speech_endpoint(context.base_url, dict(context.connection_params)) or "",
            text=command.text,
            voice=command.voice_id,
            speed=float(params.pop("speed", 1.0)),
            output_dir=str(params.pop("output_dir", "audio")),
        )
        return completed_output(result)

    poll = staticmethod(unsupported_poll)
