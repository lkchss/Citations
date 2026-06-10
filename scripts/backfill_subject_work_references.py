#!/usr/bin/env python3
"""Backfill work_references parts for existing subject table_parts.

Existing subject tables include works, authors, and counts_by_year. This script
adds `part_XXXX_work_references.csv.gz` by scanning the OpenAlex works snapshot
and retaining references for work IDs already present in selected subject
`works` parts.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable


DEFAULT_SUBJECT_ROOT = Path("/root/sdb1/openalex/subjects")
DEFAULT_SNAPSHOT_WORKS_DIR = Path("/root/sdb1/openalex/snapshot/data/works")
TARGET_SUBJECT_BY_WORK_ID: dict[str, str] = {}


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def read_csv_gz(path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def load_subject_work_ids(subject_root: Path, subjects: list[str]) -> dict[str, str]:
    subject_by_work_id: dict[str, str] = {}
    for subject in subjects:
        table_parts = subject_root / subject / "tables_parts"
        if not table_parts.exists():
            raise SystemExit(f"Missing table_parts for subject={subject}: {table_parts}")
        before = len(subject_by_work_id)
        for path in sorted(table_parts.glob("part_*_works.csv.gz")):
            for row in read_csv_gz(path):
                work_id = row.get("work_id") or ""
                if work_id:
                    subject_by_work_id[work_id] = subject
        log(
            f"loaded subject={subject} work_ids={len(subject_by_work_id) - before:,} "
            f"total={len(subject_by_work_id):,}"
        )
    return subject_by_work_id


def chunked(items: list[Path], chunks: int) -> list[list[Path]]:
    return [items[index::chunks] for index in range(chunks)]


def scan_files(files: list[Path], output_root: Path, part_id: int) -> dict[str, object]:
    handles: dict[str, object] = {}
    writers: dict[str, csv.DictWriter] = {}
    final_paths: dict[str, Path] = {}
    tmp_paths: dict[str, Path] = {}
    records_seen = 0
    target_records_seen = 0
    references_written = 0
    subject_counts: dict[str, int] = {}

    def writer_for(subject: str) -> csv.DictWriter:
        if subject not in writers:
            path = output_root / subject / "tables_parts" / f"part_{part_id:04d}_work_references.csv.gz"
            tmp_path = path.with_name(f"{path.name}.tmp")
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = gzip.open(tmp_path, "wt", encoding="utf-8", newline="")
            writer = csv.DictWriter(handle, fieldnames=["work_id", "referenced_work_id"])
            writer.writeheader()
            handles[subject] = handle
            writers[subject] = writer
            final_paths[subject] = path
            tmp_paths[subject] = tmp_path
        return writers[subject]

    try:
        for path in files:
            with gzip.open(path, "rt", encoding="utf-8") as input_handle:
                for line in input_handle:
                    if not line.strip():
                        continue
                    records_seen += 1
                    work = json.loads(line)
                    work_id = str(work.get("id") or "")
                    subject = TARGET_SUBJECT_BY_WORK_ID.get(work_id)
                    if not subject:
                        continue
                    target_records_seen += 1
                    references = work.get("referenced_works") or []
                    if not references:
                        continue
                    writer = writer_for(subject)
                    for referenced_work_id in references:
                        writer.writerow(
                            {
                                "work_id": work_id,
                                "referenced_work_id": str(referenced_work_id),
                            }
                        )
                        references_written += 1
                        subject_counts[subject] = subject_counts.get(subject, 0) + 1
    finally:
        for handle in handles.values():
            handle.close()

    for subject, tmp_path in tmp_paths.items():
        tmp_path.replace(final_paths[subject])

    return {
        "part_id": part_id,
        "files_processed": len(files),
        "records_seen": records_seen,
        "target_records_seen": target_records_seen,
        "references_written": references_written,
        "subject_counts": subject_counts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, default=DEFAULT_SUBJECT_ROOT)
    parser.add_argument("--snapshot-works-dir", type=Path, default=DEFAULT_SNAPSHOT_WORKS_DIR)
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing work_references parts for selected subjects.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    subjects = args.subject or [
        path.parent.name
        for path in sorted(args.subject_root.glob("*/tables_parts"))
    ]
    if not subjects:
        raise SystemExit("No subjects selected.")

    for subject in subjects:
        existing = list((args.subject_root / subject / "tables_parts").glob("part_*_work_references.csv.gz"))
        if existing and not args.overwrite:
            raise SystemExit(
                f"Existing work_references parts for subject={subject}; pass --overwrite to replace."
            )
        if args.overwrite:
            for path in existing:
                path.unlink()

    global TARGET_SUBJECT_BY_WORK_ID
    TARGET_SUBJECT_BY_WORK_ID = load_subject_work_ids(args.subject_root, subjects)
    files = sorted(args.snapshot_works_dir.rglob("*.gz"))
    if args.max_files:
        files = files[: args.max_files]
    workers = max(1, min(args.workers, len(files)))
    chunks = chunked(files, workers)

    totals: dict[str, object] = {
        "subject_root": str(args.subject_root),
        "snapshot_works_dir": str(args.snapshot_works_dir),
        "subjects": subjects,
        "target_work_ids": len(TARGET_SUBJECT_BY_WORK_ID),
        "input_files": len(files),
        "workers": workers,
        "records_seen": 0,
        "target_records_seen": 0,
        "references_written": 0,
        "subject_counts": {},
        "parts": [],
    }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(scan_files, chunk, args.subject_root, index)
            for index, chunk in enumerate(chunks)
            if chunk
        ]
        for future in as_completed(futures):
            part = future.result()
            totals["parts"].append(part)
            for key in ("records_seen", "target_records_seen", "references_written"):
                totals[key] = int(totals[key]) + int(part[key])
            for subject, count in part["subject_counts"].items():
                subject_counts = totals["subject_counts"]
                subject_counts[subject] = subject_counts.get(subject, 0) + count
            log(
                f"finished_part={part['part_id']} files={part['files_processed']} "
                f"seen={part['records_seen']:,} targets={part['target_records_seen']:,} "
                f"references={part['references_written']:,}"
            )

    summary_path = args.subject_root / "backfill_work_references_summary.json"
    summary_path.write_text(json.dumps(totals, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(totals, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
