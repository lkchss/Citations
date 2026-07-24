#!/usr/bin/env python3
"""Build a balanced full-subject event-time summary for unrelated citations."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--calculated-citations", type=Path, required=True)
    p.add_argument("--output-csv", type=Path, required=True)
    p.add_argument("--output-svg", type=Path, required=True)
    p.add_argument("--output-summary", type=Path, required=True)
    p.add_argument("--min-focal-year", type=int, default=1995)
    p.add_argument("--max-focal-year", type=int, default=2020)
    p.add_argument("--min-event", type=int, default=-5)
    p.add_argument("--max-event", type=int, default=5)
    p.add_argument("--memory-limit", default="12GB")
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--temp-directory", type=Path, required=True)
    return p.parse_args()


def write_svg(path: Path, rows: list[dict[str, float | int]], units: int) -> None:
    values = [float(row["mean_change_unrelated_citations"]) for row in rows]
    lo = min(values + [0.0])
    hi = max(values + [0.0])
    span = max(1.0, hi - lo)
    lo -= span * 0.12
    hi += span * 0.12
    x0, x1, y0, y1 = 90, 850, 95, 420

    def x(event: int) -> float:
        return x0 + (event - rows[0]["event_time"]) / max(1, rows[-1]["event_time"] - rows[0]["event_time"]) * (x1 - x0)

    def y(value: float) -> float:
        return y1 - (value - lo) / (hi - lo) * (y1 - y0)

    points = " ".join(f"{x(int(row['event_time'])):.1f},{y(float(row['mean_change_unrelated_citations'])):.1f}" for row in rows)
    x_labels = "".join(f'<text x="{x(int(row["event_time"])):.1f}" y="448" text-anchor="middle" class="axis">{int(row["event_time"])}</text>' for row in rows)
    y_ticks = ""
    for i in range(5):
        value = lo + (hi - lo) * i / 4
        yp = y(value)
        y_ticks += f'<line x1="{x0}" y1="{yp:.1f}" x2="{x1}" y2="{yp:.1f}" class="grid"/><text x="75" y="{yp + 4:.1f}" text-anchor="end" class="axis">{value:.2f}</text>'
    zero_y = y(0.0)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="520" viewBox="0 0 920 520" role="img" aria-labelledby="title desc">
  <title id="title">Full economics subject event study of unrelated citation changes</title>
  <desc id="desc">Mean change in accumulated citations to unrelated prior papers by event time relative to focal paper publication.</desc>
  <rect width="920" height="520" fill="#fff"/>
  <style>
    .title {{ font: 700 20px sans-serif; fill: #111827; }} .subtitle {{ font: 13px sans-serif; fill: #4b5563; }}
    .axis {{ font: 12px sans-serif; fill: #374151; }} .grid {{ stroke: #e5e7eb; stroke-width: 1; }}
    .zero {{ stroke: #6b7280; stroke-width: 1.5; stroke-dasharray: 5 4; }} .line {{ stroke: #1769aa; stroke-width: 3; fill: none; }}
  </style>
  <text x="40" y="34" class="title">Full economics subject event study</text>
  <text x="40" y="57" class="subtitle">Mean change in accumulated unrelated citations; t = 0 is focal-paper publication; balanced units = {units:,}</text>
  {y_ticks}
  <line x1="{x0}" y1="{zero_y:.1f}" x2="{x1}" y2="{zero_y:.1f}" class="zero"/>
  <line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#374151"/><line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#374151"/>
  <line x1="{x(0):.1f}" y1="{y0}" x2="{x(0):.1f}" y2="{y1}" stroke="#c2410c" stroke-width="1.5" stroke-dasharray="5 4"/>
  <polyline points="{points}" class="line"/>
  {''.join(f'<circle cx="{x(int(row["event_time"])):.1f}" cy="{y(float(row["mean_change_unrelated_citations"])):.1f}" r="4" fill="#1769aa"/>' for row in rows)}
  {x_labels}
  <text x="470" y="482" text-anchor="middle" class="subtitle">Event time relative to focal-paper publication</text>
  <text x="18" y="258" transform="rotate(-90 18 258)" text-anchor="middle" class="subtitle">Change in unrelated citations</text>
</svg>\n'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def main() -> int:
    parsed = parse_args()
    if parsed.min_event >= parsed.max_event or parsed.min_focal_year > parsed.max_focal_year:
        raise SystemExit("invalid event or focal-year range")
    import duckdb

    parsed.temp_directory.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(parsed.database), read_only=True)
    con.execute(f"SET memory_limit='{parsed.memory_limit}'")
    con.execute(f"SET threads={parsed.threads}")
    con.execute("SET temp_directory = ?", [str(parsed.temp_directory)])
    started = time.time()
    con.execute("""
      CREATE OR REPLACE TEMP TABLE eligible AS
      SELECT DISTINCT a.author_id, a.work_id, w.publication_year
      FROM subject_work_authors a
      JOIN subject_works w USING (subject, work_id)
      WHERE a.subject = 'economics_econometrics_and_finance'
        AND w.type IN ('article', 'review')
        AND w.publication_year BETWEEN 1990 AND 2020
    """)
    con.execute("""
      CREATE OR REPLACE TEMP TABLE focal AS
      SELECT e.author_id, e.work_id, e.publication_year
      FROM eligible e
      WHERE e.publication_year BETWEEN ? AND ?
        AND (SELECT count(DISTINCT p.work_id) FROM eligible p
             WHERE p.author_id = e.author_id
               AND p.publication_year < e.publication_year) >= 3
    """, [parsed.min_focal_year, parsed.max_focal_year])
    units = con.execute("SELECT count(*) FROM focal").fetchone()[0]
    con.execute("""
      CREATE OR REPLACE TEMP TABLE related_history AS
      SELECT DISTINCT f.author_id, f.work_id AS focal_work_id, h.work_id AS history_work_id
      FROM focal f
      JOIN eligible h ON h.author_id = f.author_id AND h.publication_year < f.publication_year
      JOIN subject_work_references r
        ON r.subject = 'economics_econometrics_and_finance'
       AND r.work_id = f.work_id AND r.referenced_work_id = h.work_id
      UNION
      SELECT DISTINCT f.author_id, f.work_id, h.work_id
      FROM focal f
      JOIN eligible h ON h.author_id = f.author_id AND h.publication_year < f.publication_year
      JOIN subject_work_references r
        ON r.subject = 'economics_econometrics_and_finance'
       AND r.work_id = h.work_id AND r.referenced_work_id = f.work_id
    """)
    con.execute("""
      CREATE OR REPLACE TEMP TABLE unrelated_history AS
      SELECT f.author_id, f.work_id AS focal_work_id, f.publication_year AS focal_year,
             h.work_id AS history_work_id, h.publication_year AS history_year
      FROM focal f
      JOIN eligible h ON h.author_id = f.author_id AND h.publication_year < f.publication_year
      LEFT JOIN related_history r
        ON r.author_id = f.author_id AND r.focal_work_id = f.work_id
       AND r.history_work_id = h.work_id
      WHERE r.history_work_id IS NULL
    """)
    con.execute("""
      CREATE OR REPLACE TEMP TABLE event_citations AS
      SELECT u.author_id, u.focal_work_id, u.focal_year, c.year AS citation_year,
             c.calculated_citations AS citations
      FROM unrelated_history u
      JOIN read_csv_auto(?, compression='gzip') c
        ON c.work_id = u.history_work_id
      WHERE c.year >= u.focal_year + ? - 1
        AND c.year <= u.focal_year + ? - 1
        AND c.year >= u.history_year
    """, [str(parsed.calculated_citations), parsed.min_event, parsed.max_event])
    sums = con.execute("""
      SELECT
        {columns}
      FROM event_citations
    """.format(columns=", ".join(
        f"sum(CASE WHEN citation_year < focal_year + {event} THEN citations ELSE 0 END) - "
        f"sum(CASE WHEN citation_year < focal_year - 1 THEN citations ELSE 0 END) AS e_{event + abs(parsed.min_event)}"
        for event in range(parsed.min_event, parsed.max_event + 1)
    ))).fetchone()
    rows = []
    for index, event in enumerate(range(parsed.min_event, parsed.max_event + 1)):
        total = float(sums[index] or 0)
        rows.append({"event_time": event, "mean_change_unrelated_citations": total / units if units else 0.0, "total_change": total, "balanced_units": units})
    parsed.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with parsed.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    write_svg(parsed.output_svg, rows, units)
    summary = {"subject": "economics_econometrics_and_finance", "balanced_units": units, "balanced_rows": units * len(rows), "event_min": parsed.min_event, "event_max": parsed.max_event, "min_focal_year": parsed.min_focal_year, "max_focal_year": parsed.max_focal_year, "citation_source": str(parsed.calculated_citations), "relatedness": "direct_reference_either_direction", "outcome": "change in accumulated unrelated citations relative to t=-1", "elapsed_seconds": time.time() - started, "csv": str(parsed.output_csv), "svg": str(parsed.output_svg), "rows": rows}
    parsed.output_summary.parent.mkdir(parents=True, exist_ok=True)
    parsed.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
