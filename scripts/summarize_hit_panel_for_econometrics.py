#!/usr/bin/env python3
"""Create econometrics-ready summaries from the hit-effect event panel."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


DEFAULT_ANALYSIS_DIR = Path(
    "/root/sdb1/openalex/subjects/economics_econometrics_and_finance/analysis/hit_effects"
)
DEFAULT_OUTPUT_DIR = DEFAULT_ANALYSIS_DIR / "econometrics_summaries"


@dataclass
class CellStats:
    rows: int = 0
    observed_rows: int = 0
    citations_sum_zero: float = 0.0
    citations_sum_observed: float = 0.0

    def add(self, citations: float, observed: bool) -> None:
        self.rows += 1
        self.citations_sum_zero += citations
        if observed:
            self.observed_rows += 1
            self.citations_sum_observed += citations

    def as_row(self, keys: tuple[str, ...]) -> dict[str, str | int | float]:
        mean_zero = self.citations_sum_zero / self.rows if self.rows else 0.0
        mean_observed = (
            self.citations_sum_observed / self.observed_rows if self.observed_rows else ""
        )
        missing_rate = 1 - (self.observed_rows / self.rows) if self.rows else 0.0
        row: dict[str, str | int | float] = {
            "rows": self.rows,
            "observed_rows": self.observed_rows,
            "missing_rows": self.rows - self.observed_rows,
            "missing_rate": f"{missing_rate:.8f}",
            "mean_citations_zero_missing": f"{mean_zero:.8f}",
            "mean_citations_observed_only": (
                "" if mean_observed == "" else f"{mean_observed:.8f}"
            ),
        }
        for name, value in zip(keys[::2], keys[1::2]):
            row[name] = value
        return row


@dataclass
class PairStats:
    pre_zero: list[float]
    post_zero: list[float]
    pre_observed: list[float]
    post_observed: list[float]


def float_or_zero(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def int_or_zero(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def age_bin(age: int) -> str:
    if age < 0:
        return "pre-publication"
    if age <= 2:
        return "0-2"
    if age <= 5:
        return "3-5"
    if age <= 10:
        return "6-10"
    if age <= 20:
        return "11-20"
    return "21+"


def add_cell(
    cells: dict[tuple[str, ...], CellStats],
    key: tuple[str, ...],
    citations: float,
    observed: bool,
) -> None:
    cells[key].add(citations, observed)


def write_cells(path: Path, cells: dict[tuple[str, ...], CellStats]) -> None:
    if not cells:
        return
    key_names = list(next(iter(cells))[::2])
    fieldnames = key_names + [
        "rows",
        "observed_rows",
        "missing_rows",
        "missing_rate",
        "mean_citations_zero_missing",
        "mean_citations_observed_only",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key, stats in sorted(cells.items()):
            writer.writerow(stats.as_row(key))


def write_pair_deltas(path: Path, pair_stats: dict[tuple[str, str, str], PairStats]) -> dict[str, object]:
    fieldnames = [
        "author_id",
        "focal_work_id",
        "hit_work_id",
        "pre_mean_zero",
        "post_mean_zero",
        "delta_zero",
        "pre_mean_observed",
        "post_mean_observed",
        "delta_observed",
    ]
    deltas_zero = []
    deltas_observed = []
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for (author_id, focal_work_id, hit_work_id), stats in sorted(pair_stats.items()):
            pre_zero = mean(stats.pre_zero) if stats.pre_zero else 0.0
            post_zero = mean(stats.post_zero) if stats.post_zero else 0.0
            delta_zero = post_zero - pre_zero
            deltas_zero.append(delta_zero)
            if stats.pre_observed and stats.post_observed:
                pre_observed: str | float = mean(stats.pre_observed)
                post_observed: str | float = mean(stats.post_observed)
                delta_observed: str | float = post_observed - pre_observed
                deltas_observed.append(delta_observed)
            else:
                pre_observed = ""
                post_observed = ""
                delta_observed = ""
            writer.writerow(
                {
                    "author_id": author_id,
                    "focal_work_id": focal_work_id,
                    "hit_work_id": hit_work_id,
                    "pre_mean_zero": f"{pre_zero:.8f}",
                    "post_mean_zero": f"{post_zero:.8f}",
                    "delta_zero": f"{delta_zero:.8f}",
                    "pre_mean_observed": (
                        "" if pre_observed == "" else f"{float(pre_observed):.8f}"
                    ),
                    "post_mean_observed": (
                        "" if post_observed == "" else f"{float(post_observed):.8f}"
                    ),
                    "delta_observed": (
                        "" if delta_observed == "" else f"{float(delta_observed):.8f}"
                    ),
                }
            )
    return {
        "paper_author_hit_pairs": len(pair_stats),
        "mean_delta_zero_missing": mean(deltas_zero) if deltas_zero else 0.0,
        "observed_pre_post_pairs": len(deltas_observed),
        "mean_delta_observed_only": mean(deltas_observed) if deltas_observed else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize hit-effect panel cells for econometrics diagnostics."
    )
    parser.add_argument(
        "--panel",
        type=Path,
        default=DEFAULT_ANALYSIS_DIR / "paper_author_hit_year_panel.csv.gz",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    by_event_time: dict[tuple[str, ...], CellStats] = defaultdict(CellStats)
    by_hit_cohort_event_time: dict[tuple[str, ...], CellStats] = defaultdict(CellStats)
    by_age_bin_event_time: dict[tuple[str, ...], CellStats] = defaultdict(CellStats)
    by_author_position_event_time: dict[tuple[str, ...], CellStats] = defaultdict(CellStats)
    pair_stats: dict[tuple[str, str, str], PairStats] = {}
    rows = 0

    with gzip.open(args.panel, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows += 1
            event_time = int_or_zero(row.get("event_time"))
            hit_year = int_or_zero(row.get("hit_publication_year"))
            age = int_or_zero(row.get("years_since_focal_publication"))
            position = row.get("author_position_on_focal") or "unknown"
            observed = int_or_zero(row.get("citations_observed")) == 1
            citations = float_or_zero(row.get("citations"))

            add_cell(
                by_event_time,
                ("event_time", str(event_time)),
                citations,
                observed,
            )
            add_cell(
                by_hit_cohort_event_time,
                ("hit_publication_year", str(hit_year), "event_time", str(event_time)),
                citations,
                observed,
            )
            add_cell(
                by_age_bin_event_time,
                ("focal_age_bin", age_bin(age), "event_time", str(event_time)),
                citations,
                observed,
            )
            add_cell(
                by_author_position_event_time,
                ("author_position_on_focal", position, "event_time", str(event_time)),
                citations,
                observed,
            )

            pair_key = (
                row.get("author_id", ""),
                row.get("focal_work_id", ""),
                row.get("hit_work_id", ""),
            )
            stats = pair_stats.setdefault(
                pair_key,
                PairStats(pre_zero=[], post_zero=[], pre_observed=[], post_observed=[]),
            )
            if event_time < 0:
                stats.pre_zero.append(citations)
                if observed:
                    stats.pre_observed.append(citations)
            else:
                stats.post_zero.append(citations)
                if observed:
                    stats.post_observed.append(citations)

    write_cells(args.output_dir / "event_time_cells.csv", by_event_time)
    write_cells(args.output_dir / "hit_cohort_event_time_cells.csv", by_hit_cohort_event_time)
    write_cells(args.output_dir / "focal_age_bin_event_time_cells.csv", by_age_bin_event_time)
    write_cells(
        args.output_dir / "author_position_event_time_cells.csv",
        by_author_position_event_time,
    )
    pair_summary = write_pair_deltas(args.output_dir / "pair_pre_post_deltas.csv.gz", pair_stats)
    summary = {
        "input_panel": str(args.panel),
        "output_dir": str(args.output_dir),
        "rows": rows,
        **pair_summary,
        "outputs": {
            "event_time_cells": str(args.output_dir / "event_time_cells.csv"),
            "hit_cohort_event_time_cells": str(
                args.output_dir / "hit_cohort_event_time_cells.csv"
            ),
            "focal_age_bin_event_time_cells": str(
                args.output_dir / "focal_age_bin_event_time_cells.csv"
            ),
            "author_position_event_time_cells": str(
                args.output_dir / "author_position_event_time_cells.csv"
            ),
            "pair_pre_post_deltas": str(args.output_dir / "pair_pre_post_deltas.csv.gz"),
        },
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
