#!/usr/bin/env python3
"""Build a balanced descriptive event study around hit-threshold crossing."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hit-events", type=Path, required=True)
    parser.add_argument("--existing-panel", type=Path, required=True)
    parser.add_argument("--calculated-citations", type=Path, required=True)
    parser.add_argument("--output-panel", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-svg", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=101)
    parser.add_argument("--event-min", type=int, default=-5)
    parser.add_argument("--event-max", type=int, default=5)
    parser.add_argument("--min-year", type=int, default=1990)
    parser.add_argument("--max-year", type=int, default=2025)
    parser.add_argument("--memory-limit", default="12GB")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--temp-directory", type=Path, required=True)
    return parser.parse_args()


def write_svg(path: Path, rows: list[dict[str, float | int]], pairs: int) -> None:
    values = [
        float(row["mean_change_from_t_minus_1"])
        for row in rows
    ]
    lows = [float(row["ci_low"]) for row in rows]
    highs = [float(row["ci_high"]) for row in rows]
    y_min = min(lows + [0.0])
    y_max = max(highs + [0.0])
    span = max(0.1, y_max - y_min)
    y_min -= span * 0.12
    y_max += span * 0.12
    x0, x1, y0, y1 = 90, 860, 95, 410

    def x(event: int) -> float:
        return x0 + (event - int(rows[0]["event_time"])) / (
            int(rows[-1]["event_time"]) - int(rows[0]["event_time"])
        ) * (x1 - x0)

    def y(value: float) -> float:
        return y1 - (value - y_min) / (y_max - y_min) * (y1 - y0)

    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="930" height="500" viewBox="0 0 930 500" role="img">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>.title{font:700 20px sans-serif;fill:#111827}.note{font:13px sans-serif;fill:#4b5563}.axis{font:12px sans-serif;fill:#374151}.grid{stroke:#e5e7eb}.zero{stroke:#6b7280;stroke-dasharray:4 4}.treatment{stroke:#c2410c;stroke-dasharray:5 4}.series{stroke:#1769aa;stroke-width:3;fill:none}.ci{stroke:#1769aa;stroke-width:1.5}</style>',
        '<text x="38" y="34" class="title">Citations to unrelated papers around a hit</text>',
        f'<text x="38" y="57" class="note">t = 0 is the first year the hit reaches 101 cumulative citations; balanced focal pairs = {pairs:,}</text>',
    ]
    for index in range(5):
        value = y_min + (y_max - y_min) * index / 4
        yp = y(value)
        elements.append(f'<line x1="{x0}" y1="{yp:.1f}" x2="{x1}" y2="{yp:.1f}" class="grid"/>')
        elements.append(f'<text x="76" y="{yp + 4:.1f}" text-anchor="end" class="axis">{value:.3f}</text>')
    elements.append(f'<line x1="{x0}" y1="{y(0):.1f}" x2="{x1}" y2="{y(0):.1f}" class="zero"/>')
    elements.append(f'<line x1="{x(0):.1f}" y1="{y0}" x2="{x(0):.1f}" y2="{y1}" class="treatment"/>')
    points = []
    for row in rows:
        event = int(row["event_time"])
        mean = float(row["mean_change_from_t_minus_1"])
        xp = x(event)
        points.append(f"{xp:.1f},{y(mean):.1f}")
        elements.append(f'<line x1="{xp:.1f}" y1="{y(float(row["ci_low"])):.1f}" x2="{xp:.1f}" y2="{y(float(row["ci_high"])):.1f}" class="ci"/>')
        elements.append(f'<circle cx="{xp:.1f}" cy="{y(mean):.1f}" r="4" fill="#1769aa"/>')
        elements.append(f'<text x="{xp:.1f}" y="438" text-anchor="middle" class="axis">{event}</text>')
    elements.append(f'<polyline points="{" ".join(points)}" class="series"/>')
    elements.append('<text x="475" y="472" text-anchor="middle" class="note">Event time relative to hit-threshold crossing</text>')
    elements.append('<text x="18" y="255" transform="rotate(-90 18 255)" text-anchor="middle" class="note">Change in annual unrelated-paper citations from t = -1</text>')
    elements.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.event_min >= -1 or args.event_max < 0:
        raise SystemExit("event window must include pre-treatment years, -1, and 0")
    import duckdb

    args.temp_directory.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{args.memory_limit}'")
    con.execute(f"SET threads={args.threads}")
    con.execute("SET temp_directory=?", [str(args.temp_directory)])
    con.execute(
        """
        CREATE TEMP TABLE annual_citations AS
        SELECT trim(work_id) AS work_id,
               try_cast(year AS INTEGER) AS year,
               try_cast(calculated_citations AS BIGINT) AS citations
        FROM read_csv_auto(?, compression='gzip')
        WHERE work_id IS NOT NULL AND year IS NOT NULL
        """,
        [str(args.calculated_citations)],
    )
    con.execute(
        """
        CREATE TEMP TABLE hit_crossings AS
        WITH hit_ids AS (
          SELECT DISTINCT hit_work_id
          FROM read_csv_auto(?, compression='gzip')
        ), cumulative AS (
          SELECT c.work_id, c.year,
                 sum(c.citations) OVER (
                   PARTITION BY c.work_id ORDER BY c.year
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                 ) AS cumulative_citations
          FROM annual_citations c
          JOIN hit_ids h ON h.hit_work_id = c.work_id
        )
        SELECT work_id AS hit_work_id, min(year) AS crossing_year
        FROM cumulative
        WHERE cumulative_citations >= ?
        GROUP BY work_id
        """,
        [str(args.hit_events), args.threshold],
    )
    con.execute(
        """
        CREATE TEMP TABLE focal_pairs AS
        SELECT DISTINCT author_id, focal_work_id, hit_work_id,
               try_cast(focal_publication_year AS INTEGER) AS focal_publication_year
        FROM read_csv_auto(?, compression='gzip')
        """,
        [str(args.existing_panel)],
    )
    con.execute(
        """
        CREATE TEMP TABLE balanced_panel AS
        WITH eligible AS (
          SELECT p.*, c.crossing_year
          FROM focal_pairs p
          JOIN hit_crossings c USING (hit_work_id)
          WHERE c.crossing_year + ? >= ?
            AND c.crossing_year + ? <= ?
            AND p.focal_publication_year < c.crossing_year
        ), event_times AS (
          SELECT unnest(range(?, ? + 1))::INTEGER AS event_time
        )
        SELECT e.author_id, e.focal_work_id, e.hit_work_id,
               e.focal_publication_year, e.crossing_year,
               t.event_time, e.crossing_year + t.event_time AS year,
               coalesce(c.citations, 0)::BIGINT AS citations
        FROM eligible e
        CROSS JOIN event_times t
        LEFT JOIN annual_citations c
          ON c.work_id = e.focal_work_id
         AND c.year = e.crossing_year + t.event_time
        """,
        [
            args.event_min,
            args.min_year,
            args.event_max,
            args.max_year,
            args.event_min,
            args.event_max,
        ],
    )
    counts = con.execute(
        """
        SELECT count(*) AS rows,
               count(DISTINCT author_id || '|' || focal_work_id || '|' || hit_work_id) AS pairs,
               count(DISTINCT author_id || '|' || hit_work_id) AS hit_author_events,
               count(DISTINCT author_id) AS authors,
               count(DISTINCT hit_work_id) AS hit_works
        FROM balanced_panel
        """
    ).fetchone()
    expected_rows = counts[1] * (args.event_max - args.event_min + 1)
    if counts[0] != expected_rows:
        raise RuntimeError(f"event panel is not balanced: rows={counts[0]} expected={expected_rows}")

    args.output_panel.parent.mkdir(parents=True, exist_ok=True)
    query = con.execute(
        """
        SELECT author_id, focal_work_id, hit_work_id, focal_publication_year,
               crossing_year, event_time, year, citations
        FROM balanced_panel
        ORDER BY author_id, hit_work_id, focal_work_id, event_time
        """
    )
    with gzip.open(args.output_panel, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "author_id",
                "focal_work_id",
                "hit_work_id",
                "focal_publication_year",
                "crossing_year",
                "event_time",
                "year",
                "citations",
            ]
        )
        while batch := query.fetchmany(50_000):
            writer.writerows(batch)

    summary_rows = con.execute(
        """
        WITH baseline AS (
          SELECT author_id, focal_work_id, hit_work_id, citations AS baseline_citations
          FROM balanced_panel
          WHERE event_time = -1
        ), deltas AS (
          SELECT p.author_id, p.event_time, p.citations,
                 p.citations - b.baseline_citations AS delta
          FROM balanced_panel p
          JOIN baseline b USING (author_id, focal_work_id, hit_work_id)
        ), means AS (
          SELECT event_time, count(*) AS observations,
                 avg(citations) AS mean_citations,
                 avg(delta) AS mean_delta
          FROM deltas
          GROUP BY event_time
        ), clusters AS (
          SELECT d.event_time, d.author_id, count(*) AS cluster_n,
                 sum(d.delta) AS cluster_sum
          FROM deltas d
          GROUP BY d.event_time, d.author_id
        ), variances AS (
          SELECT c.event_time, count(*) AS clusters,
                 sum(power(c.cluster_sum - m.mean_delta * c.cluster_n, 2))
                   AS score_squared
          FROM clusters c
          JOIN means m USING (event_time)
          GROUP BY c.event_time
        )
        SELECT m.event_time, m.observations, v.clusters, m.mean_citations,
               m.mean_delta,
               sqrt(
                 (v.clusters::DOUBLE / greatest(1, v.clusters - 1))
                 * v.score_squared / power(m.observations, 2)
               ) AS clustered_se
        FROM means m
        JOIN variances v USING (event_time)
        ORDER BY m.event_time
        """
    ).fetchall()
    rows = []
    for event_time, observations, clusters, mean_citations, mean_delta, se in summary_rows:
        rows.append(
            {
                "event_time": int(event_time),
                "observations": int(observations),
                "author_clusters": int(clusters),
                "mean_citations": float(mean_citations),
                "mean_change_from_t_minus_1": float(mean_delta),
                "clustered_se": float(se or 0),
                "ci_low": float(mean_delta - 1.96 * (se or 0)),
                "ci_high": float(mean_delta + 1.96 * (se or 0)),
            }
        )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    write_svg(args.output_svg, rows, int(counts[1]))
    result = {
        "design": "balanced descriptive event study; no control group and no DiD",
        "hit_definition": {
            "candidate_sample": "existing hit events: >=101 lifetime citations and >=50% author citation share",
            "event_year": f"first reconstructed-citation year cumulative hit citations reach {args.threshold}",
        },
        "outcome": "annual citations to pre-existing papers not referenced by the hit",
        "normalization": "pair-level change from event_time=-1",
        "event_min": args.event_min,
        "event_max": args.event_max,
        "min_calendar_year": args.min_year,
        "max_calendar_year": args.max_year,
        "rows": int(counts[0]),
        "pairs": int(counts[1]),
        "hit_author_events": int(counts[2]),
        "authors": int(counts[3]),
        "hit_works": int(counts[4]),
        "event_results": rows,
        "outputs": {
            "panel": str(args.output_panel),
            "csv": str(args.output_csv),
            "svg": str(args.output_svg),
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
