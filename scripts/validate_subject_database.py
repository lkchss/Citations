#!/usr/bin/env python3
"""Read-only integrity checks for selected subject table parts and DuckDB imports."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_SUBJECT_ROOT = Path("/root/sdb1/openalex/subjects")
DEFAULT_DATABASE = DEFAULT_SUBJECT_ROOT / "subject_level.duckdb"

TABLE_SPECS: dict[str, dict[str, Any]] = {
    "works": {
        "duckdb_table": "subject_works",
        "pattern": "part_*_works.csv.gz",
        "header": [
            "work_id", "title", "publication_year", "type", "cited_by_count",
            "fwci", "field_id", "field_name", "subfield_id", "subfield_name",
            "topic_id", "topic_name", "referenced_works_count",
        ],
    },
    "work_authors": {
        "duckdb_table": "subject_work_authors",
        "pattern": "part_*_work_authors.csv.gz",
        "header": ["work_id", "author_id", "author_name", "author_position", "author_sequence"],
    },
    "work_citations_by_year": {
        "duckdb_table": "subject_work_citations_by_year",
        "pattern": "part_*_work_citations_by_year.csv.gz",
        "header": ["work_id", "year", "citations"],
    },
    "work_references": {
        "duckdb_table": "subject_work_references",
        "pattern": "part_*_work_references.csv.gz",
        "header": ["work_id", "referenced_work_id"],
    },
}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_gzip_header(path: Path, expected: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path), "valid": False}
    try:
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            result["header"] = next(csv.reader(handle), None)
        result["header_valid"] = result["header"] == expected
        result["valid"] = bool(result["header_valid"])
        if not result["valid"]:
            result["error"] = "unexpected CSV header"
    except (OSError, EOFError, UnicodeError, csv.Error) as exc:
        result["error"] = f"invalid gzip/header: {exc}"
    return result


def table_files_check(table_parts: Path, table_key: str) -> dict[str, Any]:
    spec = TABLE_SPECS[table_key]
    files = sorted(table_parts.glob(spec["pattern"]))
    files = [path for path in files if not path.name.endswith(".tmp")]
    file_checks = [check_gzip_header(path, spec["header"]) for path in files]
    return {
        "pattern": spec["pattern"],
        "expected_files": len(files) > 0,
        "files": file_checks,
        "file_count": len(files),
        "valid": bool(files) and all(item["valid"] for item in file_checks),
    }


def reference_manifests_check(subject_dir: Path) -> dict[str, Any]:
    state_dir = subject_dir / ".reference_backfill"
    manifest_paths = sorted((state_dir / "chunks").glob("*.json")) if state_dir.is_dir() else []
    if not manifest_paths:
        return {"present": False, "manifest_count": 0, "valid": True, "manifests": []}

    parts_dir = subject_dir / "tables_parts"
    checks: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        item: dict[str, Any] = {"manifest": str(manifest_path), "valid": False}
        try:
            with manifest_path.open(encoding="utf-8") as handle:
                manifest = json.load(handle)
            item["status"] = manifest.get("status")
            output_name = manifest.get("output")
            output = parts_dir / output_name if isinstance(output_name, str) else None
            item["output"] = str(output) if output else None
            errors: list[str] = []
            if manifest.get("status") != "complete":
                errors.append("manifest status is not complete")
            if output is None or Path(output_name).name != output_name:
                errors.append("manifest output is not a file name")
            elif not output.is_file():
                errors.append("manifest output is missing")
            else:
                item["output_size"] = output.stat().st_size
                if manifest.get("output_size") != output.stat().st_size:
                    errors.append("output size mismatch")
                actual_sha = sha256_path(output)
                item["output_sha256"] = actual_sha
                if manifest.get("output_sha256") != actual_sha:
                    errors.append("output SHA-256 mismatch")
                header = check_gzip_header(output, TABLE_SPECS["work_references"]["header"])
                item["header_valid"] = header["valid"]
                if not header["valid"]:
                    errors.append(header.get("error", "unexpected CSV header"))
            item["errors"] = errors
            item["valid"] = not errors
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            item["errors"] = [f"invalid manifest: {exc}"]
        checks.append(item)
    return {
        "present": True,
        "manifest_count": len(checks),
        "valid": all(item["valid"] for item in checks),
        "manifests": checks,
    }


def duckdb_check(database: Path, subject: str, table_key: str, source_rows: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"database": str(database), "valid": False}
    if not database.is_file():
        result["error"] = "database is missing"
        return result
    try:
        import duckdb

        con = duckdb.connect(str(database), read_only=True)
        table = TABLE_SPECS[table_key]["duckdb_table"]
        actual = int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE subject = ?", [subject]).fetchone()[0])
        result["actual_rows"] = actual
        result["source_rows"] = source_rows
        result["row_count_match"] = isinstance(source_rows, int) and actual == source_rows
        result["valid"] = result["row_count_match"]
        if not result["valid"]:
            result["error"] = "DuckDB row count does not match source manifest"
        con.close()
    except Exception as exc:
        result["error"] = f"DuckDB query failed: {exc}"
    return result


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    summary_path = args.import_summary or args.database.with_suffix(args.database.suffix + ".summary.json")
    summary: dict[str, Any] = {}
    errors: list[str] = []
    try:
        with summary_path.open(encoding="utf-8") as handle:
            summary = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"import summary unavailable: {exc}")

    subjects = args.subject or summary.get("subjects", [])
    tables = args.table or summary.get("tables", [])
    if not subjects:
        errors.append("no subjects selected")
    if not tables:
        errors.append("no tables selected")
    invalid_tables = [table for table in tables if table not in TABLE_SPECS]
    if invalid_tables:
        errors.extend(f"unknown table: {table}" for table in invalid_tables)

    checks: list[dict[str, Any]] = []
    source_rows_map = summary.get("rows", {}) if isinstance(summary.get("rows", {}), dict) else {}
    for subject in subjects:
        subject_dir = args.subject_root / subject
        for table_key in tables:
            if table_key not in TABLE_SPECS:
                continue
            key = f"{subject}.{table_key}"
            source_rows = source_rows_map.get(key)
            table_check = table_files_check(subject_dir / "tables_parts", table_key)
            reference_check = (
                reference_manifests_check(subject_dir)
                if table_key == "work_references" else {"present": False, "valid": True}
            )
            db_check = duckdb_check(args.database, subject, table_key, source_rows)
            item = {"subject": subject, "table": table_key, "files": table_check,
                    "reference_manifests": reference_check, "duckdb": db_check}
            item["valid"] = all((table_check["valid"], reference_check["valid"], db_check["valid"]))
            checks.append(item)
            if not item["valid"]:
                errors.append(f"{key} failed validation")
    return {
        "valid": not errors and bool(checks) and all(item["valid"] for item in checks),
        "subject_root": str(args.subject_root),
        "database": str(args.database),
        "import_summary": str(summary_path),
        "subjects": subjects,
        "tables": tables,
        "checks": checks,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, default=DEFAULT_SUBJECT_ROOT)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--import-summary", "--source-manifest", "--manifest",
        dest="import_summary", type=Path,
    )
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--table", action="append", choices=sorted(TABLE_SPECS), default=[])
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON (the default).")
    return parser.parse_args()


def main() -> int:
    report = build_report(parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
