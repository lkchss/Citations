#!/usr/bin/env python3
"""Build a plain-text cache of OpenAlex work IDs from pulled JSONL gzip files."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


def iter_ids(directory: Path):
    for path in sorted(directory.glob("works_*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                work_id = json.loads(line).get("id")
                if work_id:
                    yield str(work_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a work-ID cache from OpenAlex JSONL gzip dirs.")
    parser.add_argument("--input-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ids: set[str] = set()
    for directory in args.input_dir:
        if directory.exists():
            ids.update(iter_ids(directory))

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = args.output_file.with_suffix(args.output_file.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for work_id in sorted(ids):
            handle.write(work_id)
            handle.write("\n")
    tmp_path.replace(args.output_file)
    print(f"ids={len(ids)} output={args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
