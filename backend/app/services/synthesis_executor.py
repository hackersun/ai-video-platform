"""
FFmpeg执行器 - 真实音视频合成

支持多镜头拼接、音频混合、字幕烧录、封面生成等功能。
FFmpeg不可用时自动降级为开发模式模拟。
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.dev_generation import dev_synthesis_url, is_dev_mode
from app.core.time_utils import utc_now
from pydantic import BaseModel


class SubtitleSegment(BaseModel):
    """字幕片段"""
    text: str
    start_time: float  # 秒
    end_time: float  # 秒
    style: Optional[Dict[str, Any]] = None


class SynthesisExecutor:
    """FFmpeg执行器，用于真实音视频合成"""

    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="synthesis_"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._ffmpeg_available = None  # lazy check

    @property
    def ffmpeg_available(self) -> bool:
        """检查FFmpeg是否可用"""
        if self._ffmpeg_available is None:
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                self._ffmpeg_available = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                self._ffmpeg_available = False
        return self._ffmpeg_available

    def _run_ffmpeg(self, args: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """执行FFmpeg命令"""
        if not self.ffmpeg_available:
            raise RuntimeError("FFmpeg不可用，请安装FFmpeg或启用DEV_MODE")
        return subprocess.run(args, capture_output=True, timeout=timeout, text=True)

    async def concatenate_videos(
        self,
        video_urls: List[str],
        output_filename: Optional[str] = None
    ) -> str:
        """拼接多个视频为单个视频文件"""
        if not video_urls:
            raise ValueError("video_urls不能为空")

        # DEV模式：返回模拟URL
        if not self.ffmpeg_available or is_dev_mode():
            job_id = str(uuid4())
            return dev_synthesis_url(job_id)

        output_filename = output_filename or f"concat_{uuid4().hex[:8]}.mp4"
        output_path = self.work_dir / output_filename

        # 下载所有视频到临时文件
        temp_files: List[Path] = []
        for i, url in enumerate(video_urls):
            temp_file = self.work_dir / f"video_{i}_{uuid4().hex[:8]}.mp4"
            await self._download_file(url, temp_file)
            temp_files.append(temp_file)

        try:
            # 创建文件列表
            list_file = self.work_dir / "concat_list.txt"
            with open(list_file, "w") as f:
                for tf in temp_files:
                    f.write(f"file '{tf.absolute()}'\n")

            # 执行拼接
            args = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file.absolute()),
                "-c", "copy",
                "-movflags", "+faststart",
                str(output_path.absolute())
            ]
            result = self._run_ffmpeg(args)

            if result.returncode != 0:
                # 尝试重新编码拼接
                args = [
                    "ffmpeg", "-y",
                    "-i", f"concat:{'|'.join(str(tf.absolute()) for tf in temp_files)}",
                    "-c", "copy",
                    "-movflags", "+faststart",
                    str(output_path.absolute())
                ]
                result = self._run_ffmpeg(args)

            if result.returncode != 0:
                # 最后尝试：完全重新编码
                args = [
                    "ffmpeg", "-y",
                    "-i", f"concat:{'|'.join(str(tf.absolute()) for tf in temp_files)}",
                    "-c:v", "libx264", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(output_path.absolute())
                ]
                result = self._run_ffmpeg(args, timeout=600)

            if result.returncode != 0:
                raise RuntimeError(f"视频拼接失败: {result.stderr}")

            return str(output_path.absolute())

        finally:
            # 清理临时文件
            for tf in temp_files:
                tf.unlink(missing_ok=True)
            list_file.unlink(missing_ok=True)

    async def mix_audio(
        self,
        audio_urls: List[str],
        output_filename: Optional[str] = None,
        volumes: Optional[List[float]] = None
    ) -> str:
        """混合多个音频文件"""
        if not audio_urls:
            raise ValueError("audio_urls不能为空")

        # DEV模式：返回模拟URL
        if not self.ffmpeg_available or is_dev_mode():
            job_id = str(uuid4())
            return dev_audio_url(job_id)

        output_filename = output_filename or f"mixed_{uuid4().hex[:8]}.mp3"
        output_path = self.work_dir / output_filename

        # 下载所有音频到临时文件
        temp_files: List[Path] = []
        for i, url in enumerate(audio_urls):
            temp_file = self.work_dir / f"audio_{i}_{uuid4().hex[:8]}.mp3"
            await self._download_file(url, temp_file)
            temp_files.append(temp_file)

        try:
            if len(temp_files) == 1:
                # 单个音频直接复制
                shutil.copy(temp_files[0], output_path)
                return str(output_path.absolute())

            # 构建混合滤镜
            filter_parts = []
            inputs = []
            for i, tf in enumerate(temp_files):
                inputs.extend(["-i", str(tf.absolute())])
                vol = (volumes[i] if volumes and i < len(volumes) else 1.0)
                filter_parts.append(f"[{i}:a]volume={vol}[a{i}]")

            filter_complex = ";".join(filter_parts)
            amix_inputs = "[a0]"
            for i in range(1, len(temp_files)):
                amix_inputs += f"[a{i}]"
            filter_complex += f";{amix_inputs}amix=inputs={len(temp_files)}:duration=longest[out]"

            args = [
                "ffmpeg", "-y"
            ] + inputs + [
                "-filter_complex", filter_complex,
                "-map", "[out]",
                "-ar", "44100", "-ac", "2",
                str(output_path.absolute())
            ]
            result = self._run_ffmpeg(args)

            if result.returncode != 0:
                # 简化混合
                args = [
                    "ffmpeg", "-y",
                    "-i", str(temp_files[0].absolute()),
                    "-i", str(temp_files[1].absolute()),
                    "-filter_complex", "amix=inputs=2:duration=longest[out]",
                    "-map", "[out]",
                    str(output_path.absolute())
                ]
                result = self._run_ffmpeg(args)

            if result.returncode != 0:
                raise RuntimeError(f"音频混合失败: {result.stderr}")

            return str(output_path.absolute())

        finally:
            for tf in temp_files:
                tf.unlink(missing_ok=True)

    async def burn_subtitles(
        self,
        video_path: str,
        subtitles: List[SubtitleSegment],
        output_filename: Optional[str] = None,
        subtitle_style: Optional[Dict[str, Any]] = None
    ) -> str:
        """烧录字幕到视频"""
        if not subtitles:
            return video_path

        # DEV模式：返回原视频
        if not self.ffmpeg_available or is_dev_mode():
            return video_path

        output_filename = output_filename or f"burned_{uuid4().hex[:8]}.mp4"
        output_path = self.work_dir / output_filename

        # 生成ASS字幕文件
        subtitle_file = self.work_dir / f"subs_{uuid4().hex[:8]}.ass"
        self._generate_ass_subtitle(subtitle_file, subtitles, subtitle_style)

        try:
            # 获取视频信息
            probe_result = self._run_ffmpeg([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                video_path
            ])
            resolution = probe_result.stdout.strip().split("x")
            width = int(resolution[0]) if resolution else 1920
            height = int(resolution[1]) if len(resolution) > 1 else 1080

            # 字幕样式
            font_size = max(18, min(width, height) // 40)
            margin_v = height - int(height * 0.15)

            args = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"ass={subtitle_file.absolute()}",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(output_path.absolute())
            ]
            result = self._run_ffmpeg(args, timeout=600)

            if result.returncode != 0:
                raise RuntimeError(f"字幕烧录失败: {result.stderr}")

            return str(output_path.absolute())

        finally:
            subtitle_file.unlink(missing_ok=True)

    def _generate_ass_subtitle(
        self,
        output_path: Path,
        subtitles: List[SubtitleSegment],
        style: Optional[Dict[str, Any]] = None
    ) -> None:
        """生成ASS格式字幕文件"""
        font_name = style.get("font", "Arial") if style else "Arial"
        font_size = style.get("font_size", 48) if style else 48
        primary_color = style.get("primary_color", "&H00FFFFFF") if style else "&H00FFFFFF"
        outline_color = style.get("outline_color", "&H00000000") if style else "&H00000000"

        lines = [
            "[Script Info]",
            f"Title: Generated Subtitles",
            f"ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{font_name},{font_size},{primary_color},{outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        for seg in subtitles:
            start = self._format_ass_time(seg.start_time)
            end = self._format_ass_time(seg.end_time)
            text = seg.text.replace("\n", "\\N")
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    def _format_ass_time(self, seconds: float) -> str:
        """将秒数格式化为ASS时间格式 (H:MM:SS.CS)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    async def generate_cover(
        self,
        video_path: str,
        output_filename: Optional[str] = None,
        timestamp: Optional[float] = None
    ) -> str:
        """从视频提取一帧作为封面"""
        # DEV模式：返回模拟URL
        if not self.ffmpeg_available or is_dev_mode():
            job_id = str(uuid4())
            return dev_image_url(job_id, "cover")

        output_filename = output_filename or f"cover_{uuid4().hex[:8]}.jpg"
        output_path = self.work_dir / output_filename

        timestamp = timestamp or 1.0  # 默认取第1秒

        args = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            "-movflags", "+faststart",
            str(output_path.absolute())
        ]
        result = self._run_ffmpeg(args, timeout=60)

        if result.returncode != 0:
            raise RuntimeError(f"封面生成失败: {result.stderr}")

        return str(output_path.absolute())

    async def synthesize(
        self,
        video_urls: List[str],
        audio_urls: Optional[List[str]] = None,
        subtitles: Optional[List[SubtitleSegment]] = None,
        output_format: str = "mp4",
        quality: str = "high"
    ) -> Dict[str, Any]:
        """完整合成流程：拼接视频 + 混合音频 + 烧录字幕 + 生成封面"""
        job_id = str(uuid4())
        output_filename = f"final_{job_id}.{output_format}"
        output_path = self.work_dir / output_filename

        # DEV模式：返回模拟结果
        if not self.ffmpeg_available or is_dev_mode():
            video_url = dev_synthesis_url(job_id)
            cover_url = dev_image_url(job_id, "cover")
            return {
                "job_id": job_id,
                "status": "succeeded",
                "video_url": video_url,
                "cover_url": cover_url,
                "duration_seconds": 0,
                "output_path": None,
            }

        try:
            # 1. 拼接视频
            if len(video_urls) == 1:
                concatenated_video = video_urls[0]
            else:
                concatenated_video = await self.concatenate_videos(video_urls)

            # 2. 混合音频（如有）
            if audio_urls:
                mixed_audio = await self.mix_audio(audio_urls)
                # 3. 合并视频音频
                final_video = await self._merge_video_audio(
                    concatenated_video, mixed_audio,
                    output_filename
                )
            else:
                final_video = concatenated_video

            # 4. 烧录字幕（如有）
            if subtitles:
                final_video = await self.burn_subtitles(
                    final_video, subtitles,
                    output_filename.replace(f".{output_format}", "_burned.mp4")
                )

            # 5. 生成封面
            cover_path = await self.generate_cover(final_video)

            return {
                "job_id": job_id,
                "status": "succeeded",
                "video_url": final_video,
                "cover_url": cover_path,
                "duration_seconds": 0,  # TODO: 从视频获取实际时长
                "output_path": str(output_path),
            }

        except Exception as e:
            return {
                "job_id": job_id,
                "status": "failed",
                "error": str(e),
                "video_url": None,
                "cover_url": None,
                "duration_seconds": 0,
                "output_path": None,
            }

    async def _merge_video_audio(
        self,
        video_path: str,
        audio_path: str,
        output_filename: str
    ) -> str:
        """合并视频和音频流"""
        output_path = self.work_dir / output_filename

        args = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",  # 保留原视频编码
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",  # 使用较短者的长度
            "-movflags", "+faststart",
            str(output_path.absolute())
        ]
        result = self._run_ffmpeg(args, timeout=600)

        if result.returncode != 0:
            raise RuntimeError(f"视频音频合并失败: {result.stderr}")

        return str(output_path.absolute())

    async def _download_file(self, url: str, dest_path: Path) -> None:
        """下载文件到本地"""
        if url.startswith("http"):
            # 使用curl下载
            result = subprocess.run(
                ["curl", "-L", "-s", "-o", str(dest_path), url],
                timeout=300,
                text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"下载失败 {url}: {result.stderr}")
        else:
            # 本地文件路径
            src = Path(url)
            if src.exists():
                shutil.copy(src, dest_path)
            else:
                raise FileNotFoundError(f"文件不存在: {url}")

    def cleanup(self) -> None:
        """清理临时目录"""
        try:
            shutil.rmtree(self.work_dir)
        except Exception:
            pass


def dev_audio_url(job_id: str) -> str:
    """DEV模式下的模拟音频URL"""
    return dev_synthesis_url(job_id)  # 复用视频模拟


def dev_image_url(job_id: str, label: str = "image") -> str:
    """DEV模式下的模拟图片URL"""
    from app.core.dev_generation import dev_image_url as dev_img_url
    return dev_img_url(job_id, label)