#!/usr/bin/env python3
"""Build paper-author-year panels from subject table part files."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from itertools import groupby
from pathlib import Path


DEFAULT_INPUT_ROOT = Path("/root/sdb1/openalex/subjects")


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


def part_id(path: Path, suffix: str) -> str:
    name = path.name
    return name.removeprefix("part_").removesuffix(suffix)


def build_subject_panel(
    *,
    subject_dir: Path,
    output: Path,
    start_year: int,
    end_year: int,
    zero_missing_citations: bool,
) -> dict[str, object]:
    table_parts = subject_dir / "tables_parts"
    works_parts = sorted(table_parts.glob("part_*_works.csv.gz"))
    if not works_parts:
        raise SystemExit(f"No works parts found in {table_parts}")

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_name(f"{output.name}.tmp")
    fieldnames = [
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
    rows = 0
    works = 0
    paper_author_pairs = 0
    with gzip.open(tmp_output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for works_part in works_parts:
            pid = part_id(works_part, "_works.csv.gz")
            authors_part = table_parts / f"part_{pid}_work_authors.csv.gz"
            citations_part = table_parts / f"part_{pid}_work_citations_by_year.csv.gz"
            author_groups = grouped_by_work(authors_part) if authors_part.exists() else iter(())
            citation_groups = grouped_by_work(citations_part) if citations_part.exists() else iter(())
            current_authors = None
            current_citations = None
            for work in read_csv_gz(works_part):
                works += 1
                work_id = work["work_id"]
                current_authors, authorships = advance_to_work(
                    author_groups, current_authors, work_id
                )
                current_citations, citation_rows = advance_to_work(
                    citation_groups, current_citations, work_id
                )
                citations = {
                    int_or_zero(row["year"]): int_or_zero(row["citations"]) for row in citation_rows
                }
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
                                "work_id": work_id,
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

    summary = {
        "subject_dir": str(subject_dir),
        "output": str(output),
        "parts": len(works_parts),
        "works": works,
        "paper_author_pairs": paper_author_pairs,
        "panel_rows": rows,
        "start_year": start_year or "publication_year",
        "end_year": end_year,
        "zero_missing_citations": zero_missing_citations,
    }
    tmp_output.replace(output)
    output.with_name(f"{output.name}.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build panels from subject table parts.")
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--start-year", type=int, default=0)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--zero-missing-citations", action="store_true")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip subjects whose final panel and summary JSON already exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    subjects = args.subject or [
        path.name for path in sorted(args.input_root.iterdir()) if (path / "tables_parts").exists()
    ]
    summaries = []
    for subject in subjects:
        subject_dir = args.input_root / subject
        output = subject_dir / "panels" / "paper_author_year.csv.gz"
        summary_path = output.with_name(f"{output.name}.summary.json")
        if args.skip_existing and output.exists() and summary_path.exists():
            print(f"skipping existing subject={subject} output={output}", flush=True)
            continue
        summary = build_subject_panel(
            subject_dir=subject_dir,
            output=output,
            start_year=args.start_year,
            end_year=args.end_year,
            zero_missing_citations=args.zero_missing_citations,
        )
        summaries.append(summary)
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
