#!/usr/bin/env python3
"""Extract economics works from a local OpenAlex works snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT_WORKS_DIR = Path("/root/sdb1/openalex/snapshot/data/works")
DEFAULT_OUTPUT_DIR = Path("/root/sdb1/openalex/derived/economics/works")
ECONOMICS_FIELD_IDS = {
    "20",
    "https://openalex.org/fields/20",
    "https://openalex.org/F20",
}


def is_economics(work: dict[str, Any]) -> bool:
    topic = work.get("primary_topic") or {}
    field = topic.get("field") or {}
    field_id = str(field.get("id") or "")
    return field_id in ECONOMICS_FIELD_IDS


def iter_snapshot_files(snapshot_works_dir: Path, max_files: int):
    files = sorted(snapshot_works_dir.rglob("*.gz"))
    if max_files:
        return files[:max_files]
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract economics works from OpenAlex snapshot files.")
    parser.add_argument("--snapshot-works-dir", type=Path, default=DEFAULT_SNAPSHOT_WORKS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--records-per-output", type=int, default=100_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = iter_snapshot_files(args.snapshot_works_dir, args.max_files)

    output_index = 1
    output_count = 0
    seen = 0
    kept = 0
    handle = None
    try:
        for path in files:
            with gzip.open(path, "rt", encoding="utf-8") as input_handle:
                for line in input_handle:
                    if not line.strip():
                        continue
                    seen += 1
                    work = json.loads(line)
                    if not is_economics(work):
                        continue
                    if handle is None or output_count >= args.records_per_output:
                        if handle is not None:
                            handle.close()
                        out = args.output_dir / f"works_{output_index:08d}.jsonl.gz"
                        handle = gzip.open(out, "wt", encoding="utf-8")
                        output_index += 1
                        output_count = 0
                    handle.write(json.dumps(work, ensure_ascii=False, separators=(",", ":")))
                    handle.write("\n")
                    output_count += 1
                    kept += 1
            print(f"processed={path} seen={seen} kept={kept}", flush=True)
    finally:
        if handle is not None:
            handle.close()

    summary = {
        "snapshot_works_dir": str(args.snapshot_works_dir),
        "output_dir": str(args.output_dir),
        "files_processed": len(files),
        "records_seen": seen,
        "records_kept": kept,
    }
    (args.output_dir / "extract_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
