#!/usr/bin/env python3
"""Build a sharded paper-author-year panel from normalized subject tables."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from itertools import groupby
from pathlib import Path
from typing import Any


DEFAULT_TABLE_DIR = Path("/root/sdb1/openalex/derived/economics/tables")
DEFAULT_OUTPUT_DIR = Path("/root/sdb1/openalex/derived/economics/panels/paper_author_year_parts")

FIELDNAMES = [
    "work_id",
    "author_id",
    "author_name",
    "author_position",
    "author_sequence",
    "year",
    "publication_year",
    "paper_age",
    "type",
    "title",
    "field_id",
    "field_name",
    "subfield_id",
    "subfield_name",
    "topic_id",
    "topic_name",
    "work_cited_by_count_total",
    "fwci",
    "citations",
    "citations_observed",
]


def read_csv_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def int_or_zero(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def grouped_by_work(path: Path):
    for work_id, rows in groupby(read_csv_gz(path), key=lambda row: row["work_id"]):
        yield work_id, list(rows)


def advance_to_work(groups, current, work_id: str):
    if current is None:
        try:
            current = next(groups)
        except StopIteration:
            return None, []
    current_work_id, rows = current
    if current_work_id == work_id:
        try:
            next_current = next(groups)
        except StopIteration:
            next_current = None
        return next_current, rows
    return current, []


def write_part(
    *,
    output_dir: Path,
    part_id: int,
    records: list[tuple[dict[str, str], list[dict[str, str]], dict[int, int]]],
    start_year: int,
    end_year: int,
    zero_missing_citations: bool,
) -> dict[str, Any]:
    output = output_dir / f"part_{part_id:05d}.csv.gz"
    rows = 0
    works = 0
    paper_author_pairs = 0
    with gzip.open(output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for work, authorships, citations in records:
            works += 1
            publication_year = int_or_zero(work["publication_year"])
            if not publication_year:
                continue
            first_year = max(start_year or publication_year, publication_year)
            last_year = max(end_year, first_year)
            for authorship in authorships:
                paper_author_pairs += 1
                for year in range(first_year, last_year + 1):
                    if year in citations:
                        citation_value: str | int = citations[year]
                        observed = 1
                    elif zero_missing_citations:
                        citation_value = 0
                        observed = 1
                    else:
                        citation_value = ""
                        observed = 0
                    writer.writerow(
                        {
                            "work_id": work["work_id"],
                            "author_id": authorship["author_id"],
                            "author_name": authorship["author_name"],
                            "author_position": authorship["author_position"],
                            "author_sequence": authorship["author_sequence"],
                            "year": year,
                            "publication_year": publication_year,
                            "paper_age": year - publication_year,
                            "type": work["type"],
                            "title": work["title"],
                            "field_id": work["field_id"],
                            "field_name": work["field_name"],
                            "subfield_id": work["subfield_id"],
                            "subfield_name": work["subfield_name"],
                            "topic_id": work["topic_id"],
                            "topic_name": work["topic_name"],
                            "work_cited_by_count_total": work["cited_by_count"],
                            "fwci": work["fwci"],
                            "citations": citation_value,
                            "citations_observed": observed,
                        }
                    )
                    rows += 1
    return {
        "part_id": part_id,
        "output": str(output),
        "works": works,
        "paper_author_pairs": paper_author_pairs,
        "panel_rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build sharded paper-author-year panel.")
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-year", type=int, default=0)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--zero-missing-citations", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--works-per-part", type=int, default=50_000)
    parser.add_argument("--max-in-flight", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    author_groups = grouped_by_work(args.table_dir / "work_authors.csv.gz")
    citation_groups = grouped_by_work(args.table_dir / "work_citations_by_year.csv.gz")
    current_authors = None
    current_citations = None
    part_id = 0
    pending = set()
    summaries = []

    totals: dict[str, Any] = {
        "table_dir": str(args.table_dir),
        "output_dir": str(args.output_dir),
        "workers": args.workers,
        "works_per_part": args.works_per_part,
        "start_year": args.start_year or "publication_year",
        "end_year": args.end_year,
        "zero_missing_citations": args.zero_missing_citations,
        "works": 0,
        "paper_author_pairs": 0,
        "panel_rows": 0,
        "parts": [],
    }

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        batch = []
        for work in read_csv_gz(args.table_dir / "works.csv.gz"):
            work_id = work["work_id"]
            current_authors, authorships = advance_to_work(author_groups, current_authors, work_id)
            current_citations, citation_rows = advance_to_work(
                citation_groups, current_citations, work_id
            )
            citations = {
                int_or_zero(row["year"]): int_or_zero(row["citations"]) for row in citation_rows
            }
            batch.append((work, authorships, citations))
            if len(batch) >= args.works_per_part:
                pending.add(
                    executor.submit(
                        write_part,
                        output_dir=args.output_dir,
                        part_id=part_id,
                        records=batch,
                        start_year=args.start_year,
                        end_year=args.end_year,
                        zero_missing_citations=args.zero_missing_citations,
                    )
                )
                part_id += 1
                batch = []
            if len(pending) >= args.max_in_flight:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    summary = future.result()
                    summaries.append(summary)
                    print(json.dumps(summary, sort_keys=True), flush=True)
        if batch:
            pending.add(
                executor.submit(
                    write_part,
                    output_dir=args.output_dir,
                    part_id=part_id,
                    records=batch,
                    start_year=args.start_year,
                    end_year=args.end_year,
                    zero_missing_citations=args.zero_missing_citations,
                )
            )
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                summary = future.result()
                summaries.append(summary)
                print(json.dumps(summary, sort_keys=True), flush=True)

    for summary in sorted(summaries, key=lambda item: item["part_id"]):
        totals["parts"].append(summary)
        totals["works"] += summary["works"]
        totals["paper_author_pairs"] += summary["paper_author_pairs"]
        totals["panel_rows"] += summary["panel_rows"]

    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(totals, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(totals, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
