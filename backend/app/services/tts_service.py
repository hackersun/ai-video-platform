"""
语音合成服务 - Edge TTS
"""

import asyncio
import uuid
import os
from typing import Optional, List, Dict
from datetime import datetime
import edge_tts
from fastapi import HTTPException


class TTSService:
    """Edge TTS 语音合成服务"""

    # 支持的中文语音
    VOICES = {
        "zh-CN-XiaoxiaoNeural": {"name": "晓晓", "gender": "女", "style": "温柔女声"},
        "zh-CN-YunxiNeural": {"name": "云希", "gender": "男", "style": "阳光男声"},
        "zh-CN-XiaoyiNeural": {"name": "晓伊", "gender": "女", "style": "甜美女声"},
        "zh-CN-YunyangNeural": {"name": "云扬", "gender": "男", "style": "专业男声"},
        "zh-TW-HsiaoChenNeural": {"name": "晓臻", "gender": "女", "style": "台湾女声"},
        "zh-TW-YuJhongNeural": {"name": "雨仲", "gender": "男", "style": "台湾男声"},
    }

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "storage", "tts"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_speech(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        output_file: str = None,
        speed: float = 1.0,
        pitch: str = "0Hz",
        volume: str = "0%"
    ) -> Dict:
        """
        生成语音

        Args:
            text: 要转换的文本
            voice: 语音选择
            output_file: 输出文件路径
            speed: 语速 (0.5-2.0)
            pitch: 音调调整
            volume: 音量调整

        Returns:
            生成结果信息
        """
        if not text or len(text.strip()) == 0:
            raise HTTPException(status_code=400, detail="文本不能为空")

        if voice not in self.VOICES:
            raise HTTPException(status_code=400, detail=f"不支持的语音: {voice}")

        # 生成输出文件名
        if not output_file:
            filename = f"{uuid.uuid4()}.mp3"
            output_file = os.path.join(self.output_dir, filename)

        try:
            # 构建communicate对象
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=f"{'+' if speed > 1 else '-'}{int(abs(speed - 1) * 100)}%",
                pitch=pitch,
                volume=volume
            )

            # 保存音频文件
            await communicate.save(output_file)

            # 获取文件信息
            file_size = os.path.getsize(output_file)

            return {
                "success": True,
                "audio_url": f"/storage/tts/{os.path.basename(output_file)}",
                "file_path": output_file,
                "file_size": file_size,
                "voice": voice,
                "voice_name": self.VOICES[voice]["name"],
                "duration": await self._get_audio_duration(output_file),
                "text_length": len(text)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"语音生成失败: {str(e)}")

    async def _get_audio_duration(self, file_path: str) -> float:
        """获取音频时长（秒）"""
        # 简单估算：假设平均每秒 20 个字符
        # 实际需要使用 ffprobe 获取准确时长
        # TODO: 使用 ffprobe 获取准确时长
        return 0

    def get_voice_list(self) -> List[Dict]:
        """获取可用语音列表"""
        return [
            {
                "id": voice_id,
                "name": info["name"],
                "gender": info["gender"],
                "style": info["style"]
            }
            for voice_id, info in self.VOICES.items()
        ]

    async def batch_generate(
        self,
        texts: List[str],
        voice: str = "zh-CN-XiaoxiaoNeural",
        speed: float = 1.0
    ) -> List[Dict]:
        """批量生成语音"""
        results = []
        for text in texts:
            result = await self.generate_speech(
                text=text,
                voice=voice,
                speed=speed
            )
            results.append(result)
        return results


# 实例化服务
tts_service = TTSService()