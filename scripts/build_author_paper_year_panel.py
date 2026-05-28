#!/usr/bin/env python3
"""Build a first-pass paper-author-year event panel from OpenAlex works."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_INPUT_DIR = Path("/root/sdb1/openalex/economics_field20")
DEFAULT_OUTPUT_DIR = Path("/root/sdb1/openalex/econometrics_panels")
DEFAULT_TYPES = ("article", "preprint", "review")


@dataclass(frozen=True)
class Hit:
    author_id: str
    author_name: str
    work_id: str
    title: str
    publication_year: int
    work_type: str
    cited_by_count: int
    author_total_citations: int
    author_included_works: int
    author_hit_citation_share: float
    unrelated_focal_works: int
    fwci: float | None
    referenced_works: frozenset[str]


def iter_work_files(input_dir: Path, max_files: int) -> list[Path]:
    paths = sorted(input_dir.glob("works_*.jsonl.gz"))
    if max_files:
        return paths[:max_files]
    return paths


def iter_works(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def get_primary_topic(work: dict[str, Any]) -> tuple[str, str, str, str]:
    topic = work.get("primary_topic") or {}
    subfield = topic.get("subfield") or {}
    field = topic.get("field") or {}
    return (
        str(field.get("display_name") or ""),
        str(subfield.get("display_name") or ""),
        str(topic.get("id") or ""),
        str(topic.get("display_name") or ""),
    )


def get_authors(work: dict[str, Any]) -> list[tuple[str, str, str]]:
    authors: list[tuple[str, str, str]] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        author_id = author.get("id")
        if not author_id:
            continue
        authors.append(
            (
                str(author_id),
                str(author.get("display_name") or ""),
                str(authorship.get("author_position") or ""),
            )
        )
    return authors


def counts_by_year(work: dict[str, Any]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for item in work.get("counts_by_year") or []:
        year = item.get("year")
        if year is None:
            continue
        counts[int(year)] = int(item.get("cited_by_count") or 0)
    return counts


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_author_stats(
    paths: list[Path],
    allowed_types: set[str],
) -> tuple[dict[str, int], dict[str, int]]:
    citation_totals: dict[str, int] = defaultdict(int)
    work_counts: dict[str, int] = defaultdict(int)
    for work in iter_works(paths):
        work_type = str(work.get("type") or "")
        if allowed_types and work_type not in allowed_types:
            continue
        cited_by_count = int_or_zero(work.get("cited_by_count"))
        for author_id, _author_name, _position in get_authors(work):
            citation_totals[author_id] += cited_by_count
            work_counts[author_id] += 1
    return citation_totals, work_counts


def collect_hits(
    paths: list[Path],
    allowed_types: set[str],
    author_total_citations: dict[str, int],
    author_included_works: dict[str, int],
    min_hit_citations: int,
    min_hit_author_citation_share: float,
    min_author_included_works: int,
    min_hit_year: int,
    max_hit_year: int,
) -> dict[str, list[Hit]]:
    hits_by_author: dict[str, list[Hit]] = defaultdict(list)
    for work in iter_works(paths):
        work_id = str(work.get("id") or "")
        publication_year = int_or_zero(work.get("publication_year"))
        cited_by_count = int_or_zero(work.get("cited_by_count"))
        work_type = str(work.get("type") or "")
        if not work_id or not publication_year:
            continue
        if allowed_types and work_type not in allowed_types:
            continue
        if cited_by_count < min_hit_citations:
            continue
        if min_hit_year and publication_year < min_hit_year:
            continue
        if max_hit_year and publication_year > max_hit_year:
            continue

        references = frozenset(str(ref) for ref in (work.get("referenced_works") or []))
        for author_id, author_name, _position in get_authors(work):
            author_total = author_total_citations.get(author_id, 0)
            author_work_count = author_included_works.get(author_id, 0)
            if author_work_count < min_author_included_works:
                continue
            hit_share = cited_by_count / author_total if author_total else 0.0
            if hit_share < min_hit_author_citation_share:
                continue
            hits_by_author[author_id].append(
                Hit(
                    author_id=author_id,
                    author_name=author_name,
                    work_id=work_id,
                    title=str(work.get("display_name") or work.get("title") or ""),
                    publication_year=publication_year,
                    work_type=work_type,
                    cited_by_count=cited_by_count,
                    author_total_citations=author_total,
                    author_included_works=author_work_count,
                    author_hit_citation_share=hit_share,
                    unrelated_focal_works=0,
                    fwci=float_or_none(work.get("fwci")),
                    referenced_works=references,
                )
            )
    return hits_by_author


def count_unrelated_focal_works(
    paths: list[Path],
    hits_by_author: dict[str, list[Hit]],
    allowed_types: set[str],
    min_focal_age_at_hit: int,
) -> dict[tuple[str, str], int]:
    focal_works_by_hit: dict[tuple[str, str], set[str]] = defaultdict(set)
    for work in iter_works(paths):
        work_id = str(work.get("id") or "")
        publication_year = int_or_zero(work.get("publication_year"))
        work_type = str(work.get("type") or "")
        if not work_id or not publication_year:
            continue
        if allowed_types and work_type not in allowed_types:
            continue

        for author_id, _author_name, _position in get_authors(work):
            for hit in hits_by_author.get(author_id, []):
                if hit.work_id == work_id:
                    continue
                if publication_year > hit.publication_year - min_focal_age_at_hit:
                    continue
                if work_id in hit.referenced_works:
                    continue
                focal_works_by_hit[(author_id, hit.work_id)].add(work_id)

    return {key: len(work_ids) for key, work_ids in focal_works_by_hit.items()}


def filter_hits_by_unrelated_focal_works(
    hits_by_author: dict[str, list[Hit]],
    unrelated_focal_counts: dict[tuple[str, str], int],
    min_unrelated_focal_works: int,
) -> dict[str, list[Hit]]:
    filtered: dict[str, list[Hit]] = defaultdict(list)
    for author_id, hits in hits_by_author.items():
        for hit in hits:
            unrelated_count = unrelated_focal_counts.get((author_id, hit.work_id), 0)
            if unrelated_count < min_unrelated_focal_works:
                continue
            filtered[author_id].append(
                Hit(
                    author_id=hit.author_id,
                    author_name=hit.author_name,
                    work_id=hit.work_id,
                    title=hit.title,
                    publication_year=hit.publication_year,
                    work_type=hit.work_type,
                    cited_by_count=hit.cited_by_count,
                    author_total_citations=hit.author_total_citations,
                    author_included_works=hit.author_included_works,
                    author_hit_citation_share=hit.author_hit_citation_share,
                    unrelated_focal_works=unrelated_count,
                    fwci=hit.fwci,
                    referenced_works=hit.referenced_works,
                )
            )
    return filtered


def write_panel(
    paths: list[Path],
    output_path: Path,
    hits_by_author: dict[str, list[Hit]],
    allowed_types: set[str],
    pre_years: int,
    post_years: int,
    min_focal_age_at_hit: int,
) -> tuple[int, int, int]:
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
        "focal_field",
        "focal_subfield",
        "focal_primary_topic_id",
        "focal_primary_topic",
        "hit_work_id",
        "hit_title",
        "hit_publication_year",
        "hit_type",
        "hit_cited_by_count_total",
        "hit_author_total_citations",
        "hit_author_included_works",
        "hit_author_citation_share",
        "hit_unrelated_focal_works",
        "hit_fwci",
        "year",
        "event_time",
        "post_hit",
        "years_since_focal_publication",
        "citations",
        "citations_observed",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    focal_work_count = 0
    focal_author_hit_pairs = 0

    with gzip.open(output_path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for work in iter_works(paths):
            work_id = str(work.get("id") or "")
            publication_year = int_or_zero(work.get("publication_year"))
            work_type = str(work.get("type") or "")
            if not work_id or not publication_year:
                continue
            if allowed_types and work_type not in allowed_types:
                continue

            authors = get_authors(work)
            if not authors:
                continue

            annual_counts = counts_by_year(work)
            field, subfield, topic_id, topic = get_primary_topic(work)
            used_focal_work = False

            for author_id, author_name, position in authors:
                for hit in hits_by_author.get(author_id, []):
                    if hit.work_id == work_id:
                        continue
                    if publication_year > hit.publication_year - min_focal_age_at_hit:
                        continue
                    if work_id in hit.referenced_works:
                        continue

                    focal_author_hit_pairs += 1
                    used_focal_work = True
                    for event_time in range(-pre_years, post_years + 1):
                        year = hit.publication_year + event_time
                        if year < publication_year:
                            citations = 0
                            citations_observed = 1
                        elif year in annual_counts:
                            citations = annual_counts[year]
                            citations_observed = 1
                        else:
                            citations = ""
                            citations_observed = 0
                        writer.writerow(
                            {
                                "author_id": author_id,
                                "author_name": author_name or hit.author_name,
                                "author_position_on_focal": position,
                                "focal_work_id": work_id,
                                "focal_title": work.get("display_name") or work.get("title") or "",
                                "focal_publication_year": publication_year,
                                "focal_type": work_type,
                                "focal_cited_by_count_total": int_or_zero(work.get("cited_by_count")),
                                "focal_fwci": work.get("fwci"),
                                "focal_field": field,
                                "focal_subfield": subfield,
                                "focal_primary_topic_id": topic_id,
                                "focal_primary_topic": topic,
                                "hit_work_id": hit.work_id,
                                "hit_title": hit.title,
                                "hit_publication_year": hit.publication_year,
                                "hit_type": hit.work_type,
                                "hit_cited_by_count_total": hit.cited_by_count,
                                "hit_author_total_citations": hit.author_total_citations,
                                "hit_author_included_works": hit.author_included_works,
                                "hit_author_citation_share": f"{hit.author_hit_citation_share:.8f}",
                                "hit_unrelated_focal_works": hit.unrelated_focal_works,
                                "hit_fwci": hit.fwci,
                                "year": year,
                                "event_time": event_time,
                                "post_hit": int(event_time >= 0),
                                "years_since_focal_publication": year - publication_year,
                                "citations": citations,
                                "citations_observed": citations_observed,
                            }
                        )
                        row_count += 1

            if used_focal_work:
                focal_work_count += 1

    return row_count, focal_work_count, focal_author_hit_pairs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Construct a balanced paper-author-year panel around author hit papers. "
            "A focal paper is unrelated when the hit paper does not cite it."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", default="author_paper_year_event_panel.csv.gz")
    parser.add_argument("--max-files", type=int, default=0, help="0 means use all batch files.")
    parser.add_argument("--min-hit-citations", type=int, default=101)
    parser.add_argument(
        "--min-hit-author-citation-share",
        type=float,
        default=0.0,
        help=(
            "Minimum share of an author's included-work citations accounted for by the hit. "
            "For example, 0.5 keeps hits that account for at least half of author citations."
        ),
    )
    parser.add_argument(
        "--min-author-included-works",
        type=int,
        default=1,
        help="Minimum number of included works an author must have in the processed corpus.",
    )
    parser.add_argument("--min-hit-year", type=int, default=1990)
    parser.add_argument("--max-hit-year", type=int, default=0)
    parser.add_argument("--pre-years", type=int, default=5)
    parser.add_argument("--post-years", type=int, default=5)
    parser.add_argument("--min-focal-age-at-hit", type=int, default=1)
    parser.add_argument(
        "--min-unrelated-focal-works",
        type=int,
        default=0,
        help="Minimum prior unrelated focal works required for each author-hit event.",
    )
    parser.add_argument(
        "--types",
        default=",".join(DEFAULT_TYPES),
        help="Comma-separated OpenAlex work types to include. Empty means all types.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = iter_work_files(args.input_dir, args.max_files)
    if not paths:
        raise SystemExit(f"No works_*.jsonl.gz files found in {args.input_dir}")

    allowed_types = {item.strip() for item in args.types.split(",") if item.strip()}
    author_total_citations, author_included_works = collect_author_stats(
        paths=paths,
        allowed_types=allowed_types,
    )
    hits_by_author = collect_hits(
        paths=paths,
        allowed_types=allowed_types,
        author_total_citations=author_total_citations,
        author_included_works=author_included_works,
        min_hit_citations=args.min_hit_citations,
        min_hit_author_citation_share=args.min_hit_author_citation_share,
        min_author_included_works=args.min_author_included_works,
        min_hit_year=args.min_hit_year,
        max_hit_year=args.max_hit_year,
    )
    unrelated_focal_counts = count_unrelated_focal_works(
        paths=paths,
        hits_by_author=hits_by_author,
        allowed_types=allowed_types,
        min_focal_age_at_hit=args.min_focal_age_at_hit,
    )
    hits_by_author = filter_hits_by_unrelated_focal_works(
        hits_by_author=hits_by_author,
        unrelated_focal_counts=unrelated_focal_counts,
        min_unrelated_focal_works=args.min_unrelated_focal_works,
    )
    hit_count = sum(len(hits) for hits in hits_by_author.values())
    output_path = args.output_dir / args.output_name
    rows, focal_works, focal_pairs = write_panel(
        paths=paths,
        output_path=output_path,
        hits_by_author=hits_by_author,
        allowed_types=allowed_types,
        pre_years=args.pre_years,
        post_years=args.post_years,
        min_focal_age_at_hit=args.min_focal_age_at_hit,
    )

    summary_path = output_path.with_name(f"{output_path.name}.summary.json")
    summary = {
        "input_dir": str(args.input_dir),
        "input_files": len(paths),
        "output_path": str(output_path),
        "allowed_types": sorted(allowed_types),
        "min_hit_citations": args.min_hit_citations,
        "min_hit_author_citation_share": args.min_hit_author_citation_share,
        "min_author_included_works": args.min_author_included_works,
        "min_hit_year": args.min_hit_year or None,
        "max_hit_year": args.max_hit_year or None,
        "pre_years": args.pre_years,
        "post_years": args.post_years,
        "min_focal_age_at_hit": args.min_focal_age_at_hit,
        "min_unrelated_focal_works": args.min_unrelated_focal_works,
        "hit_authors": len(hits_by_author),
        "author_hit_events": hit_count,
        "focal_works": focal_works,
        "focal_author_hit_pairs": focal_pairs,
        "panel_rows": rows,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
