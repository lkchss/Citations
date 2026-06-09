#!/usr/bin/env python3
"""Supervise and optimize the lifetime prevalence pilot pipeline.

This is a policy agent, not just a health monitor. It enforces an optimized
pilot configuration, terminates matching unoptimized pilot runs, relaunches the
optimized runner when needed, and records progress/ETA signals.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_REPO_DIR = Path("/root/sdb1/projects/Citations")
DEFAULT_DATA_ROOT = Path("/root/sdb1/openalex/subjects/prevalence_regressions_lifetime_pilot")
DEFAULT_LOG_DIR = Path("/root/sdb1/openalex/subjects/prevalence_regressions_lifetime_pilot_logs")
DEFAULT_REPORT = DEFAULT_REPO_DIR / "reports/subjects/lifetime_pilot_prevalence_regressions.html"
BUILD_SCRIPT = "scripts/build_subject_prevalence_regression_data.py"
RUNNER_SCRIPT = "scripts/run_pilot_lifetime_prevalence_regressions.sh"


@dataclass
class ProcessInfo:
    pid: int
    command: str
    state: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    print(f"{utc_now()} {message}", flush=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def process_state(pid: int) -> str:
    try:
        raw = read_text(Path(f"/proc/{pid}/stat"))
    except FileNotFoundError:
        return "?"
    close_paren = raw.rfind(")")
    return raw[close_paren + 2] if close_paren > 0 else "?"


def iter_processes() -> list[ProcessInfo]:
    processes: list[ProcessInfo] = []
    own_pid = os.getpid()
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        pid = int(path.name)
        if pid in {0, 1, own_pid}:
            continue
        try:
            command = read_text(path / "cmdline").replace("\0", " ").strip()
        except FileNotFoundError:
            continue
        if not command:
            continue
        processes.append(ProcessInfo(pid=pid, command=command, state=process_state(pid)))
    return processes


def matching_builds(data_root: Path) -> list[ProcessInfo]:
    data_root_text = str(data_root)
    return [
        process
        for process in iter_processes()
        if BUILD_SCRIPT in process.command
        and data_root_text in process.command
        and "codex-linux-sandbox" not in process.command
        and "bwrap" not in process.command
    ]


def matching_runners() -> list[ProcessInfo]:
    return [
        process
        for process in iter_processes()
        if RUNNER_SCRIPT in process.command
        and "codex-linux-sandbox" not in process.command
        and "bwrap" not in process.command
    ]


def terminate(process: ProcessInfo, *, reason: str) -> None:
    log(f"action=terminate pid={process.pid} reason={reason}")
    try:
        os.kill(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(5)
    if Path(f"/proc/{process.pid}").exists():
        try:
            os.kill(process.pid, signal.SIGKILL)
            log(f"action=kill pid={process.pid} reason={reason}")
        except ProcessLookupError:
            pass


def launch_runner(args: argparse.Namespace) -> None:
    env = os.environ.copy()
    env.update(
        {
            "SAMPLE_MOD": str(args.sample_mod),
            "SAMPLE_KEEP": str(args.sample_keep),
            "FOCAL_SAMPLE_MOD": str(args.focal_sample_mod),
            "FOCAL_SAMPLE_KEEP": str(args.focal_sample_keep),
            "REFERENCE_WORKERS": str(args.reference_workers),
            "REFERENCE_BACKEND": args.reference_backend,
            "SHARED_REFERENCE_SCAN": "0" if args.skip_reference_scan else "1",
            "SKIP_REFERENCE_SCAN": "1" if args.skip_reference_scan else "0",
            "DATA_ROOT": str(args.data_root),
            "LOG_DIR": str(args.log_dir),
            "REPORT": str(args.report),
        }
    )
    args.log_dir.mkdir(parents=True, exist_ok=True)
    launch_log = args.log_dir / "optimizer_launch.log"
    with launch_log.open("ab") as handle:
        process = subprocess.Popen(
            ["bash", RUNNER_SCRIPT],
            cwd=args.repo_dir,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    log(f"action=launch_optimized_runner pid={process.pid} launch_log={launch_log}")


def build_phase(build_log: Path) -> tuple[str, str]:
    if not build_log.exists():
        return "no_log", ""
    lines = read_text(build_log).splitlines()
    if not lines:
        return "empty_log", ""
    recent = "\n".join(lines[-200:])
    if "skip_reference_scan" in recent:
        return "writing_fast_pilot_outputs", lines[-1]
    if "shared reference scan found" in recent:
        return "writing_or_rendering", lines[-1]
    if "shared reference scan across" in recent:
        match = re.search(r"reference scan batch complete (\d+)/(\d+)", recent)
        if match:
            return f"shared_reference_scan_batch_{match.group(1)}_of_{match.group(2)}", lines[-1]
        return "shared_reference_scan", lines[-1]
    if re.search(r"\[[^\]]+\] sampling authors", recent):
        subjects_seen = len(re.findall(r"\[[^\]]+\] sampling authors", "\n".join(lines)))
        return f"preparing_subjects_seen_{subjects_seen}", lines[-1]
    return "unknown", lines[-1]


def report_progress(args: argparse.Namespace, builds: list[ProcessInfo]) -> None:
    phase, last_line = build_phase(args.log_dir / "build.log")
    required_flag = "--skip-reference-scan" if args.skip_reference_scan else "--shared-reference-scan"
    optimized = all(required_flag in build.command for build in builds)
    log(
        "status=supervising "
        f"build_pids={','.join(str(build.pid) for build in builds) or '-'} "
        f"optimized={optimized} required_flag={required_flag} phase={phase} last_line={last_line!r}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", type=Path, default=DEFAULT_REPO_DIR)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--sample-mod", type=int, default=1000)
    parser.add_argument("--sample-keep", type=int, default=1)
    parser.add_argument("--focal-sample-mod", type=int, default=4)
    parser.add_argument("--focal-sample-keep", type=int, default=1)
    parser.add_argument("--reference-workers", type=int, default=8)
    parser.add_argument("--reference-backend", choices=["auto", "process", "thread"], default="thread")
    parser.add_argument("--skip-reference-scan", action="store_true")
    parser.add_argument("--no-relaunch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log(
        "optimizer_start "
        f"data_root={args.data_root} sample_mod={args.sample_mod} "
        f"focal_sample_mod={args.focal_sample_mod} "
        f"reference_policy={'skip' if args.skip_reference_scan else 'shared'}"
    )
    while True:
        builds = matching_builds(args.data_root)
        if args.skip_reference_scan:
            unoptimized = [build for build in builds if "--skip-reference-scan" not in build.command]
        else:
            unoptimized = [build for build in builds if "--shared-reference-scan" not in build.command]
        for build in unoptimized:
            terminate(build, reason="wrong_reference_policy")

        builds = matching_builds(args.data_root)
        runners = matching_runners()
        report_progress(args, builds)

        if not args.no_relaunch and not builds and not runners and not args.report.exists():
            launch_runner(args)

        time.sleep(max(30.0, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
