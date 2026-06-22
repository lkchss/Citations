#!/usr/bin/env python3
"""Build a queryable DuckDB database from subject table part CSVs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


DEFAULT_SUBJECT_ROOT = Path("/root/sdb1/openalex/subjects")
DEFAULT_DATABASE = DEFAULT_SUBJECT_ROOT / "subject_level.duckdb"
TABLE_SPECS = {
    "works": {
        "duckdb_table": "subject_works",
        "pattern": "part_*_works.csv.gz",
        "columns": {
            "work_id": "VARCHAR",
            "title": "VARCHAR",
            "publication_year": "VARCHAR",
            "type": "VARCHAR",
            "cited_by_count": "VARCHAR",
            "fwci": "VARCHAR",
            "field_id": "VARCHAR",
            "field_name": "VARCHAR",
            "subfield_id": "VARCHAR",
            "subfield_name": "VARCHAR",
            "topic_id": "VARCHAR",
            "topic_name": "VARCHAR",
            "referenced_works_count": "VARCHAR",
        },
        "select": """
            subject,
            work_id,
            title,
            TRY_CAST(publication_year AS INTEGER) AS publication_year,
            type,
            TRY_CAST(cited_by_count AS BIGINT) AS cited_by_count,
            TRY_CAST(NULLIF(fwci, '') AS DOUBLE) AS fwci,
            field_id,
            field_name,
            subfield_id,
            subfield_name,
            topic_id,
            topic_name,
            TRY_CAST(referenced_works_count AS BIGINT) AS referenced_works_count
        """,
    },
    "work_authors": {
        "duckdb_table": "subject_work_authors",
        "pattern": "part_*_work_authors.csv.gz",
        "columns": {
            "work_id": "VARCHAR",
            "author_id": "VARCHAR",
            "author_name": "VARCHAR",
            "author_position": "VARCHAR",
            "author_sequence": "VARCHAR",
        },
        "select": """
            subject,
            work_id,
            author_id,
            author_name,
            author_position,
            TRY_CAST(author_sequence AS INTEGER) AS author_sequence
        """,
    },
    "work_citations_by_year": {
        "duckdb_table": "subject_work_citations_by_year",
        "pattern": "part_*_work_citations_by_year.csv.gz",
        "columns": {
            "work_id": "VARCHAR",
            "year": "VARCHAR",
            "citations": "VARCHAR",
        },
        "select": """
            subject,
            work_id,
            TRY_CAST(year AS INTEGER) AS year,
            TRY_CAST(citations AS BIGINT) AS citations
        """,
    },
    "work_references": {
        "duckdb_table": "subject_work_references",
        "pattern": "part_*_work_references.csv.gz",
        "columns": {
            "work_id": "VARCHAR",
            "referenced_work_id": "VARCHAR",
        },
        "select": """
            subject,
            work_id,
            referenced_work_id
        """,
    },
}


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_string_list(values: Iterable[Path]) -> str:
    return "[" + ", ".join(sql_quote(str(value)) for value in values) + "]"


def sql_columns(columns: dict[str, str]) -> str:
    return "{" + ", ".join(f"{sql_quote(name)}: {dtype}" for name, dtype in columns.items()) + "}"


def selected_subjects(subject_root: Path, requested: list[str]) -> list[str]:
    subjects = requested or [
        path.parent.name
        for path in sorted(subject_root.glob("*/tables_parts"))
        if not path.parent.name.endswith("_logs")
    ]
    missing = [subject for subject in subjects if not (subject_root / subject / "tables_parts").exists()]
    if missing:
        raise SystemExit(f"Missing tables_parts for subjects: {', '.join(missing)}")
    return subjects


def create_schema(con, replace: bool) -> None:
    if replace:
        for spec in TABLE_SPECS.values():
            con.execute(f"DROP TABLE IF EXISTS {spec['duckdb_table']}")
        con.execute("DROP TABLE IF EXISTS subject_import_manifest")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS subject_works (
            subject VARCHAR,
            work_id VARCHAR,
            title VARCHAR,
            publication_year INTEGER,
            type VARCHAR,
            cited_by_count BIGINT,
            fwci DOUBLE,
            field_id VARCHAR,
            field_name VARCHAR,
            subfield_id VARCHAR,
            subfield_name VARCHAR,
            topic_id VARCHAR,
            topic_name VARCHAR,
            referenced_works_count BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS subject_work_authors (
            subject VARCHAR,
            work_id VARCHAR,
            author_id VARCHAR,
            author_name VARCHAR,
            author_position VARCHAR,
            author_sequence INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS subject_work_citations_by_year (
            subject VARCHAR,
            work_id VARCHAR,
            year INTEGER,
            citations BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS subject_work_references (
            subject VARCHAR,
            work_id VARCHAR,
            referenced_work_id VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS subject_import_manifest (
            subject VARCHAR,
            table_name VARCHAR,
            rows BIGINT,
            imported_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (subject, table_name)
        )
        """
    )


