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
BACKFILL_SCRIPT = REPO_DIR / "scripts" / "backfill_subject_work_references.py"
CHECK_SCRIPT = REPO_DIR / "scripts" / "check_openalex_environment.py"


def write_gzip_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        handle.write(text)


class ReferenceBackfillRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.subject_root = self.root / "subjects"
        self.snapshot_dir = self.root / "snapshot"
        self.table_parts = self.subject_root / "test_subject" / "tables_parts"
        self.table_parts.mkdir(parents=True)
        write_gzip_text(
            self.table_parts / "part_0000_works.csv.gz",
            "\n".join(
                [
                    "work_id,title,publication_year,type,cited_by_count,fwci,field_id,field_name,subfield_id,subfield_name,topic_id,topic_name,referenced_works_count",
                    "W1,Test,2020,article,0,,F1,Field,S1,Sub,T1,Topic,2",
                    "",
                ]
            ),
        )
        write_gzip_text(
            self.snapshot_dir / "updated_date=2026-01-01" / "part_0000.gz",
            "\n".join(
                [
                    json.dumps({"id": "W1", "referenced_works": ["W0", "W2"]}),
                    json.dumps({"id": "W9", "referenced_works": ["W1"]}),
                    "",
                ]
            ),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_backfill(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(BACKFILL_SCRIPT),
                "--subject-root",
                str(self.subject_root),
                "--snapshot-works-dir",
                str(self.snapshot_dir),
                "--subject",
                "test_subject",
                "--workers",
                "1",
                *extra,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_backfill_writes_atomic_final_reference_part(self) -> None:
        result = self.run_backfill("--clean-temp")
        self.assertEqual(result.returncode, 0, result.stderr)

        output = self.table_parts / "part_0000_work_references.csv.gz"
        tmp_output = output.with_name(f"{output.name}.tmp")
        self.assertTrue(output.exists())
        self.assertFalse(tmp_output.exists())

        with gzip.open(output, "rt", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(
            rows,
            [
                {"work_id": "W1", "referenced_work_id": "W0"},
                {"work_id": "W1", "referenced_work_id": "W2"},
            ],
        )

    def test_existing_final_parts_are_not_overwritten_by_default(self) -> None:
        first = self.run_backfill("--clean-temp")
        self.assertEqual(first.returncode, 0, first.stderr)

        second = self.run_backfill()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("pass --overwrite", second.stderr)

    def test_skip_existing_subjects_exits_successfully(self) -> None:
        first = self.run_backfill("--clean-temp")
        self.assertEqual(first.returncode, 0, first.stderr)

        second = self.run_backfill("--skip-existing-subjects")
        self.assertEqual(second.returncode, 0, second.stderr)
        summary = json.loads(second.stdout)
        self.assertTrue(summary["skipped_all_subjects"])
        self.assertEqual(summary["subjects"], [])

    def test_clean_temp_removes_stale_temp_outputs(self) -> None:
        stale = self.table_parts / "part_0000_work_references.csv.gz.tmp"
        stale.write_text("stale", encoding="utf-8")

        result = self.run_backfill("--clean-temp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(stale.exists())
        self.assertTrue((self.table_parts / "part_0000_work_references.csv.gz").exists())


class EnvironmentCheckerTests(unittest.TestCase):
    def test_checker_reports_missing_artifacts_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            openalex_root = root / "missing_openalex"
            repo_dir = root / "missing_repo"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CHECK_SCRIPT),
                    "--openalex-root",
                    str(openalex_root),
                    "--repo-dir",
                    str(repo_dir),
                    "--json",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["artifacts"]["openalex_root"]["exists"])
        self.assertFalse(report["repo"]["is_git_repo"])
        self.assertEqual(report["reference_status"][0]["final_reference_parts"], 0)


if __name__ == "__main__":
    unittest.main()
