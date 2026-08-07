#!/usr/bin/env python3
"""Build portable figures and machine-readable results from committed outputs.

This script deliberately needs only Python's standard library and the small
CSV files committed to the repository.  It can therefore run without access
to the external OpenAlex SSD.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def line_svg(
    path: Path,
    series: list[tuple[str, list[tuple[float, float]], str]],
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
    percent: bool = False,
) -> None:
    width, height, left, right, top, bottom = 1040, 570, 92, 42, 82, 78
    points = [point for _, values, _ in series for point in values]
    xmin, xmax = min(x for x, _ in points), max(x for x, _ in points)
    ymin, ymax = min(0, min(y for _, y in points)), max(y for _, y in points)
    margin = max((ymax - ymin) * .10, .02)
    ymin, ymax = ymin - margin, ymax + margin
    sx = lambda x: left + (x - xmin) * (width - left - right) / max(xmax - xmin, 1)
    sy = lambda y: height - bottom - (y - ymin) * (height - top - bottom) / max(ymax - ymin, .01)
    grid = []
    for fraction in (0, .25, .5, .75, 1):
        value = ymin + fraction * (ymax - ymin)
        label = f"{value:.0%}" if percent else f"{value:.2f}"
        grid.append(f"<line x1='{left}' y1='{sy(value):.1f}' x2='{width-right}' y2='{sy(value):.1f}' stroke='#e4e7ec'/><text x='{left-12}' y='{sy(value)+4:.1f}' text-anchor='end' font-size='12'>{label}</text>")
    for event in range(math.ceil(xmin), math.floor(xmax) + 1, 2):
        grid.append(f"<text x='{sx(event):.1f}' y='{height-bottom+25}' text-anchor='middle' font-size='12'>{event:+d}</text>")
    paths, legend = [], []
    for index, (name, values, color) in enumerate(series):
        polyline = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in values)
        paths.append(f"<polyline points='{polyline}' fill='none' stroke='{color}' stroke-width='3'/>")
        legend.append(f"<line x1='{left+index*260}' y1='61' x2='{left+28+index*260}' y2='61' stroke='{color}' stroke-width='3'/><text x='{left+36+index*260}' y='65' font-size='13'>{name}</text>")
    event_line = f"<line x1='{sx(0):.1f}' y1='{top}' x2='{sx(0):.1f}' y2='{height-bottom}' stroke='#b42318' stroke-dasharray='6 5'/><text x='{sx(0)+7:.1f}' y='{top+15}' fill='#b42318' font-size='12'>hit publication</text>"
    content = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' role='img'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='27' text-anchor='middle' font-size='21' font-weight='700'>{title}</text><text x='{width/2}' y='48' text-anchor='middle' font-size='13' fill='#475467'>{subtitle}</text>{''.join(legend)}{''.join(grid)}{event_line}{''.join(paths)}<line x1='{left}' y1='{height-bottom}' x2='{width-right}' y2='{height-bottom}' stroke='#344054'/><line x1='{left}' y1='{top}' x2='{left}' y2='{height-bottom}' stroke='#344054'/><text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>{x_label}</text><text transform='translate(22 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>{y_label}</text></svg>"""
    path.write_text(content, encoding="utf-8")


