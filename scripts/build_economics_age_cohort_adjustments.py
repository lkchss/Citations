#!/usr/bin/env python3
"""Build aggregate age/risk-set adjustments from committed economics cells."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def line_svg(path: Path, series: list[tuple[str, list[tuple[int, float]], str]], title: str, subtitle: str) -> None:
    width, height, left, right, top, bottom = 1020, 530, 85, 35, 85, 70
    points = [p for _, values, _ in series for p in values]
    xmin, xmax = min(x for x, _ in points), max(x for x, _ in points)
    ymax = max(y for _, y in points) * 1.12
    sx = lambda x: left+(x-xmin)*(width-left-right)/(xmax-xmin)
    sy = lambda y: height-bottom-y*(height-top-bottom)/ymax
    grid=[]
    for fraction in (0,.25,.5,.75,1):
        value=ymax*fraction; grid.append(f"<line x1='{left}' y1='{sy(value):.1f}' x2='{width-right}' y2='{sy(value):.1f}' stroke='#e4e7ec'/><text x='{left-9}' y='{sy(value)+4:.1f}' text-anchor='end' font-size='12'>{value:.2f}</text>")
    for event in range(xmin,xmax+1): grid.append(f"<text x='{sx(event):.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='11'>{event:+d}</text>")
    paths=[]; legends=[]
    for i,(name,values,color) in enumerate(series):
        poly=" ".join(f"{sx(x):.1f},{sy(y):.1f}" for x,y in values)
        paths.append(f"<polyline points='{poly}' fill='none' stroke='{color}' stroke-width='3'/>")
        legends.append(f"<line x1='{left+i*300}' y1='66' x2='{left+28+i*300}' y2='66' stroke='{color}' stroke-width='3'/><text x='{left+36+i*300}' y='70' font-size='12'>{name}</text>")
    path.write_text(f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='27' text-anchor='middle' font-size='21' font-weight='700'>{title}</text><text x='{width/2}' y='48' text-anchor='middle' font-size='13' fill='#475467'>{subtitle}</text>{''.join(legends)}{''.join(grid)}<line x1='{sx(0)}' y1='{top}' x2='{sx(0)}' y2='{height-bottom}' stroke='#b42318' stroke-dasharray='6 5'/>{''.join(paths)}<text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>Event time</text><text transform='translate(18 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>Mean annual citations</text></svg>""",encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--cells-dir",type=Path,default=Path("reports/economics/econometrics_summaries"))
    parser.add_argument("--output-dir",type=Path,default=Path("reports/8.7.26/economics_adjusted"))
    args=parser.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    age=read(args.cells_dir/"focal_age_bin_event_time_cells.csv")
    raw=read(args.cells_dir/"event_time_cells.csv")

    by_event=defaultdict(list)
    for row in age: by_event[int(row["event_time"])].append(row)
    at_risk=[]
    for event,cells in sorted(by_event.items()):
        valid=[r for r in cells if r["focal_age_bin"]!="pre-publication"]
        n=sum(int(r["rows"]) for r in valid)
        mean=sum(int(r["rows"])*float(r["mean_citations_zero_missing"]) for r in valid)/n
        excluded=sum(int(r["rows"]) for r in cells if r["focal_age_bin"]=="pre-publication")
        at_risk.append({"event_time":event,"at_risk_rows":n,"prepublication_rows_excluded":excluded,"prepublication_share_original":excluded/(n+excluded),"mean_citations_at_risk":mean})

    mature_bins={"3-5","6-10","11-20","21+"}
    baseline={r["focal_age_bin"]:int(r["rows"]) for r in by_event[-1] if r["focal_age_bin"] in mature_bins}
    total=sum(baseline.values()); weights={key:value/total for key,value in baseline.items()}
    standardized=[]
    for event in range(-5,5):
        cells={r["focal_age_bin"]:r for r in by_event[event]}
        value=sum(weights[key]*float(cells[key]["mean_citations_zero_missing"]) for key in weights)
        standardized.append({"event_time":event,"mean_citations_age_standardized":value,**{f"weight_{key}":weights[key] for key in sorted(weights)}})
    write(args.output_dir/"at_risk_event_time.csv",at_risk)
    write(args.output_dir/"mature_age_standardized_event_time.csv",standardized)

    raw_points=[(int(r["event_time"]),float(r["mean_citations_zero_missing"])) for r in raw]
    risk_points=[(r["event_time"],r["mean_citations_at_risk"]) for r in at_risk]
    line_svg(args.output_dir/"raw_vs_at_risk.svg",[("Original row-balanced mean",raw_points,"#667085"),("At-risk; pre-publication excluded",risk_points,"#175cd3")],"Economics: remove pre-publication pseudo-observations","Aggregate correction using committed focal-age cells")
    line_svg(args.output_dir/"mature_age_standardized.svg",[("Age-standardized, focal age 3+",[(r["event_time"],r["mean_citations_age_standardized"]) for r in standardized],"#039855")],"Economics: mature-paper age standardization","Fixed t=-1 age-bin weights; common support from event -5 through +4")
    pre=sum(r["mean_citations_age_standardized"] for r in standardized if -5<=r["event_time"]<=-1)/5
    post=sum(r["mean_citations_age_standardized"] for r in standardized if 0<=r["event_time"]<=4)/5
    summary={"status":"descriptive_aggregate_adjustment","pre_mean":pre,"post_mean":post,"raw_difference":post-pre,"age_bins":sorted(weights),"weights":weights,"warning":"Cell reweighting is not a paper-level regression or matched-control design."}
    (args.output_dir/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    (args.output_dir/"README.md").write_text(f"""# Economics age and risk-set adjustments

These outputs use committed aggregate cells and do not require the external SSD.

The first adjustment excludes observations before focal-paper publication. The
second standardizes mature focal papers (ages 3–5, 6–10, 11–20, and 21+) to the
age-bin distribution observed at event time -1 over the common -5:+4 window.

The standardized pre/post means are **{pre:.3f}** and **{post:.3f}**, a raw
difference of **{post-pre:+.3f}**. This remains descriptive cell reweighting,
not a paper-level controlled regression or causal estimate.

![Raw versus at-risk series](raw_vs_at_risk.svg)

![Mature-paper age-standardized series](mature_age_standardized.svg)
""")
    print(json.dumps(summary,indent=2))


if __name__=="__main__": main()
