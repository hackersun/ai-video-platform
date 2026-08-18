from pathlib import Path

import pytest


def test_persist_local_media_file_returns_stable_static_url(tmp_path, monkeypatch):
    from app.services import media_persistence

    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path / "static")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video-bytes")

    url = media_persistence.persist_local_media_file(
        source,
        media_type="video",
        subdir="synthesis",
        prefix="final",
    )

    assert url.startswith("/static/generated/synthesis/final-")
    assert media_persistence.local_static_path_for_url(url).read_bytes() == b"video-bytes"


@pytest.mark.asyncio
async def test_synthesis_result_persists_video_cover_and_duration(tmp_path, monkeypatch):
    from app.services import media_persistence
    from app.services import synthesis_executor
    from app.services.synthesis_executor import SynthesisExecutor, SubtitleSegment

    monkeypatch.setattr(media_persistence, "STATIC_ROOT", tmp_path / "static")
    monkeypatch.setattr(synthesis_executor, "is_dev_mode", lambda: False)
    executor = SynthesisExecutor(work_dir=str(tmp_path / "work"))
    executor._ffmpeg_available = True
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")

    async def fake_burn(_video_path, _subtitles, output_filename=None, subtitle_style=None):
        output = executor.work_dir / (output_filename or "burned.mp4")
        output.write_bytes(b"burned-video")
        return str(output)

    async def fake_cover(_video_path, output_filename=None, timestamp=None):
        output = executor.work_dir / (output_filename or "cover.jpg")
        output.write_bytes(b"cover-image")
        return str(output)

    monkeypatch.setattr(executor, "burn_subtitles", fake_burn)
    monkeypatch.setattr(executor, "generate_cover", fake_cover)
    monkeypatch.setattr(executor, "_probe_duration", lambda _path: 4.5)

    result = await executor.synthesize(
        [str(source)],
        subtitles=[SubtitleSegment(text="字幕", start_time=0, end_time=4.5)],
    )

    assert result["status"] == "succeeded"
    assert result["video_url"].startswith("/static/generated/synthesis/")
    assert result["cover_url"].startswith("/static/generated/synthesis/")
    assert result["duration_seconds"] == 4.5


@pytest.mark.asyncio
async def test_synthesize_endpoint_marks_completed_ffmpeg_output_publishable(monkeypatch):
    from app.api.v1.endpoints.synthesis import SynthesisExecuteRequest, synthesize_video
    from app.services.synthesis_executor import SynthesisExecutor

    class FakeDB:
        def __init__(self):
            self.job = None

        def add(self, job):
            self.job = job

        async def commit(self):
            return None

        async def refresh(self, job):
            from app.core.time_utils import utc_now

            job.created_at = utc_now()
            job.updated_at = job.created_at

    async def fake_synthesize(self, **_kwargs):
        return {
            "job_id": "synthesis-test-job",
            "status": "succeeded",
            "video_url": "/static/generated/synthesis/final-test.mp4",
            "cover_url": "/static/generated/synthesis/cover-test.jpg",
            "duration_seconds": 4.5,
        }

    monkeypatch.setattr(SynthesisExecutor, "synthesize", fake_synthesize)
    response = await synthesize_video(
        request=SynthesisExecuteRequest(video_urls=["/static/generated/videos/source.mp4"]),
        db=FakeDB(),
        user_id="user-test",
    )

    assert response.render_status == "rendered"
    assert response.render_backend == "ffmpeg_local"
    assert response.output_kind == "final_video"
    assert response.is_publishable is True
    assert response.publication_blockers == []


def test_generated_ass_subtitles_use_a_chinese_font_by_default(tmp_path):
    from app.services.synthesis_executor import SynthesisExecutor, SubtitleSegment

    executor = SynthesisExecutor(work_dir=str(tmp_path / "work"))
    subtitle_file = tmp_path / "subtitles.ass"
    executor._generate_ass_subtitle(
        subtitle_file,
        [SubtitleSegment(text="青岚宗山门", start_time=0, end_time=2)],
    )

    content = subtitle_file.read_text(encoding="utf-8")
    assert "Style: Default,Noto Sans CJK SC," in content
    assert "青岚宗山门" in content
