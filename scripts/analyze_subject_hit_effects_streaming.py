#!/usr/bin/env python3
"""Memory-bounded subject hit-effect analysis from subject table parts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from analyze_economics_hit_effects import (
    Authorship,
    HitCandidate,
    Work,
    float_or_blank,
    int_or_zero,
    load_hit_references,
    read_csv_gz,
    write_event_panel_and_summaries,
    write_event_summary,
    write_hit_events,
    write_report,
)


DEFAULT_WORKS_JSONL_DIR = Path("/root/sdb1/openalex/snapshot/data/works")


def table_parts(subject_dir: Path, table_name: str) -> list[Path]:
    parts = sorted((subject_dir / "tables_parts").glob(f"part_*_{table_name}.csv.gz"))
    if not parts:
        raise FileNotFoundError(f"No {table_name} parts under {subject_dir / 'tables_parts'}")
    return parts


def part_id(path: Path, suffix: str) -> str:
    return path.name.removeprefix("part_").removesuffix(suffix)


def load_works_part(path: Path) -> dict[str, Work]:
    works = {}
    for row in read_csv_gz(path):
        works[row["work_id"]] = Work(
            work_id=row["work_id"],
            title=row["title"],
            publication_year=int_or_zero(row["publication_year"]),
            work_type=row["type"],
            cited_by_count=int_or_zero(row["cited_by_count"]),
            fwci=float_or_blank(row.get("fwci")),
        )
    return works


def authors_part_for(subject_dir: Path, works_part: Path) -> Path:
    pid = part_id(works_part, "_works.csv.gz")
    return subject_dir / "tables_parts" / f"part_{pid}_work_authors.csv.gz"


def citations_part_for(subject_dir: Path, works_part: Path) -> Path:
    pid = part_id(works_part, "_works.csv.gz")
    return subject_dir / "tables_parts" / f"part_{pid}_work_citations_by_year.csv.gz"


def compute_author_stats(
    subject_dir: Path, works_parts: list[Path]
) -> tuple[int, dict[str, int], dict[str, int], dict[str, str]]:
    works_seen = 0
    author_total_citations: dict[str, int] = defaultdict(int)
    author_work_count: dict[str, int] = defaultdict(int)
    author_names: dict[str, str] = {}
    for works_part in works_parts:
        works = load_works_part(works_part)
        works_seen += len(works)
        authors_part = authors_part_for(subject_dir, works_part)
        if not authors_part.exists():
            continue
        for row in read_csv_gz(authors_part):
            work = works.get(row["work_id"])
            if not work:
                continue
            author_id = row["author_id"]
            author_total_citations[author_id] += work.cited_by_count
            author_work_count[author_id] += 1
            if row["author_name"]:
                author_names.setdefault(author_id, row["author_name"])
    return works_seen, author_total_citations, author_work_count, author_names


def find_hit_candidates(
    *,
    subject_dir: Path,
    works_parts: list[Path],
    author_total_citations: dict[str, int],
    author_work_count: dict[str, int],
    author_names: dict[str, str],
    min_hit_citations: int,
    min_hit_author_citation_share: float,
    min_author_included_works: int,
    min_hit_year: int,
    max_hit_year: int,
) -> list[HitCandidate]:
    candidates = []
    for works_part in works_parts:
        works = load_works_part(works_part)
        authors_part = authors_part_for(subject_dir, works_part)
        if not authors_part.exists():
            continue
        for row in read_csv_gz(authors_part):
            work = works.get(row["work_id"])
            if not work:
                continue
            if work.cited_by_count < min_hit_citations:
                continue
            if work.publication_year < min_hit_year:
                continue
            if max_hit_year and work.publication_year > max_hit_year:
                continue
            author_id = row["author_id"]
            included_works = author_work_count.get(author_id, 0)
            if included_works < min_author_included_works:
                continue
            total_citations = author_total_citations.get(author_id, 0)
            share = work.cited_by_count / total_citations if total_citations else 0.0
            if share < min_hit_author_citation_share:
                continue
            candidates.append(
                HitCandidate(
                    author_id=author_id,
                    author_name=row["author_name"] or author_names.get(author_id, ""),
                    hit_work_id=work.work_id,
                    hit_publication_year=work.publication_year,
                    hit_cited_by_count=work.cited_by_count,
                    author_total_citations=total_citations,
                    author_included_works=included_works,
                    hit_author_citation_share=share,
                )
            )
    return candidates


def collect_candidate_author_works(
    subject_dir: Path,
    works_parts: list[Path],
    candidate_authors: set[str],
) -> tuple[dict[str, Work], dict[str, list[Authorship]]]:
    relevant_works: dict[str, Work] = {}
    works_by_author: dict[str, list[Authorship]] = defaultdict(list)
    for works_part in works_parts:
        works = load_works_part(works_part)
        authors_part = authors_part_for(subject_dir, works_part)
        if not authors_part.exists():
            continue
        for row in read_csv_gz(authors_part):
            author_id = row["author_id"]
            if author_id not in candidate_authors:
                continue
            work = works.get(row["work_id"])
            if not work:
                continue
            relevant_works[work.work_id] = work
            works_by_author[author_id].append(
                Authorship(
                    work_id=row["work_id"],
                    author_id=author_id,
                    author_name=row["author_name"],
                    author_position=row["author_position"],
                    author_sequence=row["author_sequence"],
                )
            )
    return relevant_works, works_by_author


def load_citations_for_focals(
    subject_dir: Path, works_parts: list[Path], focal_work_ids: set[str]
) -> dict[str, dict[int, int]]:
    citations: dict[str, dict[int, int]] = defaultdict(dict)
    for works_part in works_parts:
        citations_part = citations_part_for(subject_dir, works_part)
        if not citations_part.exists():
            continue
        for row in read_csv_gz(citations_part):
            work_id = row["work_id"]
            if work_id in focal_work_ids:
                citations[work_id][int_or_zero(row["year"])] = int_or_zero(row["citations"])
    return citations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze subject citation spillovers from hit papers.")
    parser.add_argument("--subject-dir", type=Path, required=True)
    parser.add_argument("--works-jsonl-dir", type=Path, default=DEFAULT_WORKS_JSONL_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-hit-citations", type=int, default=101)
    parser.add_argument("--min-hit-author-citation-share", type=float, default=0.5)
    parser.add_argument("--min-author-included-works", type=int, default=4)
    parser.add_argument("--min-unrelated-focal-works", type=int, default=3)
    parser.add_argument("--min-focal-age-at-hit", type=int, default=1)
    parser.add_argument("--min-hit-year", type=int, default=1990)
    parser.add_argument("--max-hit-year", type=int, default=0)
    parser.add_argument("--pre-years", type=int, default=10)
    parser.add_argument("--post-years", type=int, default=10)
    parser.add_argument("--reference-workers", type=int, default=12)
    parser.add_argument("--zero-missing-citations", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    works_parts = table_parts(args.subject_dir, "works")

    print("computing author stats", flush=True)
    works_count, author_total_citations, author_work_count, author_names = compute_author_stats(
        args.subject_dir, works_parts
    )
    print(f"works={works_count}", flush=True)
    print(f"authors={len(author_work_count)}", flush=True)

    print("finding hit candidates", flush=True)
    hit_candidates = find_hit_candidates(
        subject_dir=args.subject_dir,
        works_parts=works_parts,
        author_total_citations=author_total_citations,
        author_work_count=author_work_count,
        author_names=author_names,
        min_hit_citations=args.min_hit_citations,
        min_hit_author_citation_share=args.min_hit_author_citation_share,
        min_author_included_works=args.min_author_included_works,
        min_hit_year=args.min_hit_year,
        max_hit_year=args.max_hit_year,
    )
    candidate_authors = {item.author_id for item in hit_candidates}
    hit_work_ids = {item.hit_work_id for item in hit_candidates}
    print(f"hit_candidates={len(hit_candidates)} candidate_authors={len(candidate_authors)}", flush=True)

    print("collecting candidate author works", flush=True)
    works, works_by_author = collect_candidate_author_works(
        args.subject_dir, works_parts, candidate_authors
    )

    print("loading hit references from JSONL", flush=True)
    hit_references = load_hit_references(
        args.works_jsonl_dir, hit_work_ids, args.reference_workers
    )

    hit_rows = []
    hit_focal_rows = []
    focal_work_ids = set()
    for hit in hit_candidates:
        hit_work = works.get(hit.hit_work_id)
        if not hit_work:
            continue
        hit_refs = hit_references.get(hit.hit_work_id, set())
        focal_authorships = []
        for authorship in works_by_author.get(hit.author_id, []):
            if authorship.work_id == hit.hit_work_id:
                continue
            focal = works.get(authorship.work_id)
            if not focal:
                continue
            if focal.publication_year > hit.hit_publication_year - args.min_focal_age_at_hit:
                continue
            if focal.work_id in hit_refs:
                continue
            focal_authorships.append(authorship)
        if len(focal_authorships) < args.min_unrelated_focal_works:
            continue
        hit_rows.append(
            {
                "author_id": hit.author_id,
                "author_name": hit.author_name,
                "hit_work_id": hit.hit_work_id,
                "hit_title": hit_work.title,
                "hit_publication_year": hit.hit_publication_year,
                "hit_type": hit_work.work_type,
                "hit_cited_by_count": hit.hit_cited_by_count,
                "hit_fwci": hit_work.fwci,
                "author_total_citations": hit.author_total_citations,
                "author_included_works": hit.author_included_works,
                "hit_author_citation_share": f"{hit.hit_author_citation_share:.8f}",
                "unrelated_focal_works": len(focal_authorships),
            }
        )
        for focal_authorship in focal_authorships:
            focal_work_ids.add(focal_authorship.work_id)
            hit_focal_rows.append(
                {
                    "author_id": hit.author_id,
                    "author_name": focal_authorship.author_name or hit.author_name,
                    "author_position_on_focal": focal_authorship.author_position,
                    "focal_work_id": focal_authorship.work_id,
                    "hit_work_id": hit.hit_work_id,
                    "hit_publication_year": hit.hit_publication_year,
                    "author_total_citations": hit.author_total_citations,
                    "author_included_works": hit.author_included_works,
                    "hit_author_citation_share": hit.hit_author_citation_share,
                    "hit_unrelated_focal_works": len(focal_authorships),
                }
            )
    print(f"hit_events={len(hit_rows)} focal_pairs={len(hit_focal_rows)}", flush=True)

    print("loading focal citations", flush=True)
    citations = load_citations_for_focals(args.subject_dir, works_parts, focal_work_ids)

    hit_events_output = args.output_dir / "hit_events.csv.gz"
    event_panel_output = args.output_dir / "paper_author_hit_year_panel.csv.gz"
    event_summary_output = args.output_dir / "event_time_summary.csv"
    report_output = args.output_dir / "economics_hit_effects_report.md"

    write_hit_events(output=hit_events_output, hit_rows=hit_rows)
    simple_estimates, event_summary_rows = write_event_panel_and_summaries(
        output=event_panel_output,
        hit_focal_rows=hit_focal_rows,
        works=works,
        citations=citations,
        pre_years=args.pre_years,
        post_years=args.post_years,
        zero_missing_citations=args.zero_missing_citations,
    )
    write_event_summary(event_summary_output, event_summary_rows)

    summary = {
        "criteria": {
            "min_hit_citations": args.min_hit_citations,
            "min_hit_author_citation_share": args.min_hit_author_citation_share,
            "min_author_included_works": args.min_author_included_works,
            "min_unrelated_focal_works": args.min_unrelated_focal_works,
            "min_focal_age_at_hit": args.min_focal_age_at_hit,
            "min_hit_year": args.min_hit_year,
            "max_hit_year": args.max_hit_year,
            "pre_years": args.pre_years,
            "post_years": args.post_years,
            "reference_workers": args.reference_workers,
            "zero_missing_citations": args.zero_missing_citations,
            "citation_source": "openalex_counts_by_year",
            "calculated_citations": "",
        },
        "works": works_count,
        "authors": len(author_work_count),
        "hit_candidates": len(hit_candidates),
        "candidate_authors": len(candidate_authors),
        "hit_events": len(hit_rows),
        "focal_work_ids": len(focal_work_ids),
        "outputs": {
            "hit_events": str(hit_events_output),
            "event_panel": str(event_panel_output),
            "event_time_summary": str(event_summary_output),
            "report": str(report_output),
        },
        "simple_estimates": simple_estimates,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_report(report_output, summary, event_summary_rows)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
