#!/usr/bin/env python3
"""Build a subject-level paper-author-year panel from normalized OpenAlex tables."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_TABLE_DIR = Path("/root/sdb1/openalex/derived/economics/tables")
DEFAULT_OUTPUT = Path("/root/sdb1/openalex/derived/economics/panels/paper_author_year.csv.gz")


def read_csv_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def int_or_zero(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def load_works(table_dir: Path) -> dict[str, dict[str, str]]:
    return {row["work_id"]: row for row in read_csv_gz(table_dir / "works.csv.gz")}


def load_work_authors(table_dir: Path) -> list[dict[str, str]]:
    return list(read_csv_gz(table_dir / "work_authors.csv.gz"))


def load_citations(table_dir: Path) -> dict[str, dict[int, int]]:
    citations: dict[str, dict[int, int]] = defaultdict(dict)
    for row in read_csv_gz(table_dir / "work_citations_by_year.csv.gz"):
        citations[row["work_id"]][int_or_zero(row["year"])] = int_or_zero(row["citations"])
    return citations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a balanced paper-author-year panel for a subject corpus."
    )
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-year", type=int, default=0)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument(
        "--zero-missing-citations",
        action="store_true",
        help=(
            "Fill missing work-year citation counts with zero. By default they are blank with "
            "citations_observed=0 because OpenAlex counts_by_year coverage can be incomplete."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    works = load_works(args.table_dir)
    work_authors = load_work_authors(args.table_dir)
    citations = load_citations(args.table_dir)

    args.output.parent.mkdir(parents=True, exist_ok=True)
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
    paper_author_pairs = 0
    with gzip.open(args.output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for authorship in work_authors:
            work_id = authorship["work_id"]
            work = works.get(work_id)
            if not work:
                continue
            publication_year = int_or_zero(work["publication_year"])
            if not publication_year:
                continue
            start_year = max(args.start_year or publication_year, publication_year)
            end_year = max(args.end_year, start_year)
            paper_author_pairs += 1
            for year in range(start_year, end_year + 1):
                if year in citations.get(work_id, {}):
                    citation_value: str | int = citations[work_id][year]
                    observed = 1
                elif args.zero_missing_citations:
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
        "table_dir": str(args.table_dir),
        "output": str(args.output),
        "works": len(works),
        "paper_author_pairs": paper_author_pairs,
        "panel_rows": rows,
        "start_year": args.start_year or "publication_year",
        "end_year": args.end_year,
        "zero_missing_citations": args.zero_missing_citations,
    }
    args.output.with_name(f"{args.output.name}.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
