"""MiniMax speech driver delegating to MiniMaxService's shared TTS request builder."""

from app.features.model_drivers.adapters._shared import completed_output, connection_test, unsupported_poll
from app.features.model_drivers.domain import SpeechCommand


class MiniMaxSpeechDriver:
    key = "minimax_speech_v2"
    capabilities = frozenset({"speech_generation"})

    async def test_connection(self, context):
        return await connection_test(
            lambda: self.submit(SpeechCommand(text="模型中心连接测试", voice_id="male-qn-qingse"), context),
            "MiniMax 语音模型连接成功",
        )

    async def submit(self, command, context):
        from app.services.minimax_service import MiniMaxService

        result = await MiniMaxService(context.api_key, context.base_url).text_to_speech(
            text=command.text,
            model=context.profile.api_model_id,
            voice_id=command.voice_id,
            **dict(command.params),
        )
        return completed_output(result)

    poll = staticmethod(unsupported_poll)
