from __future__ import annotations

import csv
import gzip
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
BACKFILL_SCRIPT = REPO_DIR / "scripts" / "backfill_subject_work_references_resumable.py"
REFERENCE_HEADER = "work_id,referenced_work_id\n"


def write_gzip_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        for line in lines:
            handle.write(f"{line}\n")


def read_reference_rows(path: Path) -> list[tuple[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return [
            (row["work_id"], row["referenced_work_id"])
            for row in csv.DictReader(handle)
        ]


class ResumableReferenceBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.subject_root = self.root / "subjects"
        self.snapshot_dir = self.root / "snapshot" / "data" / "works"
        self.table_parts = self.subject_root / "test_subject" / "tables_parts"
        self.table_parts.mkdir(parents=True)
        write_gzip_lines(
            self.table_parts / "part_0000_works.csv.gz",
            [
                "work_id,title",
                "W1,One",
                "W2,Two",
                "W3,Three",
                "W4,Four",
            ],
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_snapshot(self, name: str, works: list[dict[str, object]]) -> Path:
        path = self.snapshot_dir / "updated_date=2026-01-01" / name
        write_gzip_lines(path, [json.dumps(work, sort_keys=True) for work in works])
        return path

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
                "2",
                *extra,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def reference_parts(self) -> list[Path]:
        return sorted(self.table_parts.glob("part_*_work_references.csv.gz"))

    def assert_failed_with(self, result: subprocess.CompletedProcess[str], *words: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        message = f"{result.stdout}\n{result.stderr}".lower()
        self.assertTrue(
            any(word.lower() in message for word in words),
            f"expected one of {words!r} in failure output:\n{message}",
        )

    def test_deterministic_multi_file_chunk_outputs(self) -> None:
        # Chunk identity depends on sorted inputs and chunk size, not worker count.
        self.write_snapshot("a.gz", [{"id": "W1", "referenced_works": ["R1"]}])
        self.write_snapshot("b.gz", [{"id": "W2", "referenced_works": ["R2", "R3"]}])
        self.write_snapshot("c.gz", [{"id": "W3", "referenced_works": ["R4"]}])
        self.write_snapshot("d.gz", [{"id": "W4", "referenced_works": ["R5"]}])

        result = self.run_backfill("--files-per-chunk", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        parts = self.reference_parts()
        self.assertEqual([path.name for path in parts], [
            "part_refbackfill_000000_work_references.csv.gz",
            "part_refbackfill_000001_work_references.csv.gz",
        ])
        self.assertEqual(
            read_reference_rows(parts[0]),
            [("W1", "R1"), ("W2", "R2"), ("W2", "R3")],
        )
        self.assertEqual(
            read_reference_rows(parts[1]),
            [("W3", "R4"), ("W4", "R5")],
        )

    def test_chunk_with_no_references_commits_header_only_output(self) -> None:
        self.write_snapshot("a.gz", [{"id": "W1", "referenced_works": []}])
        self.write_snapshot("b.gz", [{"id": "not-in-subject", "referenced_works": ["R1"]}])

        result = self.run_backfill("--files-per-chunk", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        parts = self.reference_parts()
        self.assertEqual(len(parts), 2)
        for part in parts:
            with gzip.open(part, "rt", encoding="utf-8", newline="") as handle:
                self.assertEqual(next(csv.reader(handle)), ["work_id", "referenced_work_id"])
                self.assertEqual(list(csv.reader(handle)), [])

    def test_identical_rerun_skips_committed_chunks_and_preserves_mtimes(self) -> None:
        self.write_snapshot("a.gz", [{"id": "W1", "referenced_works": ["R1"]}])
        self.write_snapshot("b.gz", [{"id": "W2", "referenced_works": []}])
        first = self.run_backfill()
        self.assertEqual(first.returncode, 0, first.stderr)
        parts = self.reference_parts()
        before = {path.name: path.stat().st_mtime_ns for path in parts}

        time.sleep(0.02)
        second = self.run_backfill()
        self.assertEqual(second.returncode, 0, second.stderr)
        after = {path.name: path.stat().st_mtime_ns for path in self.reference_parts()}
        self.assertEqual(after, before)

    def test_snapshot_metadata_change_rejects_existing_plan(self) -> None:
        snapshot = self.write_snapshot(
            "a.gz", [{"id": "W1", "referenced_works": ["R1"]}]
        )
        first = self.run_backfill()
        self.assertEqual(first.returncode, 0, first.stderr)

        # Recreate the gzip with different content and force a distinct mtime as well.
        write_gzip_lines(
            snapshot,
            [json.dumps({"id": "W1", "referenced_works": ["R1", "R2"]})],
        )
        new_time = time.time_ns() + 1_000_000_000
        os.utime(snapshot, ns=(new_time, new_time))

        rerun = self.run_backfill()
        self.assert_failed_with(rerun, "plan", "snapshot", "metadata", "reset")

    def test_damaged_committed_output_is_rejected(self) -> None:
        self.write_snapshot("a.gz", [{"id": "W1", "referenced_works": ["R1"]}])
        first = self.run_backfill()
        self.assertEqual(first.returncode, 0, first.stderr)
        output = self.reference_parts()[0]
        output.write_bytes(output.read_bytes()[:12])

        rerun = self.run_backfill()
        self.assert_failed_with(rerun, "damaged", "corrupt", "invalid", "reset")

    def test_reset_preserves_unrelated_legacy_numeric_reference_parts(self) -> None:
        self.write_snapshot("a.gz", [{"id": "W1", "referenced_works": ["R1"]}])
        first = self.run_backfill()
        self.assertEqual(first.returncode, 0, first.stderr)

        legacy = self.table_parts / "part_9876_work_references.csv.gz"
        write_gzip_lines(legacy, [REFERENCE_HEADER.rstrip(), "LEGACY,R0"])
        legacy_bytes = legacy.read_bytes()
        legacy_mtime = legacy.stat().st_mtime_ns

        reset = self.run_backfill("--reset")
        self.assertEqual(reset.returncode, 0, reset.stderr)
        self.assertEqual(legacy.read_bytes(), legacy_bytes)
        self.assertEqual(legacy.stat().st_mtime_ns, legacy_mtime)
        self.assertEqual(read_reference_rows(legacy), [("LEGACY", "R0")])


if __name__ == "__main__":
    unittest.main()
