#!/usr/bin/env python3
"""Copy economics analysis outputs into repo reports and draw event-time chart."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path


DEFAULT_ANALYSIS_DIR = Path(
    "/root/sdb1/openalex/subjects/economics_econometrics_and_finance/analysis/hit_effects"
)
DEFAULT_REPORT_DIR = Path("/root/sdb1/projects/Citations/reports/economics")
ECONOMETRICS_SUMMARY_FILES = (
    "summary.json",
    "event_time_cells.csv",
    "hit_cohort_event_time_cells.csv",
    "focal_age_bin_event_time_cells.csv",
    "author_position_event_time_cells.csv",
)


def float_or_none(value: str) -> float | None:
    try:
        if value == "":
            return None
        return float(value)
    except ValueError:
        return None


def load_event_rows(path: Path) -> list[dict[str, float | int | None]]:
    rows: list[dict[str, float | int | None]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "event_time": int(row["event_time"]),
                    "mean_zero": float(row["mean_citations_zero_missing"]),
                    "mean_observed": float_or_none(row["mean_citations_observed_only"]),
                }
            )
    return rows


def points_for_series(
    rows: list[dict[str, float | int | None]],
    key: str,
    *,
    width: int,
    height: int,
    margin: int,
    y_max: float,
) -> str:
    event_times = [int(row["event_time"]) for row in rows]
    x_min = min(event_times)
    x_max = max(event_times)
    x_span = max(1, x_max - x_min)
    y_span = max(1.0, y_max)
    points = []
    for row in rows:
        value = row[key]
        if value is None:
            continue
        x = margin + (int(row["event_time"]) - x_min) / x_span * (width - 2 * margin)
        y = height - margin - float(value) / y_span * (height - 2 * margin)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def write_event_chart(rows: list[dict[str, float | int | None]], output: Path) -> None:
    width = 900
    height = 520
    margin = 70
    y_values = [
        float(row[key])
        for row in rows
        for key in ("mean_zero", "mean_observed")
        if row[key] is not None
    ]
    y_max = max(y_values) * 1.1 if y_values else 1.0
    zero_points = points_for_series(
        rows, "mean_zero", width=width, height=height, margin=margin, y_max=y_max
    )
    observed_points = points_for_series(
        rows, "mean_observed", width=width, height=height, margin=margin, y_max=y_max
    )
    event_times = [int(row["event_time"]) for row in rows]
    x_min = min(event_times)
    x_max = max(event_times)
    x_span = max(1, x_max - x_min)
    zero_x = margin + (0 - x_min) / x_span * (width - 2 * margin)
    output.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#333333"/>
  <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#333333"/>
  <line x1="{zero_x:.1f}" y1="{margin}" x2="{zero_x:.1f}" y2="{height - margin}" stroke="#999999" stroke-dasharray="6 6"/>
  <text x="{width / 2:.1f}" y="34" text-anchor="middle" font-family="Arial, sans-serif" font-size="22">Economics Hit-Effect Event-Time Means</text>
  <text x="{width / 2:.1f}" y="{height - 20}" text-anchor="middle" font-family="Arial, sans-serif" font-size="16">Years relative to hit publication</text>
  <text x="22" y="{height / 2:.1f}" transform="rotate(-90 22 {height / 2:.1f})" text-anchor="middle" font-family="Arial, sans-serif" font-size="16">Mean annual citations</text>
  <text x="{margin}" y="{height - margin + 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13">{x_min}</text>
  <text x="{zero_x:.1f}" y="{height - margin + 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13">0</text>
  <text x="{width - margin}" y="{height - margin + 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13">{x_max}</text>
  <text x="{margin - 10}" y="{height - margin + 4}" text-anchor="end" font-family="Arial, sans-serif" font-size="13">0</text>
  <text x="{margin - 10}" y="{margin + 4}" text-anchor="end" font-family="Arial, sans-serif" font-size="13">{y_max:.2f}</text>
  <polyline fill="none" stroke="#1f77b4" stroke-width="3" points="{zero_points}"/>
  <polyline fill="none" stroke="#d62728" stroke-width="3" points="{observed_points}"/>
  <rect x="{width - 265}" y="64" width="210" height="58" fill="#ffffff" stroke="#dddddd"/>
  <line x1="{width - 250}" y1="84" x2="{width - 212}" y2="84" stroke="#1f77b4" stroke-width="3"/>
  <text x="{width - 202}" y="89" font-family="Arial, sans-serif" font-size="14">Calculated missing=0</text>
  <line x1="{width - 250}" y1="107" x2="{width - 212}" y2="107" stroke="#d62728" stroke-width="3"/>
  <text x="{width - 202}" y="112" font-family="Arial, sans-serif" font-size="14">Observed only</text>
</svg>
""",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish economics analysis artifacts.")
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    for name in ("economics_hit_effects_report.md", "summary.json", "event_time_summary.csv"):
        shutil.copy2(args.analysis_dir / name, args.report_dir / name)
    econometrics_dir = args.analysis_dir / "econometrics_summaries"
    if econometrics_dir.exists():
        report_econometrics_dir = args.report_dir / "econometrics_summaries"
        report_econometrics_dir.mkdir(parents=True, exist_ok=True)
        for name in ECONOMETRICS_SUMMARY_FILES:
            source = econometrics_dir / name
            if source.exists():
                shutil.copy2(source, report_econometrics_dir / name)
    rows = load_event_rows(args.analysis_dir / "event_time_summary.csv")
    write_event_chart(rows, args.report_dir / "event_time_means.svg")
    summary = json.loads((args.analysis_dir / "summary.json").read_text(encoding="utf-8"))
    (args.report_dir / "README.md").write_text(
        "\n".join(
            [
                "# Economics Hit-Effect Analysis",
                "",
                "This folder is generated from the economics subject database on the SSD.",
                "",
                f"- Hit events: {summary['hit_events']:,}",
                f"- Focal work IDs: {summary['focal_work_ids']:,}",
                f"- Event-panel rows: {summary['simple_estimates']['event_panel_rows']:,}",
                f"- Mean added annual citations: {summary['simple_estimates']['mean_added_annual_citations_zero_missing']:.4f}",
                "",
                "![Event-time means](event_time_means.svg)",
                "",
                "Aggregated econometrics tables, when available, are copied into `econometrics_summaries/`.",
                "The large pair-level pre/post delta file is kept on the SSD and is not committed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
