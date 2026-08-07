#!/usr/bin/env python3
"""Screen the economics DuckDB for author-specific, citation-concentrated hits."""

from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


QUERY = r"""
WITH base AS (
  SELECT a.author_id, a.author_name, a.author_position, w.work_id, w.title,
         w.publication_year, w.type, coalesce(w.cited_by_count, 0) AS citations,
         w.subfield_name, w.topic_name
  FROM subject_work_authors a
  JOIN subject_works w USING (subject, work_id)
  WHERE a.subject = 'economics_econometrics_and_finance'
    AND w.type IN ('article', 'preprint', 'review')
    AND w.publication_year IS NOT NULL
),
ranked AS (
  SELECT *, row_number() OVER (
    PARTITION BY author_id ORDER BY citations DESC, publication_year, work_id
  ) AS citation_rank
  FROM base
),
summary AS (
  SELECT author_id, arg_max(author_name, citations) AS author_name,
         count(*) AS economics_portfolio_works,
         sum(citations) AS economics_portfolio_citations
  FROM base GROUP BY author_id
),
work_author_counts AS (
  SELECT work_id, count(DISTINCT author_id) AS hit_author_count FROM base GROUP BY work_id
),
top_work AS (
  SELECT r.* EXCLUDE (citation_rank), c.hit_author_count
  FROM ranked r JOIN work_author_counts c USING (work_id)
  WHERE citation_rank = 1
),
candidates AS (
  SELECT s.author_id, s.author_name, t.work_id AS hit_work_id,
         t.title AS hit_title, t.publication_year AS hit_publication_year,
         t.type AS hit_type, t.citations AS hit_cited_by_count,
         s.economics_portfolio_citations, s.economics_portfolio_works,
         t.citations::DOUBLE / nullif(s.economics_portfolio_citations, 0) AS hit_share,
         t.author_position AS author_position_on_hit,
         t.subfield_name, t.topic_name, t.hit_author_count
  FROM summary s JOIN top_work t USING (author_id)
  WHERE s.economics_portfolio_citations >= ?
    AND t.citations::DOUBLE / nullif(s.economics_portfolio_citations, 0) > ?
),
history AS (
  SELECT c.*,
         count(*) FILTER (WHERE b.publication_year < c.hit_publication_year) AS prior_works,
         count(*) FILTER (WHERE b.publication_year < c.hit_publication_year AND b.citations > 0) AS prior_cited_works,
         sum(b.citations) FILTER (WHERE b.publication_year < c.hit_publication_year) AS prior_citations
  FROM candidates c JOIN base b USING (author_id)
  GROUP BY ALL
)
SELECT * FROM history WHERE prior_works >= ?
ORDER BY economics_portfolio_citations DESC, hit_share DESC
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-author-citations", type=int, default=100)
    parser.add_argument("--minimum-hit-share", type=float, default=.5)
    parser.add_argument("--minimum-prior-works", type=int, default=3)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--shortlist-minimum-prior-citations", type=int, default=100)
    parser.add_argument("--shortlist-minimum-cited-prior-works", type=int, default=3)
    parser.add_argument("--shortlist-maximum-hit-authors", type=int, default=10)
    parser.add_argument("--temp-directory", type=Path, default=Path("/tmp/citations-duckdb-screen"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.temp_directory.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(args.database), read_only=True)
    con.execute("SET threads=4")
    con.execute("SET memory_limit='6GB'")
    con.execute("SET temp_directory=?", [str(args.temp_directory)])
    result = con.execute(QUERY, [args.minimum_author_citations, args.minimum_hit_share,
                                args.minimum_prior_works])
    columns = [item[0] for item in result.description]
    records = [dict(zip(columns, row)) for row in result.fetchmany(args.limit)]
    con.close()

    csv_path = args.output_dir / "economics_big_hit_candidates.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)

    shortlist = [row for row in records
                 if (row["prior_citations"] or 0) >= args.shortlist_minimum_prior_citations
                 and row["prior_cited_works"] >= args.shortlist_minimum_cited_prior_works
                 and row["hit_author_count"] <= args.shortlist_maximum_hit_authors]
    with (args.output_dir / "economics_big_hit_research_shortlist.csv").open(
            "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(shortlist)

    table_rows = "".join(
        "<tr>" + "".join([
            f"<td>{html.escape(str(row['author_name']))}</td>",
            f"<td>{html.escape(str(row['hit_title']))}</td>",
            f"<td>{row['hit_publication_year']}</td>",
            f"<td>{row['hit_cited_by_count']:,}</td>",
            f"<td>{row['economics_portfolio_citations']:,}</td>",
            f"<td>{row['hit_share']:.1%}</td>",
            f"<td>{row['prior_works']}</td>",
        ]) + "</tr>" for row in shortlist[:250]
    )
    report = f"""<!doctype html><html><head><meta charset='utf-8'><title>Economics big-hit candidates</title><style>body{{font:15px system-ui;max-width:1200px;margin:40px auto;padding:0 20px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:7px;border-bottom:1px solid #ddd;text-align:left}}th{{position:sticky;top:0;background:white}}.note{{background:#fffaeb;padding:14px;border-left:5px solid #f79009}}</style></head><body><h1>Economics big-hit author candidates</h1><p class='note'><strong>Screening output, not final classification.</strong> Citation shares use research works classified in the economics subject database, not each author's complete all-field OpenAlex portfolio. Reference-based unrelated-paper eligibility is the next validation stage.</p><p>Raw definition: author economics citations ≥ {args.minimum_author_citations:,}; top-work share &gt; {args.minimum_hit_share:.0%}; at least {args.minimum_prior_works} earlier research works. The displayed research shortlist additionally requires ≥{args.shortlist_minimum_prior_citations} prior citations, ≥{args.shortlist_minimum_cited_prior_works} cited prior works, and ≤{args.shortlist_maximum_hit_authors} authors on the hit. {len(shortlist):,} shortlisted among {len(records):,} raw rows shown.</p><table><thead><tr><th>Author</th><th>Candidate hit</th><th>Year</th><th>Hit cites</th><th>Portfolio cites</th><th>Share</th><th>Prior works</th></tr></thead><tbody>{table_rows}</tbody></table></body></html>"""
    (args.output_dir / "economics_big_hit_candidates.html").write_text(report, encoding="utf-8")
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(args.database), "definition": "economics research-work portfolio",
        "work_types": ["article", "preprint", "review"],
        "minimum_author_citations": args.minimum_author_citations,
        "minimum_hit_share_strict": args.minimum_hit_share,
        "minimum_prior_works": args.minimum_prior_works,
        "rows_written": len(records), "shortlist_rows": len(shortlist), "limit": args.limit,
        "temp_directory": str(args.temp_directory),
        "caveat": "Requires all-field denominator, deduplication, and hit-reference validation before final classification.",
    }
    (args.output_dir / "economics_big_hit_screen_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
