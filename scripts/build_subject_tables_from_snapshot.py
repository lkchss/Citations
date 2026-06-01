#!/usr/bin/env python3
"""Build subject-partitioned paper/author/citation tables from an OpenAlex snapshot."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT_WORKS_DIR = Path("/root/sdb1/openalex/snapshot/data/works")
DEFAULT_OUTPUT_ROOT = Path("/root/sdb1/openalex/subjects")
DEFAULT_TYPES = ("article", "preprint", "review")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug or "unknown"


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def get_topic_parts(work: dict[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    topic = work.get("primary_topic") or {}
    field = topic.get("field") or {}
    subfield = topic.get("subfield") or {}
    field_name = str(field.get("display_name") or "Unknown")
    return (
        slugify(field_name),
        str(field.get("id") or ""),
        field_name,
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


class SubjectWriters:
    def __init__(self, output_root: Path, part_id: int):
        self.output_root = output_root
        self.part_id = part_id
        self.handles: dict[tuple[str, str], Any] = {}
        self.writers: dict[tuple[str, str], csv.DictWriter] = {}

    def writer(self, subject_slug: str, table: str, fieldnames: list[str]) -> csv.DictWriter:
        key = (subject_slug, table)
        if key not in self.writers:
            path = self.output_root / subject_slug / "tables_parts" / f"part_{self.part_id:04d}_{table}.csv.gz"
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = gzip.open(path, "wt", encoding="utf-8", newline="")
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            self.handles[key] = handle
            self.writers[key] = writer
        return self.writers[key]

    def close(self) -> None:
        for handle in self.handles.values():
            handle.close()


def chunked(items: list[Path], chunks: int) -> list[list[Path]]:
    return [items[index::chunks] for index in range(chunks)]


def process_files(
    *,
    files: list[Path],
    output_root: Path,
    part_id: int,
    allowed_types: set[str],
) -> dict[str, Any]:
    writers = SubjectWriters(output_root, part_id)
    subject_counts: dict[str, int] = {}
    seen = 0
    written = 0
    authors_written = 0
    citations_written = 0
    try:
        for path in files:
            with gzip.open(path, "rt", encoding="utf-8") as input_handle:
                for line in input_handle:
                    if not line.strip():
                        continue
                    seen += 1
                    work = json.loads(line)
                    work_type = str(work.get("type") or "")
                    if allowed_types and work_type not in allowed_types:
                        continue
                    work_id = str(work.get("id") or "")
                    publication_year = int_or_zero(work.get("publication_year"))
                    if not work_id or not publication_year:
                        continue
                    (
                        subject_slug,
                        field_id,
                        field_name,
                        subfield_id,
                        subfield_name,
                        topic_id,
                        topic_name,
                    ) = get_topic_parts(work)

                    works_writer = writers.writer(
                        subject_slug,
                        "works",
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
                    works_writer.writerow(
                        {
                            "work_id": work_id,
                            "title": str(work.get("display_name") or work.get("title") or ""),
                            "publication_year": publication_year,
                            "type": work_type,
                            "cited_by_count": int_or_zero(work.get("cited_by_count")),
                            "fwci": "" if work.get("fwci") is None else str(work.get("fwci")),
                            "field_id": field_id,
                            "field_name": field_name,
                            "subfield_id": subfield_id,
                            "subfield_name": subfield_name,
                            "topic_id": topic_id,
                            "topic_name": topic_name,
                            "referenced_works_count": len(work.get("referenced_works") or []),
                        }
                    )
                    written += 1
                    subject_counts[subject_slug] = subject_counts.get(subject_slug, 0) + 1

                    authors_writer = writers.writer(
                        subject_slug,
                        "work_authors",
                        ["work_id", "author_id", "author_name", "author_position", "author_sequence"],
                    )
                    for author_id, author_name, position, sequence in get_authors(work):
                        authors_writer.writerow(
                            {
                                "work_id": work_id,
                                "author_id": author_id,
                                "author_name": author_name,
                                "author_position": position,
                                "author_sequence": sequence,
                            }
                        )
                        authors_written += 1

                    citations_writer = writers.writer(
                        subject_slug,
                        "work_citations_by_year",
                        ["work_id", "year", "citations"],
                    )
                    for year, citations in counts_by_year(work):
                        citations_writer.writerow(
                            {"work_id": work_id, "year": year, "citations": citations}
                        )
                        citations_written += 1
    finally:
        writers.close()

    return {
        "part_id": part_id,
        "files_processed": len(files),
        "records_seen": seen,
        "works_written": written,
        "work_authors_written": authors_written,
        "work_citations_by_year_written": citations_written,
        "subject_counts": subject_counts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build subject-partitioned OpenAlex tables.")
    parser.add_argument("--snapshot-works-dir", type=Path, default=DEFAULT_SNAPSHOT_WORKS_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--types", default=",".join(DEFAULT_TYPES))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = sorted(args.snapshot_works_dir.rglob("*.gz"))
    if args.max_files:
        files = files[: args.max_files]
    if not files:
        raise SystemExit(f"No snapshot files found in {args.snapshot_works_dir}")

    workers = max(1, min(args.workers, len(files)))
    chunks = chunked(files, workers)
    allowed_types = {item.strip() for item in args.types.split(",") if item.strip()}
    args.output_root.mkdir(parents=True, exist_ok=True)

    totals: dict[str, Any] = {
        "snapshot_works_dir": str(args.snapshot_works_dir),
        "output_root": str(args.output_root),
        "input_files": len(files),
        "workers": workers,
        "types": sorted(allowed_types),
        "records_seen": 0,
        "works_written": 0,
        "work_authors_written": 0,
        "work_citations_by_year_written": 0,
        "subject_counts": {},
        "parts": [],
    }

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                process_files,
                files=chunk,
                output_root=args.output_root,
                part_id=index,
                allowed_types=allowed_types,
            )
            for index, chunk in enumerate(chunks)
            if chunk
        ]
        for future in as_completed(futures):
            part = future.result()
            totals["parts"].append(part)
            for key in (
                "records_seen",
                "works_written",
                "work_authors_written",
                "work_citations_by_year_written",
            ):
                totals[key] += part[key]
            for subject, count in part["subject_counts"].items():
                totals["subject_counts"][subject] = totals["subject_counts"].get(subject, 0) + count
            print(
                "finished_part="
                f"{part['part_id']} files={part['files_processed']} seen={part['records_seen']} "
                f"works={part['works_written']}",
                flush=True,
            )

    (args.output_root / "build_subject_tables_summary.json").write_text(
        json.dumps(totals, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(totals, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
