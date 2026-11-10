"""Bounded disk I/O for spooled uploads and object-storage request bodies."""
from pathlib import Path
from typing import AsyncIterator, Protocol
import anyio

CHUNK_BYTES = 1024 * 1024


class UploadReader(Protocol):
    async def read(self, size: int) -> bytes: ...


class UploadTooLarge(ValueError):
    pass


class EmptyUpload(ValueError):
    pass


async def copy_upload(upload: UploadReader, target: Path, *, max_bytes: int) -> int:
    """Copy at most max_bytes; never trust multipart size metadata.

    Create exclusively, and remove only our partial file on any failure,
    including cancellation. The caller owns closing the upload itself.
    """
    if max_bytes <= 0:
        raise ValueError("上传大小限制必须为正数")
    output = await anyio.open_file(target, "xb")
    total = 0
    try:
        async with output:
            while chunk := await upload.read(CHUNK_BYTES):
                total += len(chunk)
                if total > max_bytes:
                    raise UploadTooLarge("媒体文件超过本地持久化大小限制")
                await output.write(chunk)
            if not total:
                raise EmptyUpload("媒体文件为空")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return total


async def iter_file_chunks(path: Path) -> AsyncIterator[bytes]:
    async with await anyio.open_file(path, "rb") as source:
        while chunk := await source.read(CHUNK_BYTES):
            yield chunk
