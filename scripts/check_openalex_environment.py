#!/usr/bin/env python3
"""Report OpenAlex disk, artifact, and job status.

This is intentionally read-only. It is useful after reboots or disk swaps when
the expected `/root/sdb1/openalex` data root may or may not be mounted.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_OPENALEX_ROOT = Path("/root/sdb1/openalex")
DEFAULT_REPO_DIR = Path("/root/sdb1/projects/Citations")
PROCESS_PATTERNS = (
    "build_subject_duckdb",
    "run_subject_duckdb_build",
    "backfill_subject_work_references",
    "run_reference_backfill",
    "build_subject_prevalence_regression_data",
    "run_pilot_lifetime_prevalence_regressions",
)


def run(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    return completed.returncode, completed.stdout.strip()


def path_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
    }
    if path.exists():
        stat = path.stat()
        info["size_bytes"] = stat.st_size
        info["mtime_epoch"] = int(stat.st_mtime)
    return info


def mount_info(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path)}
    code, output = run(["findmnt", "-T", str(path), "-no", "SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%,OPTIONS"])
    result["findmnt_exit_code"] = code
    result["findmnt"] = output
    code, output = run(["df", "-h", str(path)])
    result["df_exit_code"] = code
    result["df"] = output
    return result


def process_info() -> list[dict[str, str]]:
    code, output = run(["ps", "-eo", "pid,etime,%cpu,%mem,rss,cmd"])
    if code != 0:
        return [{"error": output}]
    matches = []
    for line in output.splitlines()[1:]:
        if any(pattern in line for pattern in PROCESS_PATTERNS):
            parts = line.split(None, 5)
            if len(parts) == 6:
                matches.append(
                    {
                        "pid": parts[0],
                        "etime": parts[1],
                        "cpu_percent": parts[2],
                        "mem_percent": parts[3],
                        "rss_kb": parts[4],
                        "cmd": parts[5],
                    }
                )
    return matches


def subject_reference_status(subject_root: Path, subject: str) -> dict[str, Any]:
    table_parts = subject_root / subject / "tables_parts"
    final_parts = sorted(table_parts.glob("part_*_work_references.csv.gz"))
    tmp_parts = sorted(table_parts.glob("part_*_work_references.csv.gz.tmp"))
    return {
        "subject": subject,
        "table_parts": str(table_parts),
        "table_parts_exists": table_parts.exists(),
        "final_reference_parts": len(final_parts),
        "tmp_reference_parts": len(tmp_parts),
        "final_reference_bytes": sum(path.stat().st_size for path in final_parts),
        "tmp_reference_bytes": sum(path.stat().st_size for path in tmp_parts),
        "tmp_reference_files": [str(path) for path in tmp_parts[:20]],
    }


def git_info(repo_dir: Path) -> dict[str, Any]:
    if not (repo_dir / ".git").exists():
        return {"repo_dir": str(repo_dir), "exists": repo_dir.exists(), "is_git_repo": False}
    info: dict[str, Any] = {"repo_dir": str(repo_dir), "is_git_repo": True}
    for key, command in {
        "status_short": ["git", "status", "--short"],
        "head": ["git", "rev-parse", "--short", "HEAD"],
        "branch": ["git", "branch", "--show-current"],
    }.items():
        code, output = run(command if command[0] != "git" else ["git", "-C", str(repo_dir), *command[1:]])
        info[key] = output if code == 0 else f"ERROR({code}): {output}"
    return info


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    openalex_root = args.openalex_root
    subject_root = openalex_root / "subjects"
    repo_dir = args.repo_dir
    artifacts = {
        "openalex_root": path_info(openalex_root),
        "snapshot_works": path_info(openalex_root / "snapshot" / "data" / "works"),
        "subject_root": path_info(subject_root),
        "subject_duckdb": path_info(subject_root / "subject_level.duckdb"),
        "subject_duckdb_summary": path_info(subject_root / "subject_level.duckdb.summary.json"),
        "duckdb_build_log": path_info(subject_root / "subject_level_duckdb_build.log"),
        "reference_sequential_log": path_info(subject_root / "reference_backfill_logs" / "sequential.log"),
    }
    subjects = args.subject or ["economics_econometrics_and_finance"]
    return {
        "openalex_root": str(openalex_root),
        "repo_dir": str(repo_dir),
        "cwd": os.getcwd(),
        "mounts": {
            "openalex_parent": mount_info(openalex_root.parent),
            "repo_parent": mount_info(repo_dir.parent),
        },
        "block_devices": run(["lsblk", "-f"])[1],
        "artifacts": artifacts,
        "processes": process_info(),
        "reference_status": [
            subject_reference_status(subject_root, subject)
            for subject in subjects
        ],
        "repo": git_info(repo_dir),
        "which_duckdb_python": shutil.which("python3"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openalex-root", type=Path, default=DEFAULT_OPENALEX_ROOT)
    parser.add_argument("--repo-dir", type=Path, default=DEFAULT_REPO_DIR)
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def print_text(report: dict[str, Any]) -> None:
    print(f"OpenAlex root: {report['openalex_root']}")
    print(f"Repo dir: {report['repo_dir']}")
    print()
    print("Mounts:")
    for name, info in report["mounts"].items():
        print(f"- {name}: {info.get('findmnt') or 'not found'}")
    print()
    print("Artifacts:")
    for name, info in report["artifacts"].items():
        size = info.get("size_bytes")
        suffix = f" size={size:,}" if size is not None else ""
        print(f"- {name}: exists={info['exists']} file={info['is_file']} dir={info['is_dir']}{suffix}")
    print()
    print("Processes:")
    if report["processes"]:
        for proc in report["processes"]:
            print(f"- pid={proc.get('pid')} etime={proc.get('etime')} rss_kb={proc.get('rss_kb')} cmd={proc.get('cmd')}")
    else:
        print("- none")
    print()
    print("Reference status:")
    for status in report["reference_status"]:
        print(
            f"- {status['subject']}: final_parts={status['final_reference_parts']} "
            f"tmp_parts={status['tmp_reference_parts']} "
            f"final_bytes={status['final_reference_bytes']:,} "
            f"tmp_bytes={status['tmp_reference_bytes']:,}"
        )
    print()
    repo = report["repo"]
    print(f"Repo: git={repo.get('is_git_repo')} branch={repo.get('branch', '')} head={repo.get('head', '')}")
    if repo.get("status_short"):
        print("Repo status:")
        print(repo["status_short"])


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
