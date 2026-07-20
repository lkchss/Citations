#!/usr/bin/env python3
"""Validate reconstructed economics citation totals against subject_works."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_SUBJECT = "economics_econometrics_and_finance"
DEFAULT_SUBJECT_ROOT = Path("/root/sdb1/openalex/subjects")
DEFAULT_DATABASE = DEFAULT_SUBJECT_ROOT / "subject_level.duckdb"


def subject_for_root(subject_root: Path, panel: Path, requested: str | None) -> str:
    """Return the subject partition represented by the supplied root."""
    if requested:
        return requested
    if (subject_root / "tables_parts").is_dir():
        return subject_root.name
    partitions = [p for p in subject_root.iterdir() if (p / "tables_parts").is_dir()]
    if not partitions:
        raise SystemExit(f"No subject tables_parts directory under {subject_root}")
    by_name = {p.name: p.name for p in partitions}
    if DEFAULT_SUBJECT in by_name:
        return DEFAULT_SUBJECT
    panel_parts = set(panel.parts)
    matching = [p.name for p in partitions if p.name in panel_parts]
    if len(matching) == 1:
        return matching[0]
    if len(partitions) == 1:
        return partitions[0].name
    raise SystemExit(
        "Cannot infer subject from --subject-root; expected the economics subject "
        "partition or a root containing exactly one subject"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--panel", type=Path, required=True, help="Gzip exposure CSV")
    parser.add_argument("--calculated-citations", type=Path, required=True, help="Gzip annual citation CSV")
    parser.add_argument("--subject-root", type=Path, default=DEFAULT_SUBJECT_ROOT)
    parser.add_argument("--subject", default=None)
    parser.add_argument(
        "--max-absolute-difference", "--absolute-difference-threshold",
        dest="max_absolute_difference", type=int, default=0,
    )
    parser.add_argument(
        "--max-missing-calculated-totals", "--missing-calculated-totals-threshold",
        dest="max_missing_calculated_totals", type=int, default=0,
    )
    args = parser.parse_args()
    if args.max_absolute_difference < 0 or args.max_missing_calculated_totals < 0:
        parser.error("validity thresholds cannot be negative")
    return args


def run(args: argparse.Namespace) -> dict[str, object]:
    try:
        import duckdb
    except ImportError as exc:
        raise SystemExit("DuckDB is required to validate citation coverage") from exc

    for path in (args.database, args.panel, args.calculated_citations):
        if not path.is_file():
            raise SystemExit(f"Required file does not exist: {path}")
    subject = subject_for_root(args.subject_root, args.panel, args.subject)
    con = duckdb.connect(str(args.database), read_only=True)
    try:
        # The first temp table bounds every later database/CSV join to focal IDs.
        con.execute(
            """
            CREATE TEMP TABLE focal_work_ids AS
            SELECT DISTINCT trim(work_id) AS work_id
            FROM read_csv(?, header=true, compression='gzip', auto_detect=true)
            WHERE work_id IS NOT NULL AND trim(work_id) <> ''
            """,
            [str(args.panel)],
        )
        con.execute(
            """
            CREATE TEMP TABLE calculated_totals AS
            SELECT trim(c.work_id) AS work_id,
                   SUM(TRY_CAST(c.calculated_citations AS BIGINT))::BIGINT AS calculated_total
            FROM read_csv(?, header=true, compression='gzip', auto_detect=true) c
            JOIN focal_work_ids f ON f.work_id = trim(c.work_id)
            GROUP BY trim(c.work_id)
            """,
            [str(args.calculated_citations)],
        )
        row = con.execute(
            """
            WITH targets AS (
                SELECT w.work_id,
                       max(coalesce(w.cited_by_count, 0))::BIGINT AS cited_by_count,
                       max(coalesce(w.cited_by_count, 0))::BIGINT AS cited_by_count_source
                FROM subject_works w
                JOIN focal_work_ids f ON f.work_id = w.work_id
                WHERE w.subject = ?
                GROUP BY w.work_id
            ), comparison AS (
                SELECT f.work_id, t.cited_by_count, t.cited_by_count_source,
                       c.calculated_total,
                       CASE WHEN c.calculated_total IS NULL
                            THEN 0 ELSE c.calculated_total END AS effective_total
                FROM focal_work_ids f
                LEFT JOIN targets t USING (work_id)
                LEFT JOIN calculated_totals c USING (work_id)
            )
            SELECT
                count(*)::BIGINT AS focal_count,
                count(*) FILTER (WHERE (calculated_total IS NOT NULL
                    OR coalesce(cited_by_count_source, 0) = 0)
                    AND effective_total = coalesce(cited_by_count, 0))::BIGINT AS exact_matches,
                count(*) FILTER (WHERE calculated_total IS NULL
                    AND coalesce(cited_by_count_source, 0) > 0)::BIGINT AS missing_calculated_totals,
                count(*) FILTER (WHERE (calculated_total IS NOT NULL
                    OR coalesce(cited_by_count_source, 0) = 0)
                    AND effective_total > coalesce(cited_by_count, 0))::BIGINT AS calculated_higher,
                count(*) FILTER (WHERE (calculated_total IS NOT NULL
                    OR coalesce(cited_by_count_source, 0) = 0)
                    AND effective_total < coalesce(cited_by_count, 0))::BIGINT AS calculated_lower,
                coalesce(sum(CASE WHEN calculated_total IS NOT NULL
                    OR coalesce(cited_by_count_source, 0) = 0
                    THEN abs(effective_total - coalesce(cited_by_count, 0)) ELSE 0 END), 0)::BIGINT
                    AS absolute_difference
            FROM comparison
            """,
            [subject],
        ).fetchone()
    finally:
        con.close()

    keys = (
        "focal_count", "exact_matches", "missing_calculated_totals",
        "calculated_higher", "calculated_lower", "absolute_difference",
    )
    report: dict[str, object] = dict(zip(keys, (int(value) for value in row)))
    report["subject"] = subject
    report["thresholds"] = {
        "max_absolute_difference": args.max_absolute_difference,
        "max_missing_calculated_totals": args.max_missing_calculated_totals,
    }
    report["valid"] = (
        report["absolute_difference"] <= args.max_absolute_difference
        and report["missing_calculated_totals"] <= args.max_missing_calculated_totals
    )
    return report


def main() -> int:
    report = run(parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
