#!/usr/bin/env python3
"""Audit duplicate incoming references for focal works with citation mismatches."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--panel", type=Path, required=True)
    p.add_argument("--calculated-citations", type=Path, required=True)
    p.add_argument("--snapshot-works-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--progress-every", type=int, default=100)
    return p.parse_args()


def focal_mismatches(database: Path, panel: Path, calculated: Path) -> dict[str, int]:
    con = duckdb.connect(str(database), read_only=True)
    query = """
    WITH focal AS (
      SELECT DISTINCT work_id FROM read_csv_auto(?, header=true)
    ), calc AS (
      SELECT work_id, SUM(TRY_CAST(calculated_citations AS BIGINT)) AS total
      FROM read_csv_auto(?, header=true)
      GROUP BY 1
    )
    SELECT f.work_id
    FROM focal f
    JOIN subject_works w
      ON w.subject = 'economics_econometrics_and_finance' AND w.work_id = f.work_id
    LEFT JOIN calc c ON c.work_id = f.work_id
    WHERE COALESCE(c.total, 0) <> w.cited_by_count
    """
    return {row[0]: 1 for row in con.execute(query, [str(panel), str(calculated)]).fetchall()}


def main() -> int:
    parsed = args()
    targets = set(focal_mismatches(parsed.database, parsed.panel, parsed.calculated_citations))
    total_matches: Counter[str] = Counter()
    unique_citers: defaultdict[str, set[str]] = defaultdict(set)
    duplicate_entries: Counter[str] = Counter()
    examples: list[dict[str, object]] = []
    files_seen = records_seen = matching_citers = 0
    files = sorted(parsed.snapshot_works_dir.rglob("*.gz"))
    for file_index, path in enumerate(files, 1):
        files_seen += 1
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                records_seen += 1
                work = json.loads(line)
                work_id = str(work.get("id") or "")
                matches = [str(ref) for ref in (work.get("referenced_works") or []) if str(ref) in targets]
                if not matches:
                    continue
                matching_citers += 1
                counts = Counter(matches)
                for target, count in counts.items():
                    total_matches[target] += count
                    unique_citers[target].add(work_id)
                    if count > 1:
                        duplicate_entries[target] += count - 1
                        if len(examples) < 50:
                            examples.append({"citing_work_id": work_id, "target_work_id": target, "repetitions": count, "source_file": str(path)})
        if file_index % parsed.progress_every == 0:
            print(f"files={file_index:,}/{len(files):,} records={records_seen:,} matching_citers={matching_citers:,}", flush=True)

    result = {
        "target_count": len(targets),
        "files_seen": files_seen,
        "records_seen": records_seen,
        "matching_citing_works": matching_citers,
        "total_matching_reference_entries": sum(total_matches.values()),
        "duplicate_reference_entries": sum(duplicate_entries.values()),
        "targets_with_duplicate_entries": len(duplicate_entries),
        "duplicate_entries_by_target": dict(sorted(duplicate_entries.items())),
        "reference_entries_by_target": dict(sorted(total_matches.items())),
        "unique_citers_by_target": {k: len(unique_citers[k]) for k in sorted(unique_citers)},
        "examples": examples,
    }
    parsed.output.parent.mkdir(parents=True, exist_ok=True)
    parsed.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("target_count", "files_seen", "records_seen", "duplicate_reference_entries", "targets_with_duplicate_entries")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
