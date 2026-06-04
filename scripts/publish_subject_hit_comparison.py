#!/usr/bin/env python3
"""Publish compact hit-effect summaries across subjects."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any


SUBJECT_ROOT = Path("/root/sdb1/openalex/subjects")
REPORT_ROOT = Path("/root/sdb1/projects/Citations/reports")

SUBJECTS = {
    "economics_econometrics_and_finance": "Economics, Econometrics, and Finance",
    "agricultural_and_biological_sciences": "Agricultural and Biological Sciences",
    "biochemistry_genetics_and_molecular_biology": "Biochemistry, Genetics, and Molecular Biology",
    "physics_and_astronomy": "Physics and Astronomy",
}

ECONOMICS_OLD_COUNTS = {
    "label": "Economics, old OpenAlex counts_by_year",
    "citation_source": "openalex_counts_by_year",
    "works": 7_924_745,
    "hit_events": 11_158,
    "paper_author_hit_pairs": 76_074,
    "event_panel_rows": 1_597_554,
    "mean_pre": 0.1612,
    "mean_post": 0.5000,
    "mean_delta_zero": 0.3388,
    "observed_pairs": 26_092,
    "mean_delta_observed": 2.0412,
    "missing_overall": 0.7027,
    "missing_pre": 0.5204,
    "missing_post": 0.8685,
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_event_summary(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def missing_rates(event_rows: list[dict[str, str]]) -> tuple[float, float, float]:
    missing_total = 0
    total = 0
    missing_pre = 0
    total_pre = 0
    missing_post = 0
    total_post = 0
    for row in event_rows:
        pairs = int(row["paper_author_hit_pairs"])
        observed = int(row["observed_pair_years"])
        missing = pairs - observed
        event_time = int(row["event_time"])
        total += pairs
        missing_total += missing
        if event_time < 0:
            total_pre += pairs
            missing_pre += missing
        else:
            total_post += pairs
            missing_post += missing
    return (
        missing_total / total if total else 0,
        missing_pre / total_pre if total_pre else 0,
        missing_post / total_post if total_post else 0,
    )


def row_from_summary(label: str, summary: dict[str, Any], event_rows: list[dict[str, str]]) -> dict[str, Any]:
    simple = summary["simple_estimates"]
    missing_overall, missing_pre, missing_post = missing_rates(event_rows)
    return {
        "label": label,
        "citation_source": summary["criteria"]["citation_source"],
        "works": summary["works"],
        "hit_events": summary["hit_events"],
        "paper_author_hit_pairs": simple["paper_author_hit_pairs"],
        "event_panel_rows": simple["event_panel_rows"],
        "mean_pre": simple["mean_pre_annual_citations_zero_missing"],
        "mean_post": simple["mean_post_annual_citations_zero_missing"],
        "mean_delta_zero": simple["mean_added_annual_citations_zero_missing"],
        "observed_pairs": simple["observed_only_pairs_with_pre_and_post"],
        "mean_delta_observed": simple["mean_added_annual_citations_observed_only"],
        "missing_overall": missing_overall,
        "missing_pre": missing_pre,
        "missing_post": missing_post,
    }


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def pct(value: float) -> str:
    return f"{100 * value:.2f}%"


def copy_artifacts(subject: str, source_dir: Path, report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    for name in ("summary.json", "event_time_summary.csv", "economics_hit_effects_report.md"):
        source = source_dir / name
        if source.exists():
            target_name = "hit_effects_report.md" if name == "economics_hit_effects_report.md" else name
            shutil.copy2(source, report_dir / target_name)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "label",
        "citation_source",
        "works",
        "hit_events",
        "paper_author_hit_pairs",
        "event_panel_rows",
        "mean_pre",
        "mean_post",
        "mean_delta_zero",
        "observed_pairs",
        "mean_delta_observed",
        "missing_overall",
        "missing_pre",
        "missing_post",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Subject Hit-Effect Comparison",
        "",
        "This report compares the same descriptive hit-effect design across completed subject panels. The three non-economics subjects use OpenAlex `counts_by_year` and therefore still have sparse citation-year rows. Economics is shown both with the earlier sparse `counts_by_year` run and with the corrected recalculated-reference citation run.",
        "",
        "## Summary",
        "",
        "| Subject / run | Citation source | Works | Hit events | Pairs | Rows | Missing overall | Missing pre | Missing post | Mean pre | Mean post | Added, zero-filled | Added, observed-only | Observed pairs |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["label"],
                    row["citation_source"],
                    fmt(row["works"]),
                    fmt(row["hit_events"]),
                    fmt(row["paper_author_hit_pairs"]),
                    fmt(row["event_panel_rows"]),
                    pct(row["missing_overall"]),
                    pct(row["missing_pre"]),
                    pct(row["missing_post"]),
                    fmt(row["mean_pre"]),
                    fmt(row["mean_post"]),
                    fmt(row["mean_delta_zero"]),
                    fmt(row["mean_delta_observed"]),
                    fmt(row["observed_pairs"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The economics recalculated-reference run is the only run here with the zero-count citation fix applied.",
            "- The three new subject runs are intentionally pre-recalculation baselines. Their observed-only estimates should be treated cautiously when missing rates are high or asymmetric around the hit year.",
            "- Large event panels remain on the SSD. GitHub contains only compact summaries and event-time tables.",
            "",
            "## Output Folders",
            "",
        ]
    )
    for subject, label in SUBJECTS.items():
        if subject == "economics_econometrics_and_finance":
            lines.append(f"- {label}: `reports/economics/`")
        else:
            lines.append(f"- {label}: `reports/subjects/{subject}/hit_effects_counts_by_year/`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish subject hit-effect comparison.")
    parser.add_argument("--subject-root", type=Path, default=SUBJECT_ROOT)
    parser.add_argument("--report-root", type=Path, default=REPORT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = [ECONOMICS_OLD_COUNTS]

    econ_dir = args.subject_root / "economics_econometrics_and_finance" / "analysis" / "hit_effects"
    rows.append(
        row_from_summary(
            "Economics, recalculated references",
            read_json(econ_dir / "summary.json"),
            read_event_summary(econ_dir / "event_time_summary.csv"),
        )
    )

    for subject, label in SUBJECTS.items():
        if subject == "economics_econometrics_and_finance":
            continue
        analysis_dir = args.subject_root / subject / "analysis" / "hit_effects_counts_by_year"
        summary_path = analysis_dir / "summary.json"
        event_path = analysis_dir / "event_time_summary.csv"
        if not summary_path.exists() or not event_path.exists():
            raise SystemExit(f"Missing analysis outputs for {subject}: {analysis_dir}")
        rows.append(row_from_summary(label, read_json(summary_path), read_event_summary(event_path)))
        copy_artifacts(
            subject,
            analysis_dir,
            args.report_root / "subjects" / subject / "hit_effects_counts_by_year",
        )

    comparison_dir = args.report_root / "subjects"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    write_csv(comparison_dir / "subject_hit_effects_comparison.csv", rows)
    write_markdown(comparison_dir / "subject_hit_effects_comparison.md", rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
