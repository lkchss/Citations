#!/usr/bin/env python3
"""Analyze citation spillovers from author hit papers in economics."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_TABLE_DIR = Path("/root/sdb1/openalex/subjects/economics_econometrics_and_finance")
DEFAULT_WORKS_JSONL_DIR = Path("/root/sdb1/openalex/snapshot/data/works")
DEFAULT_CALCULATED_CITATIONS = (
    DEFAULT_TABLE_DIR / "calculated_citations" / "calculated_citations_by_year.csv.gz"
)
DEFAULT_OUTPUT_DIR = Path(
    "/root/sdb1/openalex/subjects/economics_econometrics_and_finance/analysis/hit_effects"
)


@dataclass(frozen=True)
class Work:
    work_id: str
    title: str
    publication_year: int
    work_type: str
    cited_by_count: int
    fwci: str


@dataclass(frozen=True)
class Authorship:
    work_id: str
    author_id: str
    author_name: str
    author_position: str
    author_sequence: str


@dataclass(frozen=True)
class HitCandidate:
    author_id: str
    author_name: str
    hit_work_id: str
    hit_publication_year: int
    hit_cited_by_count: int
    author_total_citations: int
    author_included_works: int
    hit_author_citation_share: float


def read_csv_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def iter_table_rows(table_dir: Path, table_name: str):
    flat_path = table_dir / f"{table_name}.csv.gz"
    if flat_path.exists():
        yield from read_csv_gz(flat_path)
        return

    parts_dir = table_dir / "tables_parts"
    if not parts_dir.exists() and table_dir.name == "tables_parts":
        parts_dir = table_dir
    part_paths = sorted(parts_dir.glob(f"part_*_{table_name}.csv.gz"))
    if not part_paths:
        raise FileNotFoundError(f"No {table_name} table found under {table_dir}")
    for path in part_paths:
        yield from read_csv_gz(path)


def int_or_zero(value: str | int | None) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def float_or_blank(value: str | None) -> str:
    return "" if value in (None, "") else str(value)


def iter_work_jsonl(paths: list[Path]):
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def extract_top_level_id(line: str) -> str:
    marker = '"id":"'
    start = line.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = line.find('"', start)
    if end < 0:
        return ""
    return line[start:end]


def load_works(table_dir: Path) -> dict[str, Work]:
    works = {}
    for row in iter_table_rows(table_dir, "works"):
        works[row["work_id"]] = Work(
            work_id=row["work_id"],
            title=row["title"],
            publication_year=int_or_zero(row["publication_year"]),
            work_type=row["type"],
            cited_by_count=int_or_zero(row["cited_by_count"]),
            fwci=float_or_blank(row.get("fwci")),
        )
    return works


def compute_author_stats(
    table_dir: Path, works: dict[str, Work]
) -> tuple[dict[str, int], dict[str, int], dict[str, str]]:
    author_total_citations: dict[str, int] = defaultdict(int)
    author_work_count: dict[str, int] = defaultdict(int)
    author_names: dict[str, str] = {}
    for row in iter_table_rows(table_dir, "work_authors"):
        work = works.get(row["work_id"])
        if not work:
            continue
        author_id = row["author_id"]
        author_total_citations[author_id] += work.cited_by_count
        author_work_count[author_id] += 1
        if row["author_name"]:
            author_names.setdefault(author_id, row["author_name"])
    return author_total_citations, author_work_count, author_names


def find_hit_candidates(
    *,
    table_dir: Path,
    works: dict[str, Work],
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
    for row in iter_table_rows(table_dir, "work_authors"):
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
    table_dir: Path, works: dict[str, Work], candidate_authors: set[str]
) -> dict[str, list[Authorship]]:
    works_by_author: dict[str, list[Authorship]] = defaultdict(list)
    for row in iter_table_rows(table_dir, "work_authors"):
        author_id = row["author_id"]
        if author_id not in candidate_authors:
            continue
        if row["work_id"] not in works:
            continue
        works_by_author[author_id].append(
            Authorship(
                work_id=row["work_id"],
                author_id=author_id,
                author_name=row["author_name"],
                author_position=row["author_position"],
                author_sequence=row["author_sequence"],
            )
        )
    return works_by_author


def load_hit_references(works_jsonl_dir: Path, hit_work_ids: set[str]) -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}
    if not hit_work_ids:
        return references
    files = sorted(works_jsonl_dir.rglob("*.gz"))
    seen = 0
    next_progress_log = 1_000_000
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                seen += 1
                work_id = extract_top_level_id(line)
                if work_id not in hit_work_ids:
                    continue
                work = json.loads(line)
                references[work_id] = {str(item) for item in (work.get("referenced_works") or [])}
                if len(references) == len(hit_work_ids):
                    print(
                        f"found all hit references after records_seen={seen} files_scanned={path}",
                        flush=True,
                    )
                    return references
        if seen >= next_progress_log:
            print(
                f"reference_scan records_seen={seen} hit_references_found={len(references)}",
                flush=True,
            )
            next_progress_log = ((seen // 1_000_000) + 1) * 1_000_000
    return references


def load_citations_for_focals(
    table_dir: Path,
    focal_work_ids: set[str],
    calculated_citations: Path | None,
) -> dict[str, dict[int, int]]:
    citations: dict[str, dict[int, int]] = defaultdict(dict)
    if calculated_citations:
        rows = read_csv_gz(calculated_citations)
    else:
        rows = iter_table_rows(table_dir, "work_citations_by_year")
    for row in rows:
        work_id = row["work_id"]
        if work_id in focal_work_ids:
            citations[work_id][int_or_zero(row["year"])] = int_or_zero(
                row.get("calculated_citations") or row.get("citations")
            )
    return citations


def write_hit_events(
    *,
    output: Path,
    hit_rows: list[dict[str, Any]],
) -> None:
    fieldnames = [
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
    ]
    with gzip.open(output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(hit_rows)


def write_event_panel_and_summaries(
    *,
    output: Path,
    hit_focal_rows: list[dict[str, Any]],
    works: dict[str, Work],
    citations: dict[str, dict[int, int]],
    pre_years: int,
    post_years: int,
    zero_missing_citations: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
    event_stats: dict[int, dict[str, Any]] = {
        event_time: {"values_zero": [], "values_observed": []}
        for event_time in range(-pre_years, post_years + 1)
    }
    pair_stats = []
    rows = 0
    with gzip.open(output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in hit_focal_rows:
            focal = works[item["focal_work_id"]]
            hit = works[item["hit_work_id"]]
            pre_values_zero = []
            post_values_zero = []
            pre_values_observed = []
            post_values_observed = []
            for event_time in range(-pre_years, post_years + 1):
                year = item["hit_publication_year"] + event_time
                observed = int(year in citations.get(focal.work_id, {}))
                if year < focal.publication_year:
                    citation_value: str | int = 0
                    observed = 1
                elif observed:
                    citation_value = citations[focal.work_id][year]
                elif zero_missing_citations:
                    citation_value = 0
                    observed = 1
                else:
                    citation_value = ""
                zero_value = int(citation_value or 0)
                event_stats[event_time]["values_zero"].append(zero_value)
                if observed:
                    event_stats[event_time]["values_observed"].append(zero_value)
                if event_time < 0:
                    pre_values_zero.append(zero_value)
                    if observed:
                        pre_values_observed.append(zero_value)
                else:
                    post_values_zero.append(zero_value)
                    if observed:
                        post_values_observed.append(zero_value)
                writer.writerow(
                    {
                        "author_id": item["author_id"],
                        "author_name": item["author_name"],
                        "author_position_on_focal": item["author_position_on_focal"],
                        "focal_work_id": focal.work_id,
                        "focal_title": focal.title,
                        "focal_publication_year": focal.publication_year,
                        "focal_type": focal.work_type,
                        "focal_cited_by_count_total": focal.cited_by_count,
                        "focal_fwci": focal.fwci,
                        "hit_work_id": hit.work_id,
                        "hit_title": hit.title,
                        "hit_publication_year": hit.publication_year,
                        "hit_type": hit.work_type,
                        "hit_cited_by_count_total": hit.cited_by_count,
                        "hit_author_total_citations": item["author_total_citations"],
                        "hit_author_included_works": item["author_included_works"],
                        "hit_author_citation_share": f"{item['hit_author_citation_share']:.8f}",
                        "hit_unrelated_focal_works": item["hit_unrelated_focal_works"],
                        "year": year,
                        "event_time": event_time,
                        "post_hit": int(event_time >= 0),
                        "years_since_focal_publication": year - focal.publication_year,
                        "citations": citation_value,
                        "citations_observed": observed,
                    }
                )
                rows += 1
            pair_stats.append(
                {
                    "pre_mean_zero": mean(pre_values_zero) if pre_values_zero else 0,
                    "post_mean_zero": mean(post_values_zero) if post_values_zero else 0,
                    "pre_mean_observed": mean(pre_values_observed) if pre_values_observed else None,
                    "post_mean_observed": mean(post_values_observed) if post_values_observed else None,
                }
            )

    event_summary_rows = []
    for event_time, stats in event_stats.items():
        observed_values = stats["values_observed"]
        zero_values = stats["values_zero"]
        event_summary_rows.append(
            {
                "event_time": event_time,
                "paper_author_hit_pairs": len(zero_values),
                "observed_pair_years": len(observed_values),
                "mean_citations_zero_missing": mean(zero_values) if zero_values else 0,
                "mean_citations_observed_only": mean(observed_values) if observed_values else "",
            }
        )

    pre_zero = [item["pre_mean_zero"] for item in pair_stats]
    post_zero = [item["post_mean_zero"] for item in pair_stats]
    observed_pairs = [
        item
        for item in pair_stats
        if item["pre_mean_observed"] is not None and item["post_mean_observed"] is not None
    ]
    simple_estimates = {
        "event_panel_rows": rows,
        "paper_author_hit_pairs": len(pair_stats),
        "mean_pre_annual_citations_zero_missing": mean(pre_zero) if pre_zero else 0,
        "mean_post_annual_citations_zero_missing": mean(post_zero) if post_zero else 0,
        "mean_added_annual_citations_zero_missing": (
            mean(post - pre for post, pre in zip(post_zero, pre_zero)) if pair_stats else 0
        ),
        "observed_only_pairs_with_pre_and_post": len(observed_pairs),
        "mean_added_annual_citations_observed_only": (
            mean(
                item["post_mean_observed"] - item["pre_mean_observed"]  # type: ignore[operator]
                for item in observed_pairs
            )
            if observed_pairs
            else None
        ),
    }
    return simple_estimates, event_summary_rows


def write_event_summary(output: Path, rows: list[dict[str, Any]]) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "event_time",
                "paper_author_hit_pairs",
                "observed_pair_years",
                "mean_citations_zero_missing",
                "mean_citations_observed_only",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_report(output: Path, summary: dict[str, Any], event_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Economics Hit-Effect First Pass",
        "",
        "## Criteria",
        "",
        f"- Minimum hit citations: {summary['criteria']['min_hit_citations']}",
        f"- Minimum hit author citation share: {summary['criteria']['min_hit_author_citation_share']}",
        f"- Minimum unrelated pre-hit focal papers per hit-author event: {summary['criteria']['min_unrelated_focal_works']}",
        f"- Event window: -{summary['criteria']['pre_years']} to +{summary['criteria']['post_years']} years",
        "",
        "## Counts",
        "",
        f"- Economics works: {summary['works']:,}",
        f"- Candidate hit-author rows before unrelated-paper filter: {summary['hit_candidates']:,}",
        f"- Accepted hit-author events: {summary['hit_events']:,}",
        f"- Focal paper-author-hit pairs: {summary['simple_estimates']['paper_author_hit_pairs']:,}",
        f"- Event-panel rows: {summary['simple_estimates']['event_panel_rows']:,}",
        "",
        "## Simple Estimate",
        "",
        "- This is not yet a causal design; it is the treated focal papers' before/after citation change around the author's hit.",
        f"- Mean pre-hit annual citations, missing as zero: {summary['simple_estimates']['mean_pre_annual_citations_zero_missing']:.4f}",
        f"- Mean post-hit annual citations, missing as zero: {summary['simple_estimates']['mean_post_annual_citations_zero_missing']:.4f}",
        f"- Mean added annual citations, missing as zero: {summary['simple_estimates']['mean_added_annual_citations_zero_missing']:.4f}",
        f"- Observed-only pairs with both pre and post citation observations: {summary['simple_estimates']['observed_only_pairs_with_pre_and_post']:,}",
    ]
    observed_delta = summary["simple_estimates"]["mean_added_annual_citations_observed_only"]
    if observed_delta is not None:
        lines.append(f"- Mean added annual citations, observed-only: {observed_delta:.4f}")
    lines.extend(["", "## Event-Time Means", "", "| Event Time | Mean Citations, Missing=0 | Mean Citations, Observed Only |", "|---:|---:|---:|"])
    for row in event_rows:
        observed = row["mean_citations_observed_only"]
        observed_text = "" if observed == "" else f"{observed:.4f}"
        lines.append(
            f"| {row['event_time']} | {row['mean_citations_zero_missing']:.4f} | {observed_text} |"
        )
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze economics citation spillovers from hit papers.")
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--works-jsonl-dir", type=Path, default=DEFAULT_WORKS_JSONL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--calculated-citations",
        type=Path,
        default=DEFAULT_CALCULATED_CITATIONS,
        help="Annual citation file calculated from referenced_works.",
    )
    parser.add_argument(
        "--use-openalex-counts-by-year",
        action="store_true",
        help="Use OpenAlex counts_by_year instead of calculated referenced_works citations.",
    )
    parser.add_argument("--min-hit-citations", type=int, default=101)
    parser.add_argument("--min-hit-author-citation-share", type=float, default=0.5)
    parser.add_argument("--min-author-included-works", type=int, default=4)
    parser.add_argument("--min-unrelated-focal-works", type=int, default=3)
    parser.add_argument("--min-focal-age-at-hit", type=int, default=1)
    parser.add_argument("--min-hit-year", type=int, default=1990)
    parser.add_argument("--max-hit-year", type=int, default=0)
    parser.add_argument("--pre-years", type=int, default=5)
    parser.add_argument("--post-years", type=int, default=5)
    parser.add_argument("--zero-missing-citations", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.use_openalex_counts_by_year:
        args.calculated_citations = None
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("loading works", flush=True)
    works = load_works(args.table_dir)
    print(f"works={len(works)}", flush=True)

    print("computing author stats", flush=True)
    author_total_citations, author_work_count, author_names = compute_author_stats(
        args.table_dir, works
    )
    print(f"authors={len(author_work_count)}", flush=True)

    print("finding hit candidates", flush=True)
    hit_candidates = find_hit_candidates(
        table_dir=args.table_dir,
        works=works,
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
    works_by_author = collect_candidate_author_works(args.table_dir, works, candidate_authors)

    print("loading hit references from JSONL", flush=True)
    hit_references = load_hit_references(args.works_jsonl_dir, hit_work_ids)

    hit_rows = []
    hit_focal_rows = []
    focal_work_ids = set()
    for hit in hit_candidates:
        hit_work = works[hit.hit_work_id]
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
    calculated_citations = (
        args.calculated_citations if args.calculated_citations and args.calculated_citations.exists() else None
    )
    if args.calculated_citations and not calculated_citations:
        raise SystemExit(f"Calculated citations file not found: {args.calculated_citations}")
    citations = load_citations_for_focals(args.table_dir, focal_work_ids, calculated_citations)
    zero_missing_citations = args.zero_missing_citations or bool(calculated_citations)

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
        zero_missing_citations=zero_missing_citations,
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
            "zero_missing_citations": zero_missing_citations,
            "citation_source": "calculated_references" if calculated_citations else "openalex_counts_by_year",
            "calculated_citations": str(calculated_citations) if calculated_citations else "",
        },
        "works": len(works),
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
