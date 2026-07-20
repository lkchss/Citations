from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "validate_subject_database.py"


class SubjectDatabaseValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.subject_root = self.root / "subjects"
        self.subject = "test_subject"
        self.parts = self.subject_root / self.subject / "tables_parts"
        self.parts.mkdir(parents=True)
        self.database = self.root / "subject_level.duckdb"
        self.summary = self.database.with_suffix(".duckdb.summary.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_part(self, name: str, header: str = "work_id,referenced_work_id\n", rows: str = "W1,R1\n") -> Path:
        path = self.parts / name
        with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
            handle.write(header)
            handle.write(rows)
        return path

    def write_database(self, rows: int = 1) -> None:
        import duckdb

        con = duckdb.connect(str(self.database))
        con.execute("CREATE TABLE subject_work_references(subject VARCHAR, work_id VARCHAR, referenced_work_id VARCHAR)")
        for index in range(rows):
            con.execute("INSERT INTO subject_work_references VALUES (?, ?, ?)", [self.subject, f"W{index}", "R1"])
        con.close()

    def write_summary(self, rows: int = 1) -> None:
        self.summary.write_text(json.dumps({
            "database": str(self.database), "subject_root": str(self.subject_root),
            "subjects": [self.subject], "tables": ["work_references"],
            "rows": {f"{self.subject}.work_references": rows},
        }), encoding="utf-8")

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run([
            sys.executable, str(SCRIPT), "--subject-root", str(self.subject_root),
            "--database", str(self.database), "--subject", self.subject,
            "--table", "work_references", "--import-summary", str(self.summary),
        ], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_validates_header_manifest_checksum_and_row_count(self) -> None:
        try:
            import duckdb  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("duckdb is not installed")
        output = self.write_part("part_refbackfill_000000_work_references.csv.gz")
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        manifest_dir = self.subject_root / self.subject / ".reference_backfill" / "chunks"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "000000.json").write_text(json.dumps({
            "status": "complete", "output": output.name,
            "output_size": output.stat().st_size, "output_sha256": digest,
        }), encoding="utf-8")
        self.write_database()
        self.write_summary()

        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        check = report["checks"][0]
        self.assertTrue(check["files"]["valid"])
        self.assertTrue(check["reference_manifests"]["valid"])
        self.assertTrue(check["duckdb"]["row_count_match"])

    def test_detects_bad_header_checksum_and_row_count(self) -> None:
        output = self.write_part("part_0000_work_references.csv.gz", header="wrong,header\n")
        manifest_dir = self.subject_root / self.subject / ".reference_backfill" / "chunks"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "000000.json").write_text(json.dumps({
            "status": "complete", "output": output.name,
            "output_size": output.stat().st_size, "output_sha256": "0" * 64,
        }), encoding="utf-8")
        self.write_summary(rows=1)

        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        check = report["checks"][0]
        self.assertFalse(check["files"]["valid"])
        self.assertFalse(check["reference_manifests"]["valid"])
        self.assertFalse(check["duckdb"]["valid"])

    def test_missing_reference_state_is_not_an_error_but_missing_parts_is(self) -> None:
        self.write_summary(rows=0)
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        check = json.loads(result.stdout)["checks"][0]
        self.assertFalse(check["files"]["expected_files"])
        self.assertTrue(check["reference_manifests"]["valid"])


if __name__ == "__main__":
    unittest.main()
