#!/usr/bin/env python3
"""Build a presentation figure contrasting hit concentration and citation change."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "8.7.26" / "author_hit_profiles"


def main() -> None:
    profiles = {
        row["requested_name"]: row
        for row in csv.DictReader((OUTPUT / "author_hit_profiles.csv").open())
    }
    matched = {
        row["author_name"]: row
        for row in csv.DictReader(
            (ROOT / "reports" / "8.7.26" / "author_matched_controls" / "matched_control_summary.csv").open()
        )
    }
    rows = [
        {
            "author": "John List",
            "economics_hit_share": 0.10136094180512649,
            "all_field_hit_share": "",
            "raw_change": float(matched["John A. List"]["focal_change"]),
            "pretrend": "fails",
            "case_type": "gradual prominence",
        }
    ]
    for name in ("Michael C. Jensen", "Manuel Arellano", "Robert M. Solow"):
        profile = profiles[name]
        rows.append(
            {
                "author": name.replace(" C.", "").replace(" M.", ""),
                "economics_hit_share": float(profile["local_economics_hit_share"]),
                "all_field_hit_share": float(profile["live_all_field_hit_share"]),
                "raw_change": float(profile["raw_difference"]),
                "pretrend": "fails" if name == "Michael C. Jensen" else "passes loose screen",
                "case_type": "candidate single hit",
            }
        )

    csv_path = OUTPUT / "author_prominence_contrast.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    width, height = 1080, 540
    left, right, top, bottom = 210, 55, 82, 66
    panel_gap = 92
    panel_width = (width - left - right - panel_gap) / 2
    names = [row["author"] for row in rows]
    colors = ["#6941c6", "#175cd3", "#039855", "#f79009"]
    bar_height = 42
    y_positions = [top + 28 + i * 92 for i in range(len(rows))]
    share_x = lambda value: left + value / 0.75 * panel_width
    change_left = left + panel_width + panel_gap
    change_x = lambda value: change_left + value / 6.0 * panel_width

    elements = [
        f"<rect width='{width}' height='{height}' fill='white'/>",
        f"<text x='{width/2}' y='28' text-anchor='middle' font-size='22' font-weight='700'>Different paths to prominence, different citation patterns</text>",
        f"<text x='{width/2}' y='50' text-anchor='middle' font-size='13' fill='#475467'>Economics-portfolio hit concentration and raw change in older-paper annual citations</text>",
        f"<text x='{left + panel_width/2}' y='76' text-anchor='middle' font-size='14' font-weight='700'>Largest-paper share</text>",
        f"<text x='{change_left + panel_width/2}' y='76' text-anchor='middle' font-size='14' font-weight='700'>Post-minus-pre change</text>",
    ]
    for value in (0, 0.25, 0.5, 0.75):
        x = share_x(value)
        elements.append(f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{height-bottom}' stroke='#eaecf0'/>")
        elements.append(f"<text x='{x:.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='12'>{value:.0%}</text>")
    for value in (0, 2, 4, 6):
        x = change_x(value)
        elements.append(f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{height-bottom}' stroke='#eaecf0'/>")
        elements.append(f"<text x='{x:.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='12'>+{value:.0f}</text>")
    elements.append(f"<line x1='{share_x(.5):.1f}' y1='{top}' x2='{share_x(.5):.1f}' y2='{height-bottom}' stroke='#b42318' stroke-width='2' stroke-dasharray='6 5'/>")
    for row, name, color, y in zip(rows, names, colors, y_positions):
        share = row["economics_hit_share"]
        change = row["raw_change"]
        elements.extend(
            [
                f"<text x='{left-14}' y='{y+27}' text-anchor='end' font-size='14'>{name}</text>",
                f"<rect x='{left}' y='{y}' width='{share_x(share)-left:.1f}' height='{bar_height}' rx='3' fill='{color}'/>",
                f"<text x='{share_x(share)+7:.1f}' y='{y+27}' font-size='13'>{share:.1%}</text>",
                f"<rect x='{change_left}' y='{y}' width='{change_x(change)-change_left:.1f}' height='{bar_height}' rx='3' fill='{color}'/>",
                f"<text x='{change_x(change)+7:.1f}' y='{y+27}' font-size='13'>+{change:.2f}</text>",
            ]
        )
    elements.append(f"<text x='{width/2}' y='{height-14}' text-anchor='middle' font-size='12' fill='#475467'>Descriptive comparison; event definitions differ for gradual-prominence List and candidate-hit authors</text>")
    (OUTPUT / "author_prominence_contrast.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1080 540' role='img'>"
        + "".join(elements)
        + "</svg>\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
