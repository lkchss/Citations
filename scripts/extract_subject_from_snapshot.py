#!/usr/bin/env python3
"""Extract works for one OpenAlex field from a local works snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT_WORKS_DIR = Path("/root/sdb1/openalex/snapshot/data/works")


def normalize_id(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("https://openalex.org/fields/"):
        return value.rsplit("/", 1)[-1]
    if value.startswith("https://openalex.org/F"):
        return value.rsplit("F", 1)[-1]
    if value.startswith("F") and value[1:].isdigit():
        return value[1:]
    return value


def subject_matches(work: dict[str, Any], field_ids: set[str], field_names: set[str]) -> bool:
    topic = work.get("primary_topic") or {}
    field = topic.get("field") or {}
    field_id = normalize_id(str(field.get("id") or ""))
    field_name = str(field.get("display_name") or "").casefold()
    return (field_id in field_ids) or (field_name in field_names)


def iter_snapshot_files(snapshot_works_dir: Path, max_files: int):
    files = sorted(snapshot_works_dir.rglob("*.gz"))
    if max_files:
        return files[:max_files]
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract one OpenAlex field from snapshot files.")
    parser.add_argument("--snapshot-works-dir", type=Path, default=DEFAULT_SNAPSHOT_WORKS_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--field-id", action="append", default=[])
    parser.add_argument("--field-name", action="append", default=[])
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--records-per-output", type=int, default=100_000)
    args = parser.parse_args()
    if not args.field_id and not args.field_name:
        raise SystemExit("Pass at least one --field-id or --field-name.")
    return args


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = iter_snapshot_files(args.snapshot_works_dir, args.max_files)
    field_ids = {normalize_id(value) for value in args.field_id if normalize_id(value)}
    field_names = {value.casefold() for value in args.field_name if value.strip()}

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
                    if not subject_matches(work, field_ids, field_names):
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
        "field_ids": sorted(field_ids),
        "field_names": sorted(field_names),
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
