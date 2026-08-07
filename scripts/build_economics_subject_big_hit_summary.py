#!/usr/bin/env python3
"""Summarize the economics big-hit panel around hit publication year."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


def svg(rows: list[dict], path: Path) -> None:
    width, height, left, right, top, bottom = 980, 500, 85, 35, 65, 70
    values = [float(row["mean_change_from_t_minus_1"]) for row in rows]
    low, high = min(values + [0]), max(values + [0])
    margin = max((high-low)*.15, .05)
    low, high = low-margin, high+margin
    emin, emax = int(rows[0]["event_time"]), int(rows[-1]["event_time"])
    x = lambda e: left + (e-emin)*(width-left-right)/max(emax-emin, 1)
    y = lambda v: height-bottom-(v-low)*(height-top-bottom)/max(high-low, .01)
    points = " ".join(f"{x(int(r['event_time'])):.1f},{y(float(r['mean_change_from_t_minus_1'])):.1f}" for r in rows)
    ticks = []
    for row in rows:
        e = int(row["event_time"])
        ticks.append(f"<text x='{x(e):.1f}' y='{height-bottom+24}' text-anchor='middle' font-size='12'>{e}</text>")
    for frac in (0, .25, .5, .75, 1):
        value = low+(high-low)*frac
        ticks.append(f"<line x1='{left}' y1='{y(value):.1f}' x2='{width-right}' y2='{y(value):.1f}' stroke='#e5e7eb'/><text x='{left-10}' y='{y(value)+4:.1f}' text-anchor='end' font-size='12'>{value:.2f}</text>")
    circles = "".join(f"<circle cx='{x(int(r['event_time'])):.1f}' cy='{y(float(r['mean_change_from_t_minus_1'])):.1f}' r='4' fill='#175cd3'/>" for r in rows)
    content = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}'><rect width='100%' height='100%' fill='white'/><text x='{width/2}' y='28' text-anchor='middle' font-size='20' font-weight='bold'>Economics big-hit publication event</text><text x='{width/2}' y='49' text-anchor='middle' font-size='13' fill='#475467'>Mean annual citations to older unrelated papers, relative to t = -1</text>{''.join(ticks)}<line x1='{left}' y1='{y(0):.1f}' x2='{width-right}' y2='{y(0):.1f}' stroke='#667085' stroke-dasharray='5 4'/><line x1='{x(0):.1f}' y1='{top}' x2='{x(0):.1f}' y2='{height-bottom}' stroke='#b42318' stroke-dasharray='5 4'/><polyline points='{points}' fill='none' stroke='#175cd3' stroke-width='3'/>{circles}<text x='{width/2}' y='{height-18}' text-anchor='middle' font-size='14'>Years relative to hit publication</text><text transform='translate(18 {height/2}) rotate(-90)' text-anchor='middle' font-size='14'>Mean change in annual citations</text></svg>"""
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--temp-directory", type=Path, default=Path("/tmp/citations-subject-summary"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.temp_directory.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='6GB'")
    con.execute("SET temp_directory=?", [str(args.temp_directory)])
    con.execute("""
      CREATE TEMP TABLE panel AS
      SELECT DISTINCT author_id, focal_work_id, hit_work_id,
             try_cast(event_time AS INTEGER) event_time,
             try_cast(citations AS DOUBLE) citations
      FROM read_csv_auto(?, compression='gzip')
      WHERE try_cast(event_time AS INTEGER) BETWEEN -10 AND 10
    """, [str(args.panel)])
    counts = con.execute("""
      SELECT count(*), count(DISTINCT author_id), count(DISTINCT hit_work_id),
             count(DISTINCT author_id || '|' || hit_work_id),
             count(DISTINCT author_id || '|' || focal_work_id || '|' || hit_work_id)
      FROM panel
    """).fetchone()
    result = con.execute("""
      WITH baseline AS (
        SELECT author_id, focal_work_id, hit_work_id, citations baseline
        FROM panel WHERE event_time=-1
      )
      SELECT p.event_time, count(*) observations,
             count(DISTINCT p.author_id) authors,
             avg(p.citations) mean_citations,
             avg(p.citations-b.baseline) mean_change_from_t_minus_1,
             avg((p.citations>0)::INTEGER) share_with_positive_citations
      FROM panel p JOIN baseline b USING(author_id,focal_work_id,hit_work_id)
      GROUP BY p.event_time ORDER BY p.event_time
    """)
    columns = [item[0] for item in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    con.close()
    with (args.output_dir/"economics_big_hit_event_time.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    svg(rows, args.output_dir/"economics_big_hit_event_time.svg")
    pre = sum(float(r["mean_citations"]) for r in rows if -5 <= r["event_time"] <= -1)/5
    post = sum(float(r["mean_citations"]) for r in rows if 0 <= r["event_time"] <= 4)/5
    table = "\n".join(f"| {r['event_time']:+d} | {r['mean_citations']:.3f} | {r['mean_change_from_t_minus_1']:+.3f} | {r['share_with_positive_citations']:.1%} |" for r in rows)
    report = f"""# Economics subject-level big-hit summary

> **Descriptive, not causal.** Hits are author-specific papers with at least
> 101 lifetime citations and over 50% of the author's economics-portfolio
> citations. Treatment is hit publication year. Older papers are unrelated
> when the hit does not cite them. OpenAlex identity, version duplication, and
> economics-only denominators remain unresolved.

- Authors: **{counts[1]:,}**
- Author-hit events: **{counts[3]:,}**
- Focal pairs: **{counts[4]:,}**
- Mean citations, event -5:-1 versus 0:+4: **{pre:.3f} → {post:.3f}**

![Economics event-time figure](economics_big_hit_event_time.svg)

| Event time | Mean citations | Change from -1 | Positive share |
|---:|---:|---:|---:|
{table}
"""
    (args.output_dir/"economics_big_hit_subject_summary.md").write_text(report, encoding="utf-8")
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "panel": str(args.panel),
               "rows": counts[0], "authors": counts[1], "hit_works": counts[2],
               "author_hit_events": counts[3], "focal_pairs": counts[4],
               "pre_mean_event_minus_5_to_minus_1": pre,
               "post_mean_event_0_to_4": post,
               "difference": post-pre,
               "design": "descriptive publication-year event summary without controls",
               "caveats": ["economics-only author denominator", "OpenAlex identity errors",
                           "version duplication", "no counterfactual group"]}
    (args.output_dir/"economics_big_hit_subject_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
