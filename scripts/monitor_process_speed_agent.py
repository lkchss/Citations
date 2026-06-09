#!/usr/bin/env python3
"""Monitor long-running pipeline processes and guard against memory stalls.

The agent is intentionally conservative: it records process speed signals
(CPU, RSS, I/O, log growth, output growth) and only intervenes when available
memory crosses configured stop/resume thresholds.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
CLK_TCK = os.sysconf("SC_CLK_TCK")


@dataclass
class ProcSample:
    pid: int
    command: str
    state: str
    cpu_ticks: int
    rss_bytes: int
    read_bytes: int
    write_bytes: int


@dataclass
class FileSample:
    size: int
    mtime_ns: int


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    print(f"{utc_now()} {message}", flush=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_stat(path: Path) -> tuple[str, int, int, int]:
    raw = read_text(path)
    close_paren = raw.rfind(")")
    state = raw[close_paren + 2]
    fields = raw[close_paren + 4 :].split()
    utime = int(fields[10])
    stime = int(fields[11])
    rss_pages = int(fields[20])
    return state, utime, stime, rss_pages


def read_io(pid: int) -> tuple[int, int]:
    io_path = Path(f"/proc/{pid}/io")
    read_bytes = 0
    write_bytes = 0
    try:
        for line in read_text(io_path).splitlines():
            key, _, value = line.partition(":")
            if key == "read_bytes":
                read_bytes = int(value.strip())
            elif key == "write_bytes":
                write_bytes = int(value.strip())
    except FileNotFoundError:
        pass
    return read_bytes, write_bytes


def sample_process(pid: int) -> ProcSample | None:
    proc = Path(f"/proc/{pid}")
    try:
        command = read_text(proc / "cmdline").replace("\0", " ").strip()
        if not command:
            command = read_text(proc / "comm").strip()
        state, utime, stime, rss_pages = parse_stat(proc / "stat")
        read_bytes, write_bytes = read_io(pid)
    except (FileNotFoundError, ProcessLookupError, ValueError):
        return None
    return ProcSample(
        pid=pid,
        command=command,
        state=state,
        cpu_ticks=utime + stime,
        rss_bytes=rss_pages * PAGE_SIZE,
        read_bytes=read_bytes,
        write_bytes=write_bytes,
    )


def list_processes(
    *,
    pattern: re.Pattern[str] | None,
    exclude_pattern: re.Pattern[str],
    explicit_pids: set[int],
) -> list[ProcSample]:
    samples: list[ProcSample] = []
    own_pid = os.getpid()
    candidate_pids = set(explicit_pids)
    if pattern:
        for path in Path("/proc").iterdir():
            if path.name.isdigit():
                candidate_pids.add(int(path.name))
    for pid in sorted(candidate_pids):
        if pid in {0, 1, own_pid}:
            continue
        sample = sample_process(pid)
        if not sample or exclude_pattern.search(sample.command):
            continue
        if pid in explicit_pids or (pattern and pattern.search(sample.command)):
            samples.append(sample)
    return samples


def children_of(pids: set[int]) -> set[int]:
    children: set[int] = set()
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            raw = read_text(path / "stat")
            close_paren = raw.rfind(")")
            fields = raw[close_paren + 4 :].split()
            ppid = int(fields[0])
        except (FileNotFoundError, ValueError):
            continue
        if ppid in pids:
            children.add(int(path.name))
    return children


def expand_with_children(pids: set[int]) -> set[int]:
    expanded = set(pids)
    while True:
        new_children = children_of(expanded) - expanded
        if not new_children:
            return expanded
        expanded.update(new_children)


def mem_available_bytes() -> tuple[int, int, int]:
    values: dict[str, int] = {}
    for line in read_text(Path("/proc/meminfo")).splitlines():
        key, _, rest = line.partition(":")
        if key in {"MemAvailable", "SwapFree", "SwapTotal"}:
            values[key] = int(rest.strip().split()[0]) * 1024
    return (
        values.get("MemAvailable", 0),
        values.get("SwapFree", 0),
        values.get("SwapTotal", 0),
    )


def sample_file(path: Path | None) -> FileSample | None:
    if not path:
        return None
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return FileSample(size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def format_bytes(value: float) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(value)
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TiB"


def send_signal(pids: set[int], signum: signal.Signals, dry_run: bool) -> None:
    for pid in sorted(pids):
        if dry_run:
            log(f"dry_run signal={signum.name} pid={pid}")
            continue
        try:
            os.kill(pid, signum)
            log(f"sent signal={signum.name} pid={pid}")
        except ProcessLookupError:
            continue


def set_nice(pids: set[int], nice: int | None, dry_run: bool) -> None:
    if nice is None:
        return
    for pid in sorted(pids):
        if dry_run:
            log(f"dry_run set_nice pid={pid} nice={nice}")
            continue
        try:
            os.setpriority(os.PRIO_PROCESS, pid, nice)
            log(f"set_nice pid={pid} nice={nice}")
        except (PermissionError, ProcessLookupError, OSError) as error:
            log(f"set_nice_failed pid={pid} error={error}")


def set_ionice_idle(pids: set[int], dry_run: bool) -> None:
    for pid in sorted(pids):
        command = ["ionice", "-c3", "-p", str(pid)]
        if dry_run:
            log(f"dry_run ionice_idle pid={pid}")
            continue
        try:
            subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log(f"ionice_idle pid={pid}")
        except FileNotFoundError:
            log("ionice_missing")
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern",
        default="",
        help="Regex matched against process command lines.",
    )
    parser.add_argument("--pid", type=int, action="append", default=[], help="Explicit process PID to monitor.")
    parser.add_argument(
        "--exclude-pattern",
        default="monitor_process_speed_agent.py|codex-linux-sandbox|bwrap",
        help="Regex for command lines to ignore during pattern-based discovery.",
    )
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--low-mem-gb", type=float, default=1.5)
    parser.add_argument("--resume-mem-gb", type=float, default=4.0)
    parser.add_argument("--stall-seconds", type=float, default=1800.0)
    parser.add_argument("--nice", type=int)
    parser.add_argument("--ionice-idle", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.pattern and not args.pid:
        raise SystemExit("provide --pid or --pattern")
    pattern = re.compile(args.pattern) if args.pattern else None
    exclude_pattern = re.compile(args.exclude_pattern)
    explicit_pids = set(args.pid)
    low_mem = int(args.low_mem_gb * 1024**3)
    resume_mem = int(args.resume_mem_gb * 1024**3)
    previous: dict[int, ProcSample] = {}
    previous_log = sample_file(args.log_file)
    previous_output = sample_file(args.output_file)
    last_progress_time = time.monotonic()
    paused = False
    tuned_pids: set[int] = set()

    log(
        "agent_start "
        f"pattern={args.pattern!r} interval={args.interval_seconds}s "
        f"pids={','.join(str(pid) for pid in sorted(explicit_pids)) or '-'} "
        f"low_mem={format_bytes(low_mem)} resume_mem={format_bytes(resume_mem)}"
    )

    while True:
        loop_start = time.monotonic()
        samples = list_processes(
            pattern=pattern,
            exclude_pattern=exclude_pattern,
            explicit_pids=explicit_pids,
        )
        pids = {sample.pid for sample in samples}
        managed_pids = expand_with_children(pids)

        if not samples:
            log("status=no_matching_processes")
            return 0

        new_pids = managed_pids - tuned_pids
        if new_pids:
            set_nice(new_pids, args.nice, args.dry_run)
            if args.ionice_idle:
                set_ionice_idle(new_pids, args.dry_run)
            tuned_pids.update(new_pids)

        mem_available, swap_free, swap_total = mem_available_bytes()
        cpu_pct = 0.0
        read_rate = 0.0
        write_rate = 0.0
        interval = max(0.001, args.interval_seconds)
        for sample in samples:
            old = previous.get(sample.pid)
            if old:
                cpu_pct += ((sample.cpu_ticks - old.cpu_ticks) / CLK_TCK) / interval * 100
                read_rate += max(0, sample.read_bytes - old.read_bytes) / interval
                write_rate += max(0, sample.write_bytes - old.write_bytes) / interval
        rss_total = sum(sample.rss_bytes for sample in samples)

        current_log = sample_file(args.log_file)
        current_output = sample_file(args.output_file)
        log_delta = (
            current_log.size - previous_log.size
            if current_log and previous_log
            else 0
        )
        output_delta = (
            current_output.size - previous_output.size
            if current_output and previous_output
            else 0
        )
        if log_delta > 0 or output_delta > 0 or read_rate > 0 or write_rate > 0 or cpu_pct > 1:
            last_progress_time = loop_start

        states = "".join(sorted({sample.state for sample in samples}))
        log(
            "status=running "
            f"pids={','.join(str(pid) for pid in sorted(pids))} states={states} "
            f"cpu={cpu_pct:.1f}% rss={format_bytes(rss_total)} "
            f"read={format_bytes(read_rate)}/s write={format_bytes(write_rate)}/s "
            f"mem_available={format_bytes(mem_available)} swap_free={format_bytes(swap_free)} "
            f"log_delta={format_bytes(log_delta)} output_delta={format_bytes(output_delta)}"
        )

        if not paused and mem_available and mem_available < low_mem:
            log("action=pause reason=low_memory")
            send_signal(managed_pids, signal.SIGSTOP, args.dry_run)
            paused = True
        elif paused and mem_available > resume_mem:
            log("action=resume reason=memory_recovered")
            send_signal(managed_pids, signal.SIGCONT, args.dry_run)
            paused = False

        stalled_for = loop_start - last_progress_time
        if not paused and stalled_for >= args.stall_seconds:
            log(f"alert=possible_stall stalled_for={stalled_for:.0f}s")
            last_progress_time = loop_start

        previous = {sample.pid: sample for sample in samples}
        previous_log = current_log
        previous_output = current_output
        elapsed = time.monotonic() - loop_start
        time.sleep(max(1.0, args.interval_seconds - elapsed))


if __name__ == "__main__":
    raise SystemExit(main())
