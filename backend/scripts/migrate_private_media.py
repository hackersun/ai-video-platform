#!/usr/bin/env python3
"""Copy legacy media into a private prefix, verify hashes and register objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
import sys
from datetime import timedelta
from pathlib import Path, PurePosixPath
from uuid import NAMESPACE_URL, uuid5


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import sync_engine
from app.core.time_utils import utc_now
from app.features.private_media.domain import lifecycle_policy
from app.models.private_media import MediaObject


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="无损迁移历史媒体到私有存储前缀")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--lifecycle-class", choices=("original", "process", "final"), required=True)
    parser.add_argument("--storage-provider", required=True)
    parser.add_argument("--apply", action="store_true", help="执行复制、校验和数据库登记；默认仅试运行")
    return parser.parse_args()


def _manifest_rows(args: argparse.Namespace) -> list[dict]:
    rows = []
    for source in sorted(path for path in args.source_root.rglob("*") if path.is_file()):
        relative = source.relative_to(args.source_root).as_posix()
        policy = lifecycle_policy(
            args.lifecycle_class, user_id=args.user_id,
            filename=PurePosixPath(relative).name,
        )
        parent = PurePosixPath(relative).parent
        object_key = str(PurePosixPath(policy.object_key).parent / parent / source.name)
        rows.append({
            "source": relative, "canonical_url": f"/static/generated/{relative}",
            "object_key": object_key, "sha256": _sha256(source),
            "size_bytes": source.stat().st_size,
            "content_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            "retention_days": policy.retention_days,
        })
    return rows


def _copy_and_verify(args: argparse.Namespace, rows: list[dict]) -> int:
    copied = 0
    for row in rows:
        source = args.source_root / row["source"]
        target = args.destination_root / row["object_key"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or _sha256(target) != row["sha256"]:
            shutil.copy2(source, target)
        if _sha256(target) != row["sha256"]:
            raise RuntimeError(f"哈希校验失败：{source}")
        copied += 1
    return copied


def _register(args: argparse.Namespace, rows: list[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    with Session(sync_engine) as session:
        for row in rows:
            existing = session.scalar(select(MediaObject).where(
                MediaObject.storage_provider == args.storage_provider,
                MediaObject.object_key == row["object_key"],
            ))
            if existing is not None:
                if existing.sha256 != row["sha256"] or existing.user_id != args.user_id:
                    raise RuntimeError(f"目标对象已存在但所有者或哈希不一致：{row['object_key']}")
                skipped += 1
                continue
            media_kind = (row["content_type"].split("/", 1)[0] or "binary")
            session.add(MediaObject(
                id=str(uuid5(NAMESPACE_URL, f"{args.storage_provider}:{row['object_key']}")),
                user_id=args.user_id, media_kind=media_kind,
                lifecycle_class=args.lifecycle_class,
                storage_provider=args.storage_provider, object_key=row["object_key"],
                canonical_url=row["canonical_url"], sha256=row["sha256"],
                size_bytes=row["size_bytes"], content_type=row["content_type"],
                retention_until=utc_now() + timedelta(days=row["retention_days"]),
            ))
            inserted += 1
        session.commit()
    return inserted, skipped


def main() -> None:
    args = _arguments()
    source_root = args.source_root.resolve()
    if not source_root.is_dir():
        raise SystemExit("源媒体目录不存在")
    args.source_root = source_root
    rows = _manifest_rows(args)
    if not args.apply:
        print(f"试运行：发现 {len(rows)} 个媒体文件，不会复制或修改数据库")
        return
    copied = _copy_and_verify(args, rows)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    inserted, skipped = _register(args, rows)
    print(f"已复制并校验 {copied} 个，已登记 {inserted} 个，跳过 {skipped} 个")
    print("源文件未删除；请至少观察一个发布版本后再按单独审批清理")


if __name__ == "__main__":
    main()
