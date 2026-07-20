from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "validate_economics_citation_coverage.py"


class EconomicsCitationCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import duckdb  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("duckdb is not installed")
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.subject = "economics_econometrics_and_finance"
        self.subject_root = root / "subjects"
        (self.subject_root / self.subject / "tables_parts").mkdir(parents=True)
        self.database = root / "subjects.duckdb"
        self.panel = root / "panel.csv.gz"
        self.calculated = root / "calculated.csv.gz"
        import duckdb
        con = duckdb.connect(str(self.database))
        con.execute("""CREATE TABLE subject_works (
            subject VARCHAR, work_id VARCHAR, cited_by_count BIGINT,
            referenced_works_count BIGINT
        )""")
        con.executemany("INSERT INTO subject_works VALUES (?, ?, ?, ?)", [
            (self.subject, "W1", 3, 2), (self.subject, "W2", 0, 0),
            (self.subject, "W3", 4, 1), (self.subject, "W4", 2, 1),
        ])
        con.close()
        self.write_gzip(self.panel, ["work_id", "year"], [["W1", 2020], ["W2", 2020], ["W3", 2020], ["W4", 2020], ["W1", 2021]])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def write_gzip(path: Path, fields: list[str], rows: list[list[object]]) -> None:
        with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            writer.writerows(rows)

    def run_validator(self, rows: list[list[object]], *extra: str) -> tuple[int, dict[str, object]]:
        self.write_gzip(self.calculated, ["work_id", "year", "calculated_citations"], rows)
        result = subprocess.run([
            sys.executable, str(SCRIPT), "--database", str(self.database),
            "--panel", str(self.panel), "--calculated-citations", str(self.calculated),
            "--subject-root", str(self.subject_root), *extra,
        ], check=False, capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def test_counts_and_zero_reference_work(self) -> None:
        code, report = self.run_validator([
            ["W1", 2020, 1], ["W1", 2021, 2], ["W3", 2020, 5], ["W4", 2020, 1],
        ])
        self.assertEqual(code, 1)
        self.assertEqual(report["focal_count"], 4)
        self.assertEqual(report["exact_matches"], 2)
        self.assertEqual(report["missing_calculated_totals"], 0)
        self.assertEqual(report["calculated_higher"], 1)
        self.assertEqual(report["calculated_lower"], 1)
        self.assertEqual(report["absolute_difference"], 2)
        self.assertFalse(report["valid"])

    def test_missing_nonzero_reference_total_and_thresholds(self) -> None:
        code, report = self.run_validator([["W1", 2020, 3]], "--max-missing-calculated-totals", "1", "--max-absolute-difference", "0")
        self.assertEqual(code, 1)
        self.assertEqual(report["missing_calculated_totals"], 2)
        self.assertEqual(report["absolute_difference"], 0)
        code, report = self.run_validator([["W1", 2020, 3]], "--max-missing-calculated-totals", "2", "--max-absolute-difference", "0")
        self.assertEqual(code, 0)
        self.assertTrue(report["valid"])


if __name__ == "__main__":
    unittest.main()
