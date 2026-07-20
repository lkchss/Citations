#!/usr/bin/env python3
"""Build bounded-memory economics paper-author-year exposure rows from DuckDB.

The sample and all joins/aggregations stay in DuckDB.  Python receives only
small record batches while writing the final gzip CSV, so the builder does not
materialize the author graph, reference graph, or citation histories.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import tempfile
from pathlib import Path


DEFAULT_DATABASE = Path("/root/sdb1/openalex/subjects/subject_level.duckdb")
DEFAULT_SUBJECT = "economics_econometrics_and_finance"
DEFAULT_OUTPUT = Path(
    "/root/sdb1/openalex/subjects/economics_econometrics_and_finance/"
    "exposure/economics_exposure.csv.gz"
)

FIELDNAMES = [
    "subject",
    "author_id",
    "work_id",
    "year",
    "publication_year",
    "paper_age",
    "citations_jt",
    "accumulated_unrelated_citations_jt",
    "accumulated_related_citations_jt",
    "author_subject_papers",
    "related_author_papers",
    "citation_source",
]


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-year", type=int, default=1900)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--sample-mod", type=int, default=2000)
    parser.add_argument("--sample-keep", type=int, default=1)
    parser.add_argument(
        "--max-authors",
        type=int,
        default=5000,
        help="Hard cap on retained authors; deterministic author_id order is used.",
    )
    parser.add_argument("--min-author-papers", type=int, default=2)
    parser.add_argument("--focal-sample-mod", type=int, default=1)
    parser.add_argument("--focal-sample-keep", type=int, default=1)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--memory-limit", default="12GB")
    parser.add_argument(
        "--temp-directory",
        type=Path,
        default=None,
        help="DuckDB spill directory; defaults to the system temporary directory.",
    )
    parser.add_argument("--batch-size", type=int, default=10_000)
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("--start-year must not exceed --end-year")
    if args.sample_mod < 1 or not 1 <= args.sample_keep <= args.sample_mod:
        parser.error("require 1 <= --sample-keep <= --sample-mod")
    if args.max_authors < 1 or args.min_author_papers < 1:
        parser.error("--max-authors and --min-author-papers must be positive")
    if args.focal_sample_mod < 1 or not 1 <= args.focal_sample_keep <= args.focal_sample_mod:
        parser.error("require 1 <= --focal-sample-keep <= --focal-sample-mod")
    if args.threads < 1 or args.batch_size < 1:
        parser.error("--threads and --batch-size must be positive")
    return args


def build_query(args: argparse.Namespace) -> str:
    # The only Python-side result is the final ordered SELECT.  Temp tables are
    # deliberately used to prevent CTE inlining from repeating expensive joins.
    return f"""
        CREATE OR REPLACE TEMP TABLE sampled_authorships AS
        WITH author_counts AS (
            SELECT a.author_id
            FROM subject_work_authors a
            JOIN subject_works w
              ON w.subject = a.subject AND w.work_id = a.work_id
            WHERE a.subject = ? AND a.author_id IS NOT NULL AND a.author_id <> ''
              AND w.publication_year IS NOT NULL
              AND a.work_id IS NOT NULL AND a.work_id <> ''
              AND mod(hash(a.author_id), {args.sample_mod}) < {args.sample_keep}
            GROUP BY author_id
            HAVING count(DISTINCT a.work_id) >= {args.min_author_papers}
        ), retained_authors AS (
            SELECT author_id
            FROM author_counts
            ORDER BY author_id
            LIMIT {args.max_authors}
        )
        SELECT DISTINCT a.subject, a.author_id, a.work_id
        FROM subject_work_authors a
        JOIN retained_authors r USING (author_id)
        JOIN subject_works w
          ON w.subject = a.subject AND w.work_id = a.work_id
        WHERE a.subject = ? AND w.publication_year IS NOT NULL
          AND mod(hash(a.author_id), {args.sample_mod}) < {args.sample_keep}
        """


def run(args: argparse.Namespace) -> dict[str, object]:
    try:
        import duckdb
    except ImportError as exc:
        raise SystemExit("DuckDB is required; use .venv-duckdb/bin/python.") from exc

    if not args.database.exists():
        raise SystemExit(f"DuckDB database does not exist: {args.database}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_directory = args.temp_directory or Path(tempfile.gettempdir())
    temp_directory.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(args.database), read_only=True)
    con.execute(f"SET threads TO {args.threads}")
    con.execute("SET memory_limit = ?", [args.memory_limit])
    con.execute("SET temp_directory = ?", [str(temp_directory)])
    con.execute(build_query(args), [args.subject, args.subject])
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE focal_authorships AS
        SELECT a.*, w.publication_year,
               count(*) OVER (PARTITION BY a.author_id) AS author_subject_papers
        FROM sampled_authorships a
        JOIN subject_works w USING (subject, work_id)
        WHERE mod(hash(a.work_id), ?) < ?
        """,
        [args.focal_sample_mod, args.focal_sample_keep],
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE related_pairs AS
        SELECT DISTINCT subject, work_id AS focal_work_id, work_id AS related_work_id
        FROM focal_authorships
        UNION
        SELECT DISTINCT r.subject, r.work_id, r.referenced_work_id
        FROM subject_work_references r
        JOIN focal_authorships f
          ON f.subject = r.subject AND f.work_id = r.work_id
        JOIN sampled_authorships h
          ON h.subject = r.subject AND h.work_id = r.referenced_work_id
        UNION
        SELECT DISTINCT r.subject, r.referenced_work_id, r.work_id
        FROM subject_work_references r
        JOIN focal_authorships f
          ON f.subject = r.subject AND f.work_id = r.referenced_work_id
        JOIN sampled_authorships h
          ON h.subject = r.subject AND h.work_id = r.work_id
        """
    )
    authors, history_works = con.execute(
        "SELECT count(DISTINCT author_id), count(DISTINCT work_id) FROM sampled_authorships"
    ).fetchone()
    focal_works = con.execute("SELECT count(DISTINCT work_id) FROM focal_authorships").fetchone()[0]
    query = """
        WITH years AS (
            SELECT unnest(range(?, ? + 1))::INTEGER AS year
        ), focal_years AS (
            SELECT f.subject, f.author_id, f.work_id, f.publication_year,
                   y.year, f.author_subject_papers
            FROM focal_authorships f CROSS JOIN years y
            WHERE y.year >= greatest(?, f.publication_year)
        ), author_work_pairs AS (
            SELECT f.subject, f.author_id, f.work_id AS focal_work_id,
                   h.work_id AS history_work_id,
                   CASE WHEN rp.related_work_id IS NULL THEN 0 ELSE 1 END AS is_related
            FROM focal_authorships f
            JOIN sampled_authorships h
              ON h.subject = f.subject AND h.author_id = f.author_id
             AND h.work_id <> f.work_id
            LEFT JOIN related_pairs rp
              ON rp.subject = f.subject AND rp.focal_work_id = f.work_id
             AND rp.related_work_id = h.work_id
        ), stocks AS (
            SELECT fy.subject, fy.author_id, fy.work_id, fy.year,
                   sum(CASE WHEN p.is_related = 1 THEN coalesce(c.citations, 0) ELSE 0 END) AS related_stock,
                   sum(CASE WHEN p.is_related = 0 THEN coalesce(c.citations, 0) ELSE 0 END) AS unrelated_stock,
                   count(DISTINCT p.history_work_id) FILTER (WHERE p.is_related = 1) AS related_papers
            FROM focal_years fy
            JOIN author_work_pairs p
              ON p.subject = fy.subject AND p.author_id = fy.author_id
             AND p.focal_work_id = fy.work_id
            JOIN subject_works hw
              ON hw.subject = p.subject AND hw.work_id = p.history_work_id
            LEFT JOIN subject_work_citations_by_year c
              ON c.subject = hw.subject AND c.work_id = hw.work_id
             AND c.year >= greatest(?, hw.publication_year)
             AND c.year < fy.year
            GROUP BY fy.subject, fy.author_id, fy.work_id, fy.year
        )
        SELECT fy.subject, fy.author_id, fy.work_id, fy.year,
               fy.publication_year, fy.year - fy.publication_year AS paper_age,
               coalesce(fc.citations, 0) AS citations_jt,
               coalesce(s.unrelated_stock, 0) AS accumulated_unrelated_citations_jt,
               coalesce(s.related_stock, 0) AS accumulated_related_citations_jt,
               fy.author_subject_papers, coalesce(s.related_papers, 0) AS related_author_papers,
               'duckdb_subject_work_citations_by_year' AS citation_source
        FROM focal_years fy
        LEFT JOIN subject_work_citations_by_year fc
          ON fc.subject = fy.subject AND fc.work_id = fy.work_id AND fc.year = fy.year
        LEFT JOIN stocks s
          ON s.subject = fy.subject AND s.author_id = fy.author_id
         AND s.work_id = fy.work_id AND s.year = fy.year
        ORDER BY fy.author_id, fy.work_id, fy.year
    """

    tmp_name: str | None = None
    rows = 0
    citations_sum = 0
    fd, tmp_name = tempfile.mkstemp(prefix=f".{args.output.name}.", suffix=".tmp", dir=args.output.parent)
    os.close(fd)
    try:
        with gzip.open(tmp_name, "wt", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(FIELDNAMES)
            result = con.execute(query, [args.start_year, args.end_year, args.start_year, args.start_year])
            while batch := result.fetchmany(args.batch_size):
                for row in batch:
                    writer.writerow(row)
                    rows += 1
                    citations_sum += int(row[6] or 0)
                    if rows % 1_000_000 == 0:
                        log(f"wrote {rows:,} rows")
        os.replace(tmp_name, args.output)
        tmp_name = None
    finally:
        con.close()
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    summary = {
        "database": str(args.database),
        "subject": args.subject,
        "output": str(args.output),
        "rows": rows,
        "observed_citations_sum": citations_sum,
        "authors": int(authors),
        "focal_works": int(focal_works),
        "author_history_works": int(history_works),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "sample_mod": args.sample_mod,
        "sample_keep": args.sample_keep,
        "max_authors": args.max_authors,
        "min_author_papers": args.min_author_papers,
        "focal_sample_mod": args.focal_sample_mod,
        "focal_sample_keep": args.focal_sample_keep,
        "memory_limit": args.memory_limit,
        "temp_directory": str(temp_directory),
        "relation_definition": "self_or_direct_reference_either_direction",
        "lag_definition": "citation_year >= max(start_year, publication_year) and citation_year < row_year",
    }
    atomic_json(args.output.with_name(f"{args.output.name}.summary.json"), summary)
    return summary


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))
