#!/usr/bin/env python3
"""Build author-paper-year rows for subject prevalence regressions.

For each author-paper-year observation, the script computes lagged cumulative
citations to the author's other subject papers, split into related and unrelated
pools for the focal paper. Papers i and j are related when i=j, i cites j, or
j cites i.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import multiprocessing as mp
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable


DEFAULT_SUBJECT_ROOT = Path("/root/sdb1/openalex/subjects")
DEFAULT_SNAPSHOT_WORKS_DIR = Path("/root/sdb1/openalex/snapshot/data/works")
DEFAULT_OUTPUT_ROOT = Path("/root/sdb1/openalex/subjects/prevalence_regressions")
DEFAULT_SUBJECTS = [
    "economics_econometrics_and_finance",
    "agricultural_and_biological_sciences",
    "biochemistry_genetics_and_molecular_biology",
    "physics_and_astronomy",
]
REFERENCE_TARGET_WORKS: set[str] = set()


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def read_csv_gz(path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def stable_bucket(value: str, modulo: int) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).hexdigest()
    return int(digest, 16) % modulo


def chunked(items: list[Path], chunks: int) -> list[list[Path]]:
    return [items[index::chunks] for index in range(chunks)]


def load_sampled_author_works(
    table_parts: Path,
    *,
    sample_mod: int,
    sample_keep: int,
    max_authors: int,
    min_author_papers: int,
) -> dict[str, set[str]]:
    author_works: dict[str, set[str]] = defaultdict(set)
    closed_authors: set[str] = set()
    for path in sorted(table_parts.glob("part_*_work_authors.csv.gz")):
        for row in read_csv_gz(path):
            author_id = row.get("author_id") or ""
            work_id = row.get("work_id") or ""
            if not author_id or not work_id or author_id in closed_authors:
                continue
            if stable_bucket(author_id, sample_mod) >= sample_keep:
                continue
            author_works[author_id].add(work_id)
            if max_authors and len(author_works) >= max_authors:
                closed_authors.update(
                    author
                    for author, works in author_works.items()
                    if len(works) >= min_author_papers
                )
                if len(closed_authors) >= max_authors:
                    return {
                        author: works
                        for author, works in author_works.items()
                        if len(works) >= min_author_papers
                    }
    return {
        author: works
        for author, works in author_works.items()
        if len(works) >= min_author_papers
    }


def load_work_metadata(table_parts: Path, target_works: set[str]) -> dict[str, dict[str, object]]:
    metadata: dict[str, dict[str, object]] = {}
    for path in sorted(table_parts.glob("part_*_works.csv.gz")):
        for row in read_csv_gz(path):
            work_id = row.get("work_id") or ""
            if work_id not in target_works:
                continue
            publication_year = int_or_zero(row.get("publication_year"))
            if not publication_year:
                continue
            metadata[work_id] = {
                "publication_year": publication_year,
                "cited_by_count": int_or_zero(row.get("cited_by_count")),
                "type": row.get("type", ""),
            }
    return metadata


def load_citations(table_parts: Path, target_works: set[str]) -> dict[str, dict[int, int]]:
    citations: dict[str, dict[int, int]] = {work_id: {} for work_id in target_works}
    for path in sorted(table_parts.glob("part_*_work_citations_by_year.csv.gz")):
        for row in read_csv_gz(path):
            work_id = row.get("work_id") or ""
            if work_id not in target_works:
                continue
            year = int_or_zero(row.get("year"))
            if year:
                citations.setdefault(work_id, {})[year] = int_or_zero(row.get("citations"))
    return citations


def load_calculated_citations(path: Path, target_works: set[str]) -> dict[str, dict[int, int]]:
    citations: dict[str, dict[int, int]] = {work_id: {} for work_id in target_works}
    if not path.exists():
        return citations
    for row in read_csv_gz(path):
        work_id = row.get("work_id") or ""
        if work_id not in target_works:
            continue
        year = int_or_zero(row.get("year"))
        value = int_or_zero(row.get("calculated_citations") or row.get("citations"))
        if year:
            citations.setdefault(work_id, {})[year] = value
    return citations


def init_reference_targets(target_works: set[str]) -> None:
    global REFERENCE_TARGET_WORKS
    REFERENCE_TARGET_WORKS = target_works


def process_reference_files(files: list[Path]) -> tuple[set[tuple[str, str]], int, int]:
    edges: set[tuple[str, str]] = set()
    records = 0
    records_with_target_source = 0
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                records += 1
                work = json.loads(line)
                source = str(work.get("id") or "")
                if source not in REFERENCE_TARGET_WORKS:
                    continue
                records_with_target_source += 1
                for target in work.get("referenced_works") or []:
                    target = str(target)
                    if target in REFERENCE_TARGET_WORKS:
                        edges.add((source, target))
    return edges, records, records_with_target_source


def extract_reference_edges(
    *,
    snapshot_works_dir: Path,
    target_works: set[str],
    max_snapshot_files: int,
    reference_workers: int,
) -> set[tuple[str, str]]:
    files = sorted(snapshot_works_dir.rglob("*.gz"))
    if max_snapshot_files:
        files = files[:max_snapshot_files]
    if not files:
        return set()
    workers = max(1, min(reference_workers, len(files)))
    if workers == 1:
        init_reference_targets(target_works)
        edges, records, target_sources = process_reference_files(files)
        log(
            "reference scan complete: "
            f"{records:,} records, {target_sources:,} target-source records"
        )
        return edges

    edges: set[tuple[str, str]] = set()
    completed = 0
    total_records = 0
    total_target_sources = 0
    batches = chunked(files, workers)
    context = mp.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=init_reference_targets,
        initargs=(target_works,),
    ) as executor:
        futures = [executor.submit(process_reference_files, batch) for batch in batches]
        for future in as_completed(futures):
            part_edges, records, target_sources = future.result()
            edges.update(part_edges)
            total_records += records
            total_target_sources += target_sources
            completed += 1
            log(
                "reference scan batch complete "
                f"{completed}/{len(futures)}; records={total_records:,}; "
                f"target-source records={total_target_sources:,}; edges={len(edges):,}"
            )
    return edges


def cumulative_by_year(citations: dict[int, int], *, start_year: int, end_year: int) -> dict[int, int]:
    running = 0
    cumulative: dict[int, int] = {}
    for year in range(start_year, end_year + 1):
        cumulative[year] = running
        running += citations.get(year, 0)
    return cumulative


def build_subject(
    *,
    subject: str,
    subject_root: Path,
    snapshot_works_dir: Path,
    output_root: Path,
    start_year: int,
    end_year: int,
    sample_mod: int,
    sample_keep: int,
    max_authors: int,
    min_author_papers: int,
    max_snapshot_files: int,
    reference_workers: int,
    calculated_citations: Path | None,
) -> dict[str, object]:
    subject_dir = subject_root / subject
    table_parts = subject_dir / "tables_parts"
    output_dir = output_root / subject
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "paper_author_year_prevalence_regression.csv.gz"

    log(f"[{subject}] sampling authors")
    author_works = load_sampled_author_works(
        table_parts,
        sample_mod=sample_mod,
        sample_keep=sample_keep,
        max_authors=max_authors,
        min_author_papers=min_author_papers,
    )
    target_works = {work_id for works in author_works.values() for work_id in works}
    log(f"[{subject}] loading metadata for {len(target_works):,} sampled author works")
    metadata = load_work_metadata(table_parts, target_works)
    target_works = set(metadata)
    author_works = {
        author: {work_id for work_id in works if work_id in target_works}
        for author, works in author_works.items()
    }
    author_works = {
        author: works
        for author, works in author_works.items()
        if len(works) >= min_author_papers
    }
    target_works = {work_id for works in author_works.values() for work_id in works}
    log(
        f"[{subject}] retained {len(author_works):,} authors and "
        f"{len(target_works):,} works after metadata/min-paper filters"
    )
    if calculated_citations:
        log(f"[{subject}] loading calculated annual citations")
        citations = load_calculated_citations(calculated_citations, target_works)
        citation_source = "calculated_references"
    else:
        log(f"[{subject}] loading OpenAlex counts_by_year citations")
        citations = load_citations(table_parts, target_works)
        citation_source = "openalex_counts_by_year"
    log(f"[{subject}] scanning snapshot references")
    edges = extract_reference_edges(
        snapshot_works_dir=snapshot_works_dir,
        target_works=target_works,
        max_snapshot_files=max_snapshot_files,
        reference_workers=reference_workers,
    )
    log(f"[{subject}] found {len(edges):,} sampled-work reference edges")

    related: dict[str, set[str]] = {work_id: {work_id} for work_id in target_works}
    for source, target in edges:
        related.setdefault(source, {source}).add(target)
        related.setdefault(target, {target}).add(source)

    cumulative = {
        work_id: cumulative_by_year(
            citations.get(work_id, {}),
            start_year=max(start_year, int(metadata[work_id]["publication_year"])),
            end_year=end_year,
        )
        for work_id in target_works
    }

    rows = 0
    observed_citations = 0
    tmp_output = output.with_name(f"{output.name}.tmp")
    fieldnames = [
        "subject",
        "author_id",
        "work_id",
        "year",
        "publication_year",
        "paper_age",
        "citations_jt",
        "accumulated_unrelated_citations_jt",
        "accumulated_related_citations_jt",
        "author_subject_papers",
        "related_author_papers",
        "citation_source",
    ]
    with gzip.open(tmp_output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for author_id, works in sorted(author_works.items()):
            works = sorted(works)
            author_total_by_year = Counter()
            for work_id in works:
                for year, value in cumulative.get(work_id, {}).items():
                    author_total_by_year[year] += value
            for focal in works:
                publication_year = int(metadata[focal]["publication_year"])
                first_year = max(start_year, publication_year)
                related_works = set(works) & related.get(focal, {focal})
                for year in range(first_year, end_year + 1):
                    related_stock = sum(cumulative.get(work_id, {}).get(year, 0) for work_id in related_works)
                    total_stock = author_total_by_year.get(year, 0)
                    citations_jt = citations.get(focal, {}).get(year, 0)
                    observed_citations += citations_jt
                    writer.writerow(
                        {
                            "subject": subject,
                            "author_id": author_id,
                            "work_id": focal,
                            "year": year,
                            "publication_year": publication_year,
                            "paper_age": year - publication_year,
                            "citations_jt": citations_jt,
                            "accumulated_unrelated_citations_jt": max(0, total_stock - related_stock),
                            "accumulated_related_citations_jt": related_stock,
                            "author_subject_papers": len(works),
                            "related_author_papers": len(related_works),
                            "citation_source": citation_source,
                        }
                    )
                    rows += 1
                    if rows % 1_000_000 == 0:
                        log(f"[{subject}] wrote {rows:,} regression rows")
    tmp_output.replace(output)
    summary = {
        "subject": subject,
        "output": str(output),
        "authors": len(author_works),
        "works": len(target_works),
        "rows": rows,
        "observed_citations_sum": observed_citations,
        "reference_edges_among_sample_works": len(edges),
        "start_year": start_year,
        "end_year": end_year,
        "sample_mod": sample_mod,
        "sample_keep": sample_keep,
        "max_authors": max_authors,
        "min_author_papers": min_author_papers,
        "max_snapshot_files": max_snapshot_files,
        "reference_workers": reference_workers,
        "citation_source": citation_source,
    }
    output.with_name(f"{output.name}.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, default=DEFAULT_SUBJECT_ROOT)
    parser.add_argument("--snapshot-works-dir", type=Path, default=DEFAULT_SNAPSHOT_WORKS_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--start-year", type=int, default=1900)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--sample-mod", type=int, default=2000)
    parser.add_argument("--sample-keep", type=int, default=1)
    parser.add_argument("--max-authors", type=int, default=5000)
    parser.add_argument("--min-author-papers", type=int, default=2)
    parser.add_argument("--max-snapshot-files", type=int, default=0)
    parser.add_argument("--reference-workers", type=int, default=12)
    parser.add_argument(
        "--economics-calculated-citations",
        type=Path,
        default=Path(
            "/root/sdb1/openalex/subjects/economics_econometrics_and_finance/"
            "calculated_citations/calculated_citations_by_year.csv.gz"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    subjects = args.subject or DEFAULT_SUBJECTS
    summaries = []
    for subject in subjects:
        calculated = (
            args.economics_calculated_citations
            if subject == "economics_econometrics_and_finance"
            and args.economics_calculated_citations.exists()
            else None
        )
        summary = build_subject(
            subject=subject,
            subject_root=args.subject_root,
            snapshot_works_dir=args.snapshot_works_dir,
            output_root=args.output_root,
            start_year=args.start_year,
            end_year=args.end_year,
            sample_mod=args.sample_mod,
            sample_keep=args.sample_keep,
            max_authors=args.max_authors,
            min_author_papers=args.min_author_papers,
            max_snapshot_files=args.max_snapshot_files,
            reference_workers=args.reference_workers,
            calculated_citations=calculated,
        )
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
        summaries.append(summary)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "summary.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