def bar_svg(path: Path, rows: list[dict], title: str) -> None:
    rows = rows[:15]
    width, height, left, right, top, bottom = 1100, 680, 485, 55, 70, 55
    max_abs = max(abs(float(row["change"])) for row in rows)
    zero = left + (width - left - right) / 2
    scale = (width - left - right) / 2 / max_abs
    bar_height = (height - top - bottom) / len(rows)
    items = []
    for index, row in enumerate(rows):
        value = float(row["change"])
        y = top + index * bar_height + 5
        x = zero if value >= 0 else zero + value * scale
        w = abs(value) * scale
        label = row["title"] if len(row["title"]) <= 62 else row["title"][:59] + "…"
        items.append(f"<text x='{left-10}' y='{y+bar_height*.55:.1f}' text-anchor='end' font-size='11'>{label}</text><rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{bar_height-9:.1f}' fill='{'#175cd3' if value >= 0 else '#b42318'}'/><text x='{zero+value*scale+(7 if value>=0 else -7):.1f}' y='{y+bar_height*.55:.1f}' text-anchor='{'start' if value>=0 else 'end'}' font-size='11'>{value:+.1f}</text>")
    content = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' role='img'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='28' text-anchor='middle' font-size='21' font-weight='700'>{title}</text><text x='{width/2}' y='49' text-anchor='middle' font-size='13' fill='#475467'>Change from 2002 to the 2007–09 annual average; top 15 by absolute change</text><line x1='{zero:.1f}' y1='{top}' x2='{zero:.1f}' y2='{height-bottom}' stroke='#667085'/>{''.join(items)}<text x='{width/2}' y='{height-17}' text-anchor='middle' font-size='14'>Change in annual citations</text></svg>"""
    path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=Path("reports/8.7.26"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/8.7.26/ingestion_ready"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    econ = read_csv(args.input_root / "economics_subject_level/economics_big_hit_event_time.csv")
    john_event = read_csv(args.input_root / "john_list_case_study/event_time.csv")
    contributions = read_csv(args.input_root / "john_list_case_study/paper_contributions.csv")

    econ_tidy = []
    for row in econ:
        for outcome, column in (("mean_annual_citations", "mean_citations"), ("change_from_t_minus_1", "mean_change_from_t_minus_1"), ("share_positive", "share_with_positive_citations")):
            econ_tidy.append({"analysis":"economics_big_hit", "unit":"author_focal_hit", "event_time":int(row["event_time"]), "outcome":outcome, "estimate":float(row[column]), "observations":int(row["observations"]), "authors":int(row["authors"]), "causal":0})
    write_csv(args.output_dir / "economics_event_time_tidy.csv", econ_tidy)

    fixed = [row for row in john_event if int(row["eligible_papers"]) == 49]
    john_tidy = [{"analysis":"john_list", "author_id":"https://openalex.org/A5083530241", "year":int(row["year"]), "event_time":int(row["event_time"]), "eligible_papers":int(row["eligible_papers"]), "total_citations":int(row["total_citations"]), "mean_citations":float(row["mean_citations"]), "median_citations":float(row["median_citations"]), "zero_share":float(row["zero_share"]), "causal":0} for row in fixed]
    write_csv(args.output_dir / "john_list_fixed_cohort_tidy.csv", john_tidy)

    line_svg(args.output_dir / "economics_event_levels_and_change.svg", [
        ("Citation level", [(float(r["event_time"]), float(r["mean_citations"])) for r in econ], "#175cd3"),
        ("Change from t=-1", [(float(r["event_time"]), float(r["mean_change_from_t_minus_1"])) for r in econ], "#f79009"),
    ], "Economics: citations to older unrelated papers", "Focal-paper weighted descriptive means; economics-only hit definition", "Years relative to hit publication", "Annual citations")
    line_svg(args.output_dir / "economics_positive_citation_share.svg", [
        ("Positive-citation share", [(float(r["event_time"]), float(r["share_with_positive_citations"])) for r in econ], "#039855"),
    ], "Economics: share of focal papers cited", "Share receiving at least one citation in each event year", "Years relative to hit publication", "Share with positive citations", percent=True)
    line_svg(args.output_dir / "john_list_fixed_cohort_mean.svg", [
        ("Mean citations", [(float(r["event_time"]), float(r["mean_citations"])) for r in fixed], "#175cd3"),
    ], "John List: fixed cohort of 49 prior papers", "Mean annual citations; papers not cited by the 2003 candidate hit", "Years relative to 2003", "Mean annual citations")
    line_svg(args.output_dir / "john_list_fixed_cohort_positive_share.svg", [
        ("Positive-citation share", [(float(r["event_time"]), 1-float(r["zero_share"])) for r in fixed], "#039855"),
    ], "John List: breadth of citation activity", "Share of the fixed 49-paper cohort receiving at least one citation", "Years relative to 2003", "Share with positive citations", percent=True)
    ranked = sorted(contributions, key=lambda row: abs(float(row["change"])), reverse=True)
    bar_svg(args.output_dir / "john_list_paper_change_concentration.svg", ranked, "John List: paper-level citation changes are concentrated")

    pre = sum(float(r["mean_citations"]) for r in econ if -5 <= int(r["event_time"]) <= -1) / 5
    post = sum(float(r["mean_citations"]) for r in econ if 0 <= int(r["event_time"]) <= 4) / 5
    summary_rows = [
        {"analysis":"economics_big_hit", "metric":"authors", "value":11155, "window":"all", "interpretation":"distinct OpenAlex author entities"},
        {"analysis":"economics_big_hit", "metric":"focal_pairs", "value":75882, "window":"all", "interpretation":"deduplicated author-focal-hit units"},
        {"analysis":"economics_big_hit", "metric":"pre_mean", "value":pre, "window":"event_time_-5_to_-1", "interpretation":"mean annual focal-paper citations"},
        {"analysis":"economics_big_hit", "metric":"post_mean", "value":post, "window":"event_time_0_to_4", "interpretation":"mean annual focal-paper citations"},
        {"analysis":"economics_big_hit", "metric":"raw_pre_post_difference", "value":post-pre, "window":"post_minus_pre", "interpretation":"descriptive; not causal"},
        {"analysis":"john_list", "metric":"local_economics_work_citations", "value":11977, "window":"current_snapshot", "interpretation":"economics-only work total"},
        {"analysis":"john_list", "metric":"reconstructed_economics_citations", "value":12030, "window":"available_reference_years", "interpretation":"annual citations reconstructed from local references"},
        {"analysis":"john_list", "metric":"openalex_author_object_citations", "value":46684, "window":"live_2026-08-07", "interpretation":"all-field author-entity diagnostic; identity contamination suspected"},
    ]
    write_csv(args.output_dir / "headline_results.csv", summary_rows)
    with (args.output_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for record_type, records in (("headline", summary_rows), ("economics_event_time", econ_tidy), ("john_list_event_time", john_tidy)):
            for record in records:
                handle.write(json.dumps({"record_type":record_type, **record}, sort_keys=True) + "\n")
    data_dictionary = {
        "headline_results.csv":{"primary_key":["analysis","metric","window"], "description":"Key counts, descriptive estimates, and citation reconciliation values"},
        "economics_event_time_tidy.csv":{"primary_key":["analysis","event_time","outcome"], "unit":"author-focal-paper-hit-year, aggregated with equal unit weight", "description":"Economics publication-event outcomes"},
        "john_list_fixed_cohort_tidy.csv":{"primary_key":["author_id","year"], "unit":"fixed cohort of 49 prior papers, aggregated by year", "description":"John List exploratory time series"},
        "results.jsonl":{"description":"Union of all three result tables with record_type discriminator"},
        "common_fields":{"causal":"Always 0 for this exploratory package", "event_time":"Calendar year minus candidate-hit publication year", "estimate":"Reported descriptive value in the units named by outcome"},
    }
    (args.output_dir / "data_dictionary.json").write_text(json.dumps(data_dictionary, indent=2) + "\n", encoding="utf-8")

    readme_path = args.output_dir / "README.md"
    readme_path.write_text("""# Ingestion-ready exploratory results

This directory is generated entirely from small, committed CSV outputs and does
not require the external SSD. `headline_results.csv` contains one row per key
result; the two `*_tidy.csv` files contain long-form event-time data;
`results.jsonl` combines them for direct ingestion. SVG files are portable
figures. `data_dictionary.json` documents table grain and keys, while
`manifest.json` records definitions, warnings, hashes, and provenance.

All estimates are descriptive. Do not label the pre/post difference as a causal
effect. The current hit definition uses an economics-only portfolio denominator,
not an author's complete OpenAlex career citation total.
""", encoding="utf-8")
    generated = sorted(path for path in args.output_dir.iterdir() if path.is_file() and path.name != "manifest.json")
    manifest = {
        "schema_version":"1.0.0", "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"exploratory_descriptive", "causal_claim":False,
        "source_scope":"committed aggregate outputs; no external SSD required",
        "definitions":{"hit":"paper with >50% of an author's economics-portfolio citations and at least 101 citations", "unrelated":"older focal paper absent from hit paper references", "treatment_time":"hit publication year"},
        "warnings":["economics-only treatment denominator", "OpenAlex author identity contamination", "work-version duplication", "strong pre-event trend", "no counterfactual group"],
        "files":[{"name":path.name, "bytes":path.stat().st_size, "sha256":sha256(path)} for path in generated],
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir":str(args.output_dir), "files":len(list(args.output_dir.iterdir())), "pre":pre, "post":post, "difference":post-pre}, indent=2))


if __name__ == "__main__":
    main()