def create_views(con) -> None:
    con.execute(
        """
        CREATE OR REPLACE VIEW subject_work_year_citations AS
        SELECT
            w.subject,
            w.work_id,
            w.publication_year,
            c.year,
            c.year - w.publication_year AS paper_age,
            c.citations,
            w.type,
            w.field_name,
            w.subfield_name,
            w.topic_name
        FROM subject_work_citations_by_year c
        JOIN subject_works w
          ON c.subject = w.subject AND c.work_id = w.work_id
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW subject_author_work_counts AS
        SELECT
            subject,
            author_id,
            any_value(author_name) AS author_name,
            COUNT(DISTINCT work_id) AS works
        FROM subject_work_authors
        GROUP BY subject, author_id
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW subject_year_summary AS
        SELECT
            subject,
            publication_year,
            COUNT(*) AS works,
            SUM(cited_by_count) AS cited_by_count_total
        FROM subject_works
        GROUP BY subject, publication_year
        """
    )


def delete_existing_subject(con, subject: str, table_keys: list[str]) -> None:
    for table_key in table_keys:
        duckdb_table = TABLE_SPECS[table_key]["duckdb_table"]
        con.execute(f"DELETE FROM {duckdb_table} WHERE subject = ?", [subject])
        con.execute(
            "DELETE FROM subject_import_manifest WHERE subject = ? AND table_name = ?",
            [subject, table_key],
        )


def import_subject_table(con, subject_root: Path, subject: str, table_key: str) -> int:
    spec = TABLE_SPECS[table_key]
    files = sorted((subject_root / subject / "tables_parts").glob(str(spec["pattern"])))
    files = [path for path in files if not path.name.endswith(".tmp")]
    if not files:
        log(f"skip subject={subject} table={table_key} reason=no_parts")
        return 0

    duckdb_table = spec["duckdb_table"]
    query = f"""
        INSERT INTO {duckdb_table}
        SELECT {spec["select"]}
        FROM (
            SELECT {sql_quote(subject)} AS subject, *
            FROM read_csv(
                {sql_string_list(files)},
                header = true,
                columns = {sql_columns(spec["columns"])},
                delim = ',',
                quote = '"',
                escape = '"',
                compression = 'gzip',
                null_padding = true,
                strict_mode = false
            )
        );
    """
    log(f"import_start subject={subject} table={table_key} files={len(files)}")
    con.execute(query)
    row_count = con.execute(
        f"SELECT COUNT(*) FROM {duckdb_table} WHERE subject = ?", [subject]
    ).fetchone()[0]
    log(f"import_done subject={subject} table={table_key} rows={row_count:,}")
    return int(row_count)


def create_indexes(con) -> None:
    for statement in [
        "CREATE INDEX IF NOT EXISTS idx_subject_works_subject_work ON subject_works(subject, work_id)",
        "CREATE INDEX IF NOT EXISTS idx_subject_authors_subject_work ON subject_work_authors(subject, work_id)",
        "CREATE INDEX IF NOT EXISTS idx_subject_authors_subject_author ON subject_work_authors(subject, author_id)",
        "CREATE INDEX IF NOT EXISTS idx_subject_citations_subject_work ON subject_work_citations_by_year(subject, work_id)",
        "CREATE INDEX IF NOT EXISTS idx_subject_refs_subject_work ON subject_work_references(subject, work_id)",
        "CREATE INDEX IF NOT EXISTS idx_subject_refs_subject_ref ON subject_work_references(subject, referenced_work_id)",
    ]:
        log(f"index_start {statement}")
        con.execute(statement)
        log("index_done")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, default=DEFAULT_SUBJECT_ROOT)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--table", action="append", choices=sorted(TABLE_SPECS), default=[])
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--replace-subject", action="store_true")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--memory-limit", default="12GB")
    parser.add_argument("--create-indexes", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        import duckdb
    except ImportError as exc:
        raise SystemExit(
            "DuckDB is required. Use a project venv with `python -m pip install duckdb`."
        ) from exc

    subjects = selected_subjects(args.subject_root, args.subject)
    table_keys = args.table or list(TABLE_SPECS)
    args.database.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(args.database))
    con.execute(f"SET threads TO {max(1, args.threads)}")
    con.execute(f"SET memory_limit = {sql_quote(args.memory_limit)}")
    create_schema(con, replace=args.replace)
    create_views(con)

    summary: dict[str, object] = {
        "database": str(args.database),
        "subject_root": str(args.subject_root),
        "subjects": subjects,
        "tables": table_keys,
        "rows": {},
    }
    for subject in subjects:
        if args.replace_subject:
            delete_existing_subject(con, subject, table_keys)
        for table_key in table_keys:
            existing = con.execute(
                "SELECT rows FROM subject_import_manifest WHERE subject = ? AND table_name = ?",
                [subject, table_key],
            ).fetchone()
            if existing and not args.replace_subject and not args.replace:
                log(f"skip subject={subject} table={table_key} reason=manifest_exists rows={existing[0]:,}")
                summary["rows"][f"{subject}.{table_key}"] = int(existing[0])
                continue
            rows = import_subject_table(con, args.subject_root, subject, table_key)
            con.execute(
                "INSERT OR REPLACE INTO subject_import_manifest(subject, table_name, rows) VALUES (?, ?, ?)",
                [subject, table_key, rows],
            )
            summary["rows"][f"{subject}.{table_key}"] = rows

    if args.create_indexes:
        create_indexes(con)
    create_views(con)
    con.close()

    summary_path = args.database.with_suffix(args.database.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
