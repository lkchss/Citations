#!/usr/bin/env python3
"""List candidate author hit papers from pulled OpenAlex works."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from build_author_paper_year_panel import (
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TYPES,
    collect_author_stats,
    collect_hits,
    count_unrelated_focal_works,
    filter_hits_by_unrelated_focal_works,
    get_authors,
    get_primary_topic,
    int_or_zero,
    iter_work_files,
    iter_works,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a CSV of candidate hit papers ranked by author citation share."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", default="hit_candidates.csv")
    parser.add_argument("--max-files", type=int, default=0, help="0 means use all batch files.")
    parser.add_argument("--min-hit-citations", type=int, default=101)
    parser.add_argument("--min-hit-author-citation-share", type=float, default=0.5)
    parser.add_argument("--min-author-included-works", type=int, default=3)
    parser.add_argument("--min-focal-age-at-hit", type=int, default=1)
    parser.add_argument(
        "--min-unrelated-focal-works",
        type=int,
        default=3,
        help="Minimum prior unrelated focal works required for each author-hit event.",
    )
    parser.add_argument("--min-hit-year", type=int, default=1990)
    parser.add_argument("--max-hit-year", type=int, default=0)
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
    author_total_citations, author_included_works = collect_author_stats(paths, allowed_types)
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
    kept_hit_keys = {
        (author_id, hit.work_id): hit
        for author_id, hits in hits_by_author.items()
        for hit in hits
    }
    rows: list[dict[str, object]] = []

    for work in iter_works(paths):
        work_id = str(work.get("id") or "")
        work_type = str(work.get("type") or "")
        publication_year = int_or_zero(work.get("publication_year"))
        cited_by_count = int_or_zero(work.get("cited_by_count"))
        if not work_id or not publication_year:
            continue
        if allowed_types and work_type not in allowed_types:
            continue
        if cited_by_count < args.min_hit_citations:
            continue
        if args.min_hit_year and publication_year < args.min_hit_year:
            continue
        if args.max_hit_year and publication_year > args.max_hit_year:
            continue

        field, subfield, topic_id, topic = get_primary_topic(work)
        for author_id, author_name, position in get_authors(work):
            hit = kept_hit_keys.get((author_id, work_id))
            if not hit:
                continue
            rows.append(
                {
                    "author_name": author_name,
                    "author_position": position,
                    "title": work.get("display_name") or work.get("title") or "",
                    "year": publication_year,
                    "type": work_type,
                    "citations": cited_by_count,
                    "author_total_citations": hit.author_total_citations,
                    "author_included_works": hit.author_included_works,
                    "unrelated_focal_works": hit.unrelated_focal_works,
                    "share": f"{hit.author_hit_citation_share:.8f}",
                    "fwci": work.get("fwci"),
                    "field": field,
                    "subfield": subfield,
                    "primary_topic_id": topic_id,
                    "primary_topic": topic,
                    "work_id": work_id,
                    "author_id": author_id,
                }
            )

    rows.sort(
        key=lambda row: (float(row["share"]), int(row["citations"])),
        reverse=True,
    )
    output_path = args.output_dir / args.output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "author_name",
        "author_position",
        "title",
        "year",
        "type",
        "citations",
        "author_total_citations",
        "author_included_works",
        "unrelated_focal_works",
        "share",
        "fwci",
        "field",
        "subfield",
        "primary_topic_id",
        "primary_topic",
        "work_id",
        "author_id",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"input_files={len(paths)}")
    print(f"candidate_author_paper_pairs={len(rows)}")
    print(f"unique_hit_papers={len({row['work_id'] for row in rows})}")
    print(f"unique_authors={len({row['author_id'] for row in rows})}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
