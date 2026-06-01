#!/usr/bin/env python3
"""Build normalized research tables from OpenAlex work JSONL gzip files."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_INPUT_DIR = Path("/root/sdb1/openalex/derived/economics/works")
DEFAULT_OUTPUT_DIR = Path("/root/sdb1/openalex/derived/economics/tables")
DEFAULT_TYPES = ("article", "preprint", "review")


@dataclass(frozen=True)
class WorkLite:
    work_id: str
    title: str
    publication_year: int
    work_type: str
    cited_by_count: int
    fwci: str
    field_id: str
    field_name: str
    subfield_id: str
    subfield_name: str
    topic_id: str
    topic_name: str
    referenced_works: frozenset[str]


def iter_work_files(input_dir: Path, max_files: int) -> list[Path]:
    files = sorted(input_dir.rglob("works_*.jsonl.gz"))
    if max_files:
        return files[:max_files]
    return files


def iter_works(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def get_topic_parts(work: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    topic = work.get("primary_topic") or {}
    field = topic.get("field") or {}
    subfield = topic.get("subfield") or {}
    return (
        str(field.get("id") or ""),
        str(field.get("display_name") or ""),
        str(subfield.get("id") or ""),
        str(subfield.get("display_name") or ""),
        str(topic.get("id") or ""),
        str(topic.get("display_name") or ""),
    )


def get_authors(work: dict[str, Any]) -> list[tuple[str, str, str, int]]:
    authors = []
    for index, authorship in enumerate(work.get("authorships") or [], start=1):
        author = authorship.get("author") or {}
        author_id = author.get("id")
        if not author_id:
            continue
        authors.append(
            (
                str(author_id),
                str(author.get("display_name") or ""),
                str(authorship.get("author_position") or ""),
                index,
            )
        )
    return authors


def counts_by_year(work: dict[str, Any]) -> list[tuple[int, int]]:
    counts = []
    for item in work.get("counts_by_year") or []:
        year = item.get("year")
        if year is None:
            continue
        counts.append((int(year), int_or_zero(item.get("cited_by_count"))))
    return counts


def csv_writer(path: Path, fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = gzip.open(path, "wt", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    return handle, writer


def parse_work(work: dict[str, Any]) -> WorkLite | None:
    work_id = str(work.get("id") or "")
    publication_year = int_or_zero(work.get("publication_year"))
    if not work_id or not publication_year:
        return None
    field_id, field_name, subfield_id, subfield_name, topic_id, topic_name = get_topic_parts(work)
    return WorkLite(
        work_id=work_id,
        title=str(work.get("display_name") or work.get("title") or ""),
        publication_year=publication_year,
        work_type=str(work.get("type") or ""),
        cited_by_count=int_or_zero(work.get("cited_by_count")),
        fwci="" if work.get("fwci") is None else str(work.get("fwci")),
        field_id=field_id,
        field_name=field_name,
        subfield_id=subfield_id,
        subfield_name=subfield_name,
        topic_id=topic_id,
        topic_name=topic_name,
        referenced_works=frozenset(str(ref) for ref in (work.get("referenced_works") or [])),
    )


def build_tables(args: argparse.Namespace) -> dict[str, int]:
    files = iter_work_files(args.input_dir, args.max_files)
    if not files:
        raise SystemExit(f"No works_*.jsonl.gz files found in {args.input_dir}")

    allowed_types = {item.strip() for item in args.types.split(",") if item.strip()}
    author_total_citations: dict[str, int] = defaultdict(int)
    author_work_count: dict[str, int] = defaultdict(int)
    author_names: dict[str, str] = {}
    work_by_id: dict[str, WorkLite] = {}
    work_authors: dict[str, list[tuple[str, str, str, int]]] = {}
    works_by_author: dict[str, set[str]] = defaultdict(set)

    works_handle, works_writer = csv_writer(
        args.output_dir / "works.csv.gz",
        [
            "work_id",
            "title",
            "publication_year",
            "type",
            "cited_by_count",
            "fwci",
            "field_id",
            "field_name",
            "subfield_id",
            "subfield_name",
            "topic_id",
            "topic_name",
            "referenced_works_count",
        ],
    )
    authors_handle, authors_writer = csv_writer(
        args.output_dir / "work_authors.csv.gz",
        ["work_id", "author_id", "author_name", "author_position", "author_sequence"],
    )
    citations_handle, citations_writer = csv_writer(
        args.output_dir / "work_citations_by_year.csv.gz",
        ["work_id", "year", "citations"],
    )
    references_handle = references_writer = None
    if args.include_references:
        references_handle, references_writer = csv_writer(
            args.output_dir / "work_references.csv.gz",
            ["work_id", "referenced_work_id"],
        )

    records_seen = 0
    works_written = 0
    authors_written = 0
    citations_written = 0
    references_written = 0

    try:
        for work in iter_works(files):
            records_seen += 1
            parsed = parse_work(work)
            if parsed is None:
                continue
            if allowed_types and parsed.work_type not in allowed_types:
                continue

            authors = get_authors(work)
            if not args.skip_hit_events:
                work_by_id[parsed.work_id] = parsed
                work_authors[parsed.work_id] = authors
            works_writer.writerow(
                {
                    "work_id": parsed.work_id,
                    "title": parsed.title,
                    "publication_year": parsed.publication_year,
                    "type": parsed.work_type,
                    "cited_by_count": parsed.cited_by_count,
                    "fwci": parsed.fwci,
                    "field_id": parsed.field_id,
                    "field_name": parsed.field_name,
                    "subfield_id": parsed.subfield_id,
                    "subfield_name": parsed.subfield_name,
                    "topic_id": parsed.topic_id,
                    "topic_name": parsed.topic_name,
                    "referenced_works_count": len(parsed.referenced_works),
                }
            )
            works_written += 1

            for author_id, author_name, position, sequence in authors:
                authors_writer.writerow(
                    {
                        "work_id": parsed.work_id,
                        "author_id": author_id,
                        "author_name": author_name,
                        "author_position": position,
                        "author_sequence": sequence,
                    }
                )
                authors_written += 1
                if not args.skip_author_stats or not args.skip_hit_events:
                    author_names.setdefault(author_id, author_name)
                    author_total_citations[author_id] += parsed.cited_by_count
                    author_work_count[author_id] += 1
                if not args.skip_hit_events:
                    works_by_author[author_id].add(parsed.work_id)

            for year, citations in counts_by_year(work):
                citations_writer.writerow(
                    {
                        "work_id": parsed.work_id,
                        "year": year,
                        "citations": citations,
                    }
                )
                citations_written += 1

            if references_writer is not None:
                for referenced_work_id in parsed.referenced_works:
                    references_writer.writerow(
                        {
                            "work_id": parsed.work_id,
                            "referenced_work_id": referenced_work_id,
                        }
                    )
                    references_written += 1
    finally:
        works_handle.close()
        authors_handle.close()
        citations_handle.close()
        if references_handle is not None:
            references_handle.close()

    authors_stats_written = 0
    if not args.skip_author_stats:
        author_stats_handle, author_stats_writer = csv_writer(
            args.output_dir / "author_work_stats.csv.gz",
            ["author_id", "author_name", "included_works", "total_citations"],
        )
        try:
            for author_id in sorted(author_work_count):
                author_stats_writer.writerow(
                    {
                        "author_id": author_id,
                        "author_name": author_names.get(author_id, ""),
                        "included_works": author_work_count[author_id],
                        "total_citations": author_total_citations[author_id],
                    }
                )
                authors_stats_written += 1
        finally:
            author_stats_handle.close()

    hit_events = 0
    if not args.skip_hit_events:
        hit_events = build_hit_events(
            args=args,
            work_by_id=work_by_id,
            work_authors=work_authors,
            works_by_author=works_by_author,
            author_total_citations=author_total_citations,
            author_work_count=author_work_count,
            author_names=author_names,
        )

    summary = {
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "input_files": len(files),
        "records_seen": records_seen,
        "works_written": works_written,
        "work_authors_written": authors_written,
        "work_citations_by_year_written": citations_written,
        "work_references_written": references_written,
        "authors_written": authors_stats_written,
        "hit_events_written": hit_events,
        "include_references": args.include_references,
        "skip_author_stats": args.skip_author_stats,
        "skip_hit_events": args.skip_hit_events,
        "types": sorted(allowed_types),
    }
    (args.output_dir / "build_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def build_hit_events(
    args: argparse.Namespace,
    work_by_id: dict[str, WorkLite],
    work_authors: dict[str, list[tuple[str, str, str, int]]],
    works_by_author: dict[str, set[str]],
    author_total_citations: dict[str, int],
    author_work_count: dict[str, int],
    author_names: dict[str, str],
) -> int:
    handle, writer = csv_writer(
        args.output_dir / "hit_events.csv.gz",
        [
            "author_id",
            "author_name",
            "hit_work_id",
            "hit_title",
            "hit_publication_year",
            "hit_type",
            "hit_cited_by_count",
            "hit_fwci",
            "author_total_citations",
            "author_included_works",
            "hit_author_citation_share",
            "unrelated_focal_works",
        ],
    )
    count = 0
    try:
        for work in work_by_id.values():
            if work.cited_by_count < args.min_hit_citations:
                continue
            if args.min_hit_year and work.publication_year < args.min_hit_year:
                continue
            if args.max_hit_year and work.publication_year > args.max_hit_year:
                continue
            for author_id, author_name, _position, _sequence in work_authors.get(work.work_id, []):
                total_citations = author_total_citations.get(author_id, 0)
                included_works = author_work_count.get(author_id, 0)
                if included_works < args.min_author_included_works:
                    continue
                share = work.cited_by_count / total_citations if total_citations else 0.0
                if share < args.min_hit_author_citation_share:
                    continue
                unrelated = 0
                for focal_work_id in works_by_author.get(author_id, set()):
                    if focal_work_id == work.work_id:
                        continue
                    focal = work_by_id.get(focal_work_id)
                    if not focal:
                        continue
                    if focal.publication_year > work.publication_year - args.min_focal_age_at_hit:
                        continue
                    if focal.work_id in work.referenced_works:
                        continue
                    unrelated += 1
                if unrelated < args.min_unrelated_focal_works:
                    continue
                writer.writerow(
                    {
                        "author_id": author_id,
                        "author_name": author_name or author_names.get(author_id, ""),
                        "hit_work_id": work.work_id,
                        "hit_title": work.title,
                        "hit_publication_year": work.publication_year,
                        "hit_type": work.work_type,
                        "hit_cited_by_count": work.cited_by_count,
                        "hit_fwci": work.fwci,
                        "author_total_citations": total_citations,
                        "author_included_works": included_works,
                        "hit_author_citation_share": f"{share:.8f}",
                        "unrelated_focal_works": unrelated,
                    }
                )
                count += 1
    finally:
        handle.close()
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build normalized research tables from OpenAlex works.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--types", default=",".join(DEFAULT_TYPES))
    parser.add_argument("--include-references", action="store_true")
    parser.add_argument("--skip-author-stats", action="store_true")
    parser.add_argument("--skip-hit-events", action="store_true")
    parser.add_argument("--min-hit-citations", type=int, default=101)
    parser.add_argument("--min-hit-author-citation-share", type=float, default=0.5)
    parser.add_argument("--min-author-included-works", type=int, default=3)
    parser.add_argument("--min-unrelated-focal-works", type=int, default=3)
    parser.add_argument("--min-focal-age-at-hit", type=int, default=1)
    parser.add_argument("--min-hit-year", type=int, default=1990)
    parser.add_argument("--max-hit-year", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_tables(args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
