#!/usr/bin/env python3
"""Monitor OpenAlex snapshot and API-shard download progress."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_OPENALEX_DIR = Path("/root/sdb1/openalex")
WORKS_SNAPSHOT_BYTES = 639_189_333_248


LOG_RE = re.compile(
    r"completed=(?P<completed>\d+)/(?P<total>\d+).*?mbps=(?P<mbps>[0-9.]+)"
)


def dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def human_bytes(value: float) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def parse_snapshot_log(path: Path) -> dict[str, float | int | None]:
    last = None
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = LOG_RE.search(line)
            if match:
                last = match
    if not last:
        return {"completed": None, "total": None, "mbps": None}
    return {
        "completed": int(last.group("completed")),
        "total": int(last.group("total")),
        "mbps": float(last.group("mbps")),
    }


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_status(root: Path) -> None:
    snapshot_dir = root / "snapshot"
    size = dir_size(snapshot_dir)
    log_status = parse_snapshot_log(snapshot_dir / "download_works.log")
    remaining = max(WORKS_SNAPSHOT_BYTES - size, 0)
    mbps = log_status.get("mbps")
    eta_hours = None
    if isinstance(mbps, float) and mbps > 0:
        eta_hours = remaining / (mbps * 1024 * 1024) / 3600

    print("Snapshot works")
    print(f"  downloaded_bytes: {human_bytes(size)}")
    print(f"  estimated_total:  {human_bytes(WORKS_SNAPSHOT_BYTES)}")
    print(f"  completed_files:  {log_status.get('completed')}/{log_status.get('total')}")
    print(f"  measured_rate:    {mbps} MiB/s")
    print(f"  eta_hours:        {eta_hours:.2f}" if eta_hours is not None else "  eta_hours:        unknown")


def api_shard_status(root: Path) -> None:
    shard_root = root / "economics_field20_shards_balanced"
    if not shard_root.exists():
        return
    print("\nEconomics API shards")
    for directory in sorted(path for path in shard_root.iterdir() if path.is_dir()):
        checkpoint = read_json(directory / "checkpoint.json")
        if not checkpoint:
            continue
        print(
            "  ".join(
                [
                    directory.name,
                    f"seen={checkpoint.get('records_seen')}",
                    f"written={checkpoint.get('records_written')}",
                    f"skipped={checkpoint.get('records_skipped_existing')}",
                    f"updated={checkpoint.get('updated_at')}",
                ]
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor OpenAlex downloads.")
    parser.add_argument("--openalex-dir", type=Path, default=DEFAULT_OPENALEX_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_status(args.openalex_dir)
    api_shard_status(args.openalex_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
