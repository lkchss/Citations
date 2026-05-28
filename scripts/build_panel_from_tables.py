#!/usr/bin/env python3
"""Build paper-author-hit-year panel from normalized research tables."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_TABLE_DIR = Path("/root/sdb1/openalex/derived/economics/tables")
DEFAULT_OUTPUT = Path("/root/sdb1/openalex/derived/panels/paper_author_hit_year_panel.csv.gz")


def read_csv_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def int_or_zero(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def load_tables(table_dir: Path):
    works = {row["work_id"]: row for row in read_csv_gz(table_dir / "works.csv.gz")}
    authors_by_work: dict[str, list[dict[str, str]]] = defaultdict(list)
    works_by_author: dict[str, set[str]] = defaultdict(set)
    for row in read_csv_gz(table_dir / "work_authors.csv.gz"):
        authors_by_work[row["work_id"]].append(row)
        works_by_author[row["author_id"]].add(row["work_id"])
    citations: dict[str, dict[int, int]] = defaultdict(dict)
    for row in read_csv_gz(table_dir / "work_citations_by_year.csv.gz"):
        citations[row["work_id"]][int_or_zero(row["year"])] = int_or_zero(row["citations"])
    hits_by_author: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv_gz(table_dir / "hit_events.csv.gz"):
        hits_by_author[row["author_id"]].append(row)
    return works, authors_by_work, works_by_author, citations, hits_by_author


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build event panel from normalized research tables.")
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pre-years", type=int, default=5)
    parser.add_argument("--post-years", type=int, default=5)
    parser.add_argument("--min-focal-age-at-hit", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    works, authors_by_work, works_by_author, citations, hits_by_author = load_tables(args.table_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "author_id",
        "author_name",
        "author_position_on_focal",
        "focal_work_id",
        "focal_title",
        "focal_publication_year",
        "focal_type",
        "focal_cited_by_count_total",
        "focal_fwci",
        "hit_work_id",
        "hit_title",
        "hit_publication_year",
        "hit_type",
        "hit_cited_by_count_total",
        "hit_author_total_citations",
        "hit_author_included_works",
        "hit_author_citation_share",
        "hit_unrelated_focal_works",
        "year",
        "event_time",
        "post_hit",
        "years_since_focal_publication",
        "citations",
        "citations_observed",
    ]
    rows = 0
    pairs = 0
    with gzip.open(args.output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for author_id, hit_rows in hits_by_author.items():
            for focal_work_id in works_by_author.get(author_id, set()):
                focal = works.get(focal_work_id)
                if not focal:
                    continue
                focal_year = int_or_zero(focal["publication_year"])
                focal_authorship = next(
                    (row for row in authors_by_work[focal_work_id] if row["author_id"] == author_id),
                    {},
                )
                for hit in hit_rows:
                    hit_work_id = hit["hit_work_id"]
                    hit_year = int_or_zero(hit["hit_publication_year"])
                    if focal_work_id == hit_work_id:
                        continue
                    if focal_year > hit_year - args.min_focal_age_at_hit:
                        continue
                    pairs += 1
                    for event_time in range(-args.pre_years, args.post_years + 1):
                        year = hit_year + event_time
                        if year < focal_year:
                            citation_value: str | int = 0
                            observed = 1
                        elif year in citations.get(focal_work_id, {}):
                            citation_value = citations[focal_work_id][year]
                            observed = 1
                        else:
                            citation_value = ""
                            observed = 0
                        writer.writerow(
                            {
                                "author_id": author_id,
                                "author_name": focal_authorship.get("author_name") or hit["author_name"],
                                "author_position_on_focal": focal_authorship.get("author_position", ""),
                                "focal_work_id": focal_work_id,
                                "focal_title": focal["title"],
                                "focal_publication_year": focal_year,
                                "focal_type": focal["type"],
                                "focal_cited_by_count_total": focal["cited_by_count"],
                                "focal_fwci": focal["fwci"],
                                "hit_work_id": hit_work_id,
                                "hit_title": hit["hit_title"],
                                "hit_publication_year": hit_year,
                                "hit_type": hit["hit_type"],
                                "hit_cited_by_count_total": hit["hit_cited_by_count"],
                                "hit_author_total_citations": hit["author_total_citations"],
                                "hit_author_included_works": hit["author_included_works"],
                                "hit_author_citation_share": hit["hit_author_citation_share"],
                                "hit_unrelated_focal_works": hit["unrelated_focal_works"],
                                "year": year,
                                "event_time": event_time,
                                "post_hit": int(event_time >= 0),
                                "years_since_focal_publication": year - focal_year,
                                "citations": citation_value,
                                "citations_observed": observed,
                            }
                        )
                        rows += 1

    summary = {
        "table_dir": str(args.table_dir),
        "output": str(args.output),
        "focal_author_hit_pairs": pairs,
        "panel_rows": rows,
    }
    args.output.with_name(f"{args.output.name}.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
