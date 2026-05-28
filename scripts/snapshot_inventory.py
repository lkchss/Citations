#!/usr/bin/env python3
"""Create an inventory of the local OpenAlex snapshot download."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DEFAULT_SNAPSHOT_DIR = Path("/root/sdb1/openalex/snapshot")
DEFAULT_OUTPUT = Path("/root/sdb1/openalex/derived/indexes/snapshot_inventory.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory OpenAlex snapshot files.")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_manifest(snapshot_dir: Path) -> dict[str, int]:
    manifest_path = snapshot_dir / "download_manifest.json"
    if not manifest_path.exists():
        return {}
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {entry["relative_path"]: int(entry["size"] or 0) for entry in entries}


def main() -> int:
    args = parse_args()
    expected_sizes = load_manifest(args.snapshot_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "relative_path",
        "bytes",
        "expected_bytes",
        "complete",
    ]
    rows = []
    for path in sorted((args.snapshot_dir / "data").rglob("*.gz")):
        relative = str(path.relative_to(args.snapshot_dir))
        size = path.stat().st_size
        expected = expected_sizes.get(relative, 0)
        rows.append(
            {
                "relative_path": relative,
                "bytes": size,
                "expected_bytes": expected,
                "complete": int(expected == 0 or size == expected),
            }
        )

    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"files={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
