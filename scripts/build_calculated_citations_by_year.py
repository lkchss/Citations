#!/usr/bin/env python3
"""Calculate annual citations for a subject from OpenAlex referenced_works."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import multiprocessing as mp
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT_WORKS_DIR = Path("/root/sdb1/openalex/snapshot/data/works")
DEFAULT_SUBJECT_DIR = Path("/root/sdb1/openalex/subjects/economics_econometrics_and_finance")
DEFAULT_OUTPUT_DIR = Path(
    "/root/sdb1/openalex/subjects/economics_econometrics_and_finance/calculated_citations"
)
DEFAULT_WORK_IDS_CACHE = DEFAULT_OUTPUT_DIR / "target_work_ids.txt.gz"
TARGET_WORK_IDS: set[str] = set()


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def chunked(items: list[Path], chunks: int) -> list[list[Path]]:
    return [items[index::chunks] for index in range(chunks)]


def load_subject_work_ids(subject_dir: Path) -> set[str]:
    work_ids: set[str] = set()
    for path in sorted((subject_dir / "tables_parts").glob("part_*_works.csv.gz")):
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                work_id = row.get("work_id")
                if work_id:
                    work_ids.add(work_id)
    return work_ids


def load_work_ids_cache(path: Path) -> set[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    work_ids: set[str] = set()
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            work_id = line.strip()
            if work_id:
                work_ids.add(work_id)
    return work_ids


def write_work_ids_cache(path: Path, work_ids: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(tmp_path, "wt", encoding="utf-8") as handle:
        for work_id in sorted(work_ids):
            handle.write(f"{work_id}\n")
    tmp_path.replace(path)


def get_target_work_ids(subject_dir: Path, cache_path: Path | None) -> set[str]:
    if cache_path and cache_path.exists():
        return load_work_ids_cache(cache_path)
    work_ids = load_subject_work_ids(subject_dir)
    if cache_path:
        write_work_ids_cache(cache_path, work_ids)
    return work_ids


def init_target_work_ids(work_ids: set[str]) -> None:
    global TARGET_WORK_IDS
    TARGET_WORK_IDS = work_ids


def write_counter(path: Path, counts: Counter[tuple[str, int]]) -> int:
    rows = 0
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["work_id", "year", "calculated_citations"],
        )
        writer.writeheader()
        for (work_id, year), citations in sorted(counts.items()):
            writer.writerow(
                {
                    "work_id": work_id,
                    "year": year,
                    "calculated_citations": citations,
                }
            )
            rows += 1
    return rows


def process_files(
    *,
    files: list[Path],
    output_dir: Path,
    part_id: int,
) -> dict[str, Any]:
    counts: Counter[tuple[str, int]] = Counter()
    records_seen = 0
    records_with_year = 0
    records_with_references = 0
    references_seen = 0
    matched_references = 0
    citing_works_with_matches = 0

    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                records_seen += 1
                work = json.loads(line)
                citation_year = int_or_zero(work.get("publication_year"))
                if not citation_year:
                    continue
                records_with_year += 1
                references = work.get("referenced_works") or []
                if not references:
                    continue
                records_with_references += 1
                references_seen += len(references)
                matched_this_work = 0
                for referenced_work_id in references:
                    if referenced_work_id in TARGET_WORK_IDS:
                        counts[(str(referenced_work_id), citation_year)] += 1
                        matched_references += 1
                        matched_this_work += 1
                if matched_this_work:
                    citing_works_with_matches += 1

    output_dir.mkdir(parents=True, exist_ok=True)
    part_output = output_dir / f"part_{part_id:04d}_calculated_citations_by_year.csv.gz"
    annual_rows = write_counter(part_output, counts)
    return {
        "part_id": part_id,
        "files_processed": len(files),
        "part_output": str(part_output),
        "records_seen": records_seen,
        "records_with_year": records_with_year,
        "records_with_references": records_with_references,
        "references_seen": references_seen,
        "matched_references": matched_references,
        "citing_works_with_matches": citing_works_with_matches,
        "annual_rows": annual_rows,
    }


def merge_parts(output_dir: Path, output: Path) -> dict[str, int]:
    counts: Counter[tuple[str, int]] = Counter()
    part_rows = 0
    for path in sorted(output_dir.glob("part_*_calculated_citations_by_year.csv.gz")):
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                counts[(row["work_id"], int_or_zero(row["year"]))] += int_or_zero(
                    row["calculated_citations"]
                )
                part_rows += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_name(f"{output.name}.tmp")
    annual_rows = write_counter(tmp_output, counts)
    tmp_output.replace(output)
    return {
        "part_rows": part_rows,
        "annual_rows": annual_rows,
        "total_calculated_citations": sum(counts.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate subject annual citations from OpenAlex referenced_works."
    )
    parser.add_argument("--snapshot-works-dir", type=Path, default=DEFAULT_SNAPSHOT_WORKS_DIR)
    parser.add_argument("--subject-dir", type=Path, default=DEFAULT_SUBJECT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "calculated_citations_by_year.csv.gz",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--skip-parts", action="store_true")
    parser.add_argument(
        "--work-ids-cache",
        type=Path,
        default=DEFAULT_WORK_IDS_CACHE,
        help="Cache file for subject work IDs. Use an existing cache when available.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = sorted(args.snapshot_works_dir.rglob("*.gz"))
    if args.max_files:
        files = files[: args.max_files]
    if not files:
        raise SystemExit(f"No snapshot files found in {args.snapshot_works_dir}")

    target_work_ids: set[str] = set()
    if not args.skip_parts:
        target_work_ids = get_target_work_ids(args.subject_dir, args.work_ids_cache)
        if not target_work_ids:
            raise SystemExit(f"No subject work IDs found in {args.subject_dir / 'tables_parts'}")

    workers = max(1, min(args.workers, len(files)))
    chunks = chunked(files, workers)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    totals: dict[str, Any] = {
        "snapshot_works_dir": str(args.snapshot_works_dir),
        "subject_dir": str(args.subject_dir),
        "output_dir": str(args.output_dir),
        "output": str(args.output),
        "input_files": len(files),
        "workers": workers,
        "target_works": len(target_work_ids),
        "work_ids_cache": str(args.work_ids_cache) if args.work_ids_cache else "",
        "records_seen": 0,
        "records_with_year": 0,
        "records_with_references": 0,
        "references_seen": 0,
        "matched_references": 0,
        "citing_works_with_matches": 0,
        "annual_rows_by_part": 0,
        "parts": [],
    }

    if not args.skip_parts and workers == 1:
        init_target_work_ids(target_work_ids)
        for index, chunk in enumerate(chunks):
            if not chunk:
                continue
            part = process_files(
                files=chunk,
                output_dir=args.output_dir,
                part_id=index,
            )
            totals["parts"].append(part)
            for key in (
                "records_seen",
                "records_with_year",
                "records_with_references",
                "references_seen",
                "matched_references",
                "citing_works_with_matches",
            ):
                totals[key] += part[key]
            totals["annual_rows_by_part"] += part["annual_rows"]
            print(
                "finished_part="
                f"{part['part_id']} files={part['files_processed']} "
                f"matched_refs={part['matched_references']} rows={part['annual_rows']}",
                flush=True,
            )
    elif not args.skip_parts:
        context = mp.get_context("fork")
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=context,
            initializer=init_target_work_ids,
            initargs=(target_work_ids,),
        ) as executor:
            futures = [
                executor.submit(
                    process_files,
                    files=chunk,
                    output_dir=args.output_dir,
                    part_id=index,
                )
                for index, chunk in enumerate(chunks)
                if chunk
            ]
            for future in as_completed(futures):
                part = future.result()
                totals["parts"].append(part)
                for key in (
                    "records_seen",
                    "records_with_year",
                    "records_with_references",
                    "references_seen",
                    "matched_references",
                    "citing_works_with_matches",
                ):
                    totals[key] += part[key]
                totals["annual_rows_by_part"] += part["annual_rows"]
                print(
                    "finished_part="
                    f"{part['part_id']} files={part['files_processed']} "
                    f"matched_refs={part['matched_references']} rows={part['annual_rows']}",
                    flush=True,
                )

    merge_summary = merge_parts(args.output_dir, args.output)
    totals.update(merge_summary)
    totals["match_rate_per_reference"] = (
        totals["matched_references"] / totals["references_seen"]
        if totals["references_seen"]
        else 0
    )
    summary_path = args.output.with_name(f"{args.output.name}.summary.json")
    summary_path.write_text(json.dumps(totals, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(totals, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
