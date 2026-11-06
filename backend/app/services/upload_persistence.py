"""Bounded upload persistence; legacy byte-based parsers remain explicitly capped."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from app.core.upload_stream import EmptyUpload, copy_upload
from app.services import media_persistence as media
from app.services.novel_import_service import parse_novel_import, validate_import_filename

NOVEL_IMPORT_MAX_BYTES = 10 * 1024 * 1024


async def persist_uploaded_media(upload, *, media_type: str, subdir: str,
                                 prefix: str, max_bytes: int) -> tuple[str, int]:
    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in media.ALLOWED_CONTENT_TYPES:
        raise ValueError(f"不支持的媒体类型: {media_type}")
    if content_type and content_type not in media.ALLOWED_CONTENT_TYPES[media_type]:
        raise ValueError(f"媒体类型不匹配: {content_type}")
    filename = f"{prefix}-{uuid4().hex}{media._extension_from_content_type(content_type, media_type)}"
    target = media._safe_static_path(subdir.strip("/"), filename)
    size = await copy_upload(upload, target, max_bytes=max_bytes)
    try:
        # Only the signature is needed to preserve wrong-header image detection.
        with target.open("rb") as source:
            extension = media._extension_for_payload(content_type, media_type, source.read(16))
        renamed = target.with_suffix(extension)
        target.rename(renamed)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return f"/static/{renamed.relative_to(media.STATIC_ROOT.resolve()).as_posix()}", size


async def persist_voice_sample(upload, voice_id: str, *, static_root: Path, directory: Path) -> str:
    extension = Path(upload.filename or "sample.wav").suffix.lower()
    if extension not in {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm"}:
        raise ValueError("仅支持 wav/mp3/m4a/aac/ogg/webm 音频样本")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{voice_id}{extension}"
    suffix = 1
    while target.exists():
        target = directory / f"{voice_id}-{suffix}{extension}"
        suffix += 1
    relative = target.resolve().relative_to(static_root.resolve()).as_posix()
    await copy_upload(upload, target, max_bytes=30 * 1024 * 1024)
    return f"/static/{relative}"


async def parse_uploaded_novel(upload):
    try:
        validate_import_filename(upload.filename or "")
        with TemporaryDirectory(prefix="avp-novel-import-") as directory:
            target = Path(directory) / "novel"
            await copy_upload(upload, target, max_bytes=NOVEL_IMPORT_MAX_BYTES)
            # Parser needs bytes for encoding detection. This allocation is bounded
            # to 10 MiB; multipart input is streamed to disk before parsing.
            return parse_novel_import(upload.filename, target.read_bytes())
    except EmptyUpload as exc:
        raise ValueError("上传文件为空") from exc
    finally:
        await upload.close()
