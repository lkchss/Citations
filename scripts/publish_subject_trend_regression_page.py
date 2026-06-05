#!/usr/bin/env python3
"""Publish subject trend figures, summary tables, and simple regressions."""

from __future__ import annotations

import csv
import html
import subprocess
from pathlib import Path
from typing import Any


REPORT_ROOT = Path("/root/sdb1/projects/Citations/reports")
REPO_ROOT = REPORT_ROOT.parent
OUTPUT = REPORT_ROOT / "subjects" / "trend_regression_comparison.html"
STARGAZER_OUTPUT = REPORT_ROOT / "subjects" / "trend_regression_stargazer_tables.html"
STARGAZER_SCRIPT = REPO_ROOT / "scripts" / "render_subject_regressions_stargazer.R"

SUBJECTS = [
    {
        "key": "economics",
        "label": "Economics",
        "group": "Economics",
        "event_path": REPORT_ROOT / "economics" / "event_time_summary.csv",
        "summary_path": REPORT_ROOT / "economics" / "summary.json",
        "color": "#1f77b4",
    },
    {
        "key": "ag_bio",
        "label": "Agricultural and Biological Sciences",
        "group": "Biology",
        "event_path": REPORT_ROOT
        / "subjects"
        / "agricultural_and_biological_sciences"
        / "hit_effects_counts_by_year"
        / "event_time_summary.csv",
        "summary_path": REPORT_ROOT
        / "subjects"
        / "agricultural_and_biological_sciences"
        / "hit_effects_counts_by_year"
        / "summary.json",
        "color": "#2ca02c",
    },
    {
        "key": "biochem",
        "label": "Biochemistry, Genetics, and Molecular Biology",
        "group": "Biology",
        "event_path": REPORT_ROOT
        / "subjects"
        / "biochemistry_genetics_and_molecular_biology"
        / "hit_effects_counts_by_year"
        / "event_time_summary.csv",
        "summary_path": REPORT_ROOT
        / "subjects"
        / "biochemistry_genetics_and_molecular_biology"
        / "hit_effects_counts_by_year"
        / "summary.json",
        "color": "#9467bd",
    },
    {
        "key": "physics",
        "label": "Physics and Astronomy",
        "group": "Physics",
        "event_path": REPORT_ROOT
        / "subjects"
        / "physics_and_astronomy"
        / "hit_effects_counts_by_year"
        / "event_time_summary.csv",
        "summary_path": REPORT_ROOT
        / "subjects"
        / "physics_and_astronomy"
        / "hit_effects_counts_by_year"
        / "summary.json",
        "color": "#d62728",
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return html.escape(str(value))


def pct(value: float) -> str:
    return f"{100 * value:.2f}%"


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for subject in SUBJECTS:
        for row in read_csv(subject["event_path"]):
            pairs = int(row["paper_author_hit_pairs"])
            observed = int(row["observed_pair_years"])
            event_time = int(row["event_time"])
            mean_zero = float(row["mean_citations_zero_missing"])
            mean_observed = row["mean_citations_observed_only"]
            rows.append(
                {
                    "subject": subject["key"],
                    "label": subject["label"],
                    "group": subject["group"],
                    "color": subject["color"],
                    "event_time": event_time,
                    "post": 1 if event_time >= 0 else 0,
                    "pairs": pairs,
                    "observed": observed,
                    "missing_rate": (pairs - observed) / pairs if pairs else 0.0,
                    "mean_zero": mean_zero,
                    "mean_observed": float(mean_observed) if mean_observed else None,
                }
            )
    return rows


def summary_rows(event_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    by_subject = {subject["key"]: subject for subject in SUBJECTS}
    for key, subject in by_subject.items():
        rows = [row for row in event_rows if row["subject"] == key]
        summary = read_summary(subject["summary_path"])
        simple = summary["simple_estimates"]
        total_pairs = sum(row["pairs"] for row in rows)
        total_observed = sum(row["observed"] for row in rows)
        output.append(
            {
                "Subject": subject["label"],
                "Group": subject["group"],
                "Works": summary["works"],
                "Hit events": summary["hit_events"],
                "Focal pairs": simple["paper_author_hit_pairs"],
                "Rows": simple["event_panel_rows"],
                "Mean pre": simple["mean_pre_annual_citations_zero_missing"],
                "Mean post": simple["mean_post_annual_citations_zero_missing"],
                "Added zero-filled": simple["mean_added_annual_citations_zero_missing"],
                "Added observed-only": simple["mean_added_annual_citations_observed_only"],
                "Missing rate": (total_pairs - total_observed) / total_pairs if total_pairs else 0.0,
            }
        )
    return output


def table(headers: list[str], rows: list[list[Any]], caption: str) -> str:
    out = [f"<table><caption>{html.escape(caption)}</caption><thead><tr>"]
    out.extend(f"<th>{html.escape(header)}</th>" for header in headers)
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        out.extend(f"<td>{cell}</td>" for cell in row)
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def scale(value: float, low: float, high: float, start: float, end: float) -> float:
    if high == low:
        return (start + end) / 2
    return start + (value - low) / (high - low) * (end - start)


def line_chart(
    event_rows: list[dict[str, Any]],
    *,
    value_key: str,
    caption: str,
    y_label: str,
    normalize: bool = False,
) -> str:
    width = 960
    height = 560
    margin_left = 86
    margin_right = 250
    margin_top = 54
    margin_bottom = 72
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    x_min = min(row["event_time"] for row in event_rows)
    x_max = max(row["event_time"] for row in event_rows)
    series = []
    for subject in SUBJECTS:
        rows = sorted(
            [row for row in event_rows if row["subject"] == subject["key"]],
            key=lambda item: item["event_time"],
        )
        if normalize:
            pre = [row[value_key] for row in rows if row["event_time"] < 0 and row[value_key] is not None]
            denom = sum(pre) / len(pre) if pre else 1.0
            values = [(row["event_time"], row[value_key] / denom if denom else 0.0) for row in rows]
        else:
            values = [(row["event_time"], row[value_key]) for row in rows]
        series.append((subject, [(x, y) for x, y in values if y is not None]))
    y_values = [y for _, values in series for _, y in values]
    y_min = min(0.0, min(y_values))
    y_max = max(y_values) * 1.08 if y_values else 1.0

    def xy(x_value: float, y_value: float) -> tuple[float, float]:
        x = scale(x_value, x_min, x_max, margin_left, margin_left + plot_w)
        y = scale(y_value, y_min, y_max, margin_top + plot_h, margin_top)
        return x, y

    zero_x, _ = xy(0, y_min)
    parts = [
        f'<figure><svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" stroke="#333"/>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#333"/>',
        f'<line x1="{zero_x:.1f}" y1="{margin_top}" x2="{zero_x:.1f}" y2="{margin_top + plot_h}" stroke="#777" stroke-dasharray="6 6"/>',
        f'<text x="{width / 2:.1f}" y="30" text-anchor="middle" font-size="20" font-family="Arial">{html.escape(caption)}</text>',
        f'<text x="{width / 2:.1f}" y="{height - 24}" text-anchor="middle" font-size="14" font-family="Arial">Event time</text>',
        f'<text x="24" y="{height / 2:.1f}" transform="rotate(-90 24 {height / 2:.1f})" text-anchor="middle" font-size="14" font-family="Arial">{html.escape(y_label)}</text>',
    ]
    for tick in [-10, -5, 0, 5, 10]:
        x, _ = xy(tick, y_min)
        parts.append(f'<line x1="{x:.1f}" y1="{margin_top + plot_h}" x2="{x:.1f}" y2="{margin_top + plot_h + 6}" stroke="#333"/>')
        parts.append(f'<text x="{x:.1f}" y="{margin_top + plot_h + 24}" text-anchor="middle" font-size="12" font-family="Arial">{tick}</text>')
    for i in range(5):
        value = y_min + (y_max - y_min) * i / 4
        _, y = xy(x_min, value)
        parts.append(f'<line x1="{margin_left - 6}" y1="{y:.1f}" x2="{margin_left}" y2="{y:.1f}" stroke="#333"/>')
        parts.append(f'<text x="{margin_left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" font-family="Arial">{value:.2f}</text>')
    for subject, values in series:
        points = " ".join(f"{xy(x, y)[0]:.1f},{xy(x, y)[1]:.1f}" for x, y in values)
        parts.append(f'<polyline fill="none" stroke="{subject["color"]}" stroke-width="3" points="{points}"/>')
    legend_x = margin_left + plot_w + 24
    for index, subject in enumerate(SUBJECTS):
        y = margin_top + 24 + 28 * index
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 32}" y2="{y}" stroke="{subject["color"]}" stroke-width="3"/>')
        parts.append(f'<text x="{legend_x + 42}" y="{y + 5}" font-size="13" font-family="Arial">{html.escape(subject["label"])}</text>')
    parts.extend(["</svg>", f"<figcaption>{html.escape(caption)}</figcaption></figure>"])
    return "".join(parts)


def render_stargazer_tables() -> str:
    subprocess.run(
        ["Rscript", str(STARGAZER_SCRIPT), str(REPO_ROOT), str(STARGAZER_OUTPUT)],
        check=True,
    )
    return STARGAZER_OUTPUT.read_text(encoding="utf-8")


def main() -> int:
    event_rows = load_rows()
    summaries = summary_rows(event_rows)
    summary_table = table(
        [
            "Subject",
            "Group",
            "Works",
            "Hit events",
            "Focal pairs",
            "Rows",
            "Mean pre",
            "Mean post",
            "Added zero-filled",
            "Added observed-only",
            "Missing rate",
        ],
        [
            [
                html.escape(row["Subject"]),
                html.escape(row["Group"]),
                fmt(row["Works"]),
                fmt(row["Hit events"]),
                fmt(row["Focal pairs"]),
                fmt(row["Rows"]),
                fmt(row["Mean pre"]),
                fmt(row["Mean post"]),
                fmt(row["Added zero-filled"]),
                fmt(row["Added observed-only"]),
                pct(row["Missing rate"]),
            ]
            for row in summaries
        ],
        "Summary statistics",
    )
    regression_tables = render_stargazer_tables()
    missing_table = table(
        ["Subject", "Mean missing rate", "Pre missing rate", "Post missing rate"],
        [
            [
                html.escape(subject["label"]),
                pct(sum(row["missing_rate"] for row in rows) / len(rows)),
                pct(sum(row["missing_rate"] for row in rows if row["event_time"] < 0) / 10),
                pct(sum(row["missing_rate"] for row in rows if row["event_time"] >= 0) / 11),
            ]
            for subject in SUBJECTS
            for rows in [[row for row in event_rows if row["subject"] == subject["key"]]]
        ],
        "Citation-year missingness",
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Subject Trend Regression Comparison</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #111; }}
figure {{ margin: 0 0 28px 0; }}
figcaption, caption {{ font-weight: 700; margin: 8px 0; text-align: left; }}
table {{ border-collapse: collapse; margin: 0 0 28px 0; font-size: 13px; }}
th, td {{ border: 1px solid #c8c8c8; padding: 6px 8px; text-align: right; vertical-align: top; }}
th:first-child, td:first-child, td:nth-child(2) {{ text-align: left; }}
thead th {{ background: #f2f2f2; }}
span {{ color: #555; }}
</style>
</head>
<body>
{line_chart(event_rows, value_key="mean_zero", caption="Zero-filled annual citation trends", y_label="Mean annual citations")}
{line_chart(event_rows, value_key="mean_zero", caption="Pre-period normalized annual citation trends", y_label="Index", normalize=True)}
{line_chart(event_rows, value_key="missing_rate", caption="Citation-year missingness trends", y_label="Missing rate")}
{summary_table}
{missing_table}
{regression_tables}
</body>
</html>
"""
    OUTPUT.write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
