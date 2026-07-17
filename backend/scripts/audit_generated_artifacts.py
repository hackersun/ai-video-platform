from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from app.services.generated_artifact_policy import classify_generated_artifact


SCAN_ROOTS = [
    Path("backend/static/dev"),
    Path("backend/static/generated"),
    Path("backend/static/exports"),
    Path("backend/static/starter"),
    Path("output/playwright"),
    Path("output/live-anime"),
]


def audit(root: Path) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for scan_root in SCAN_ROOTS:
        absolute = root / scan_root
        if not absolute.exists():
            continue
        for item in absolute.rglob("*"):
            if not item.is_file():
                continue
            rel = item.relative_to(root)
            classification = classify_generated_artifact(rel)
            bucket = summary.setdefault(classification.bucket, {"count": 0, "bytes": 0})
            bucket["count"] += 1
            bucket["bytes"] += item.stat().st_size
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    summary = audit(root)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for bucket, values in sorted(summary.items()):
        size_mb = values["bytes"] / 1024 / 1024
        print(f"{bucket}: {values['count']} files, {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
