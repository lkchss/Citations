#!/usr/bin/env python3
"""Build plain-language subject figures for the citation-spillover presentation."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports" / "8.7.26" / "economics_paper_level_normalized" / "normalized_event_time.csv"
OUTPUT = ROOT / "reports" / "8.7.26" / "economics_paper_level_normalized"


def draw(series: list[tuple[str, str, list[tuple[int, float]]]], path: Path, title: str, subtitle: str) -> None:
    width, height, left, right, top, bottom = 1020, 530, 90, 35, 78, 70
    values = [y for _, _, points in series for _, y in points]
    ymin, ymax = min(0, min(values)), max(values) * 1.12
    sx = lambda x: left + (x + 10) * (width - left - right) / 20
    sy = lambda y: height - bottom - (y - ymin) * (height - top - bottom) / (ymax - ymin)
    elements = [
        f"<rect width='{width}' height='{height}' fill='white'/>",
        f"<text x='{width/2}' y='28' text-anchor='middle' font-size='21' font-weight='700'>{title}</text>",
        f"<text x='{width/2}' y='49' text-anchor='middle' font-size='13' fill='#475467'>{subtitle}</text>",
    ]
    for fraction in (0, .25, .5, .75, 1):
        value = ymin + (ymax - ymin) * fraction
        elements.extend([
            f"<line x1='{left}' y1='{sy(value):.1f}' x2='{width-right}' y2='{sy(value):.1f}' stroke='#e4e7ec'/>",
            f"<text x='{left-9}' y='{sy(value)+4:.1f}' text-anchor='end' font-size='12'>{value:.2f}</text>",
        ])
    for event in range(-10, 11, 2):
        elements.append(f"<text x='{sx(event):.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='12'>{event:+d}</text>")
    elements.append(f"<line x1='{sx(0):.1f}' y1='{top}' x2='{sx(0):.1f}' y2='{height-bottom}' stroke='#b42318' stroke-dasharray='6 5'/>")
    for index, (label, color, points) in enumerate(series):
        polyline = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in points)
        legend_x = left + index * 330
        elements.extend([
            f"<polyline points='{polyline}' fill='none' stroke='{color}' stroke-width='3'/>",
            f"<line x1='{legend_x}' y1='66' x2='{legend_x+28}' y2='66' stroke='{color}' stroke-width='3'/>",
            f"<text x='{legend_x+36}' y='70' font-size='12'>{label}</text>",
        ])
    elements.extend([
        f"<text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>Years from candidate-hit publication</text>",
        f"<text transform='translate(19 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>Mean annual citations per older paper</text>",
    ])
    path.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1020 530' role='img'>"
        + "".join(elements)
        + "</svg>\n",
        encoding="utf-8",
    )


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open()))
    changing = [(int(r["event_time"]), float(r["mean_citations"])) for r in rows if r["sample_name"] == "at_risk"]
    fixed = [(int(r["event_time"]), float(r["mean_citations"])) for r in rows if r["sample_name"] == "balanced_full_window"]
    typical = [(int(r["event_time"]), float(r["mean_expected_citations"])) for r in rows if r["sample_name"] == "balanced_full_window"]
    draw(
        [("Papers available in each year", "#175cd3", changing), ("Same papers in every year", "#039855", fixed)],
        OUTPUT / "changing_vs_same_papers.svg",
        "The upward pattern disappears when the paper set is held fixed",
        "Observed citations; papers before publication are excluded",
    )
    draw(
        [("Authors' older papers", "#175cd3", fixed), ("Other economics papers at the same age", "#f79009", typical)],
        OUTPUT / "same_papers_vs_typical.svg",
        "Controlling for normal paper aging",
        "Comparison papers have the same exact age, calendar year, and document type",
    )


if __name__ == "__main__":
    main()
