#!/usr/bin/env python3
"""Resumably backfill subject work references in deterministic source chunks."""

from __future__ import annotations

import argparse
import csv
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SUBJECT_ROOT = Path("/root/sdb1/openalex/subjects")
DEFAULT_SNAPSHOT_WORKS_DIR = Path("/root/sdb1/openalex/snapshot/data/works")
SCHEMA = ["work_id", "referenced_work_id"]
PLAN_VERSION = 1


def log(message: str) -> None:
    print(f"{datetime.now(timezone.utc).isoformat()} {message}", file=sys.stderr, flush=True)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metadata(path: Path, root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": path.relative_to(root).as_posix(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def fingerprint(entries: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_bytes(entries)).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.{os.getpid()}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_work_ids(paths: list[Path]) -> set[str]:
    result: set[str] = set()
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                work_id = row.get("work_id") or ""
                if work_id:
                    result.add(work_id)
    return result


def output_name(chunk_id: int) -> str:
    return f"part_refbackfill_{chunk_id:06d}_work_references.csv.gz"


def validate_pair(manifest_path: Path, output_path: Path, plan_hash: str, chunk: dict[str, Any]) -> bool:
    try:
        manifest = read_json(manifest_path)
        if manifest.get("status") != "complete" or manifest.get("plan_sha256") != plan_hash:
            return False
        if manifest.get("chunk_id") != chunk["chunk_id"] or manifest.get("source_files") != chunk["source_files"]:
            return False
        if manifest.get("output") != output_path.name or manifest.get("output_size") != output_path.stat().st_size:
            return False
        if sha256_path(output_path) != manifest.get("output_sha256"):
            return False
        rows = 0
        with gzip.open(output_path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            if next(reader, None) != SCHEMA:
                return False
            rows = sum(1 for _ in reader)
        return rows == manifest.get("references_written")
    except (OSError, EOFError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def process_chunk(
    chunk: dict[str, Any], snapshot_root: Path, tables_parts: Path, state_dir: Path,
    work_ids: set[str], plan_hash: str,
) -> dict[str, Any]:
    chunk_id = chunk["chunk_id"]
    output = tables_parts / output_name(chunk_id)
    manifest_path = state_dir / "chunks" / f"{chunk_id:06d}.json"
    started = time.monotonic()
    records_seen = target_records_seen = references_written = 0
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{output.name}.{os.getpid()}.", suffix=".tmp", dir=tables_parts
    )
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with gzip.open(tmp, "wt", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(SCHEMA)
            for relative in chunk["source_files"]:
                with gzip.open(snapshot_root / relative, "rt", encoding="utf-8") as source:
                    for line in source:
                        if not line.strip():
                            continue
                        records_seen += 1
                        work = json.loads(line)
                        work_id = str(work.get("id") or "")
                        if work_id not in work_ids:
                            continue
                        target_records_seen += 1
                        for referenced_id in work.get("referenced_works") or []:
                            writer.writerow((work_id, str(referenced_id)))
                            references_written += 1
        output_sha256 = sha256_path(tmp)
        output_size = tmp.stat().st_size
        os.replace(tmp, output)
        manifest = {
            "version": PLAN_VERSION,
            "status": "complete",
            "chunk_id": chunk_id,
            "plan_sha256": plan_hash,
            "source_files": chunk["source_files"],
            "output": output.name,
            "output_size": output_size,
            "output_sha256": output_sha256,
            "records_seen": records_seen,
            "target_records_seen": target_records_seen,
            "references_written": references_written,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_json(manifest_path, manifest)
        if not validate_pair(manifest_path, output, plan_hash, chunk):
            raise RuntimeError(f"final validation failed for chunk {chunk_id:06d}")
        return manifest
    finally:
        tmp.unlink(missing_ok=True)


def make_plan(subject: str, snapshot_root: Path, source_paths: list[Path], works_paths: list[Path], files_per_chunk: int) -> dict[str, Any]:
    source_metadata = [metadata(path, snapshot_root) for path in source_paths]
    subject_root = works_paths[0].parent if works_paths else Path(".")
    works_metadata = [metadata(path, subject_root) for path in works_paths]
    chunks = [
        {
            "chunk_id": index,
            "source_files": [item["path"] for item in source_metadata[start:start + files_per_chunk]],
        }
        for index, start in enumerate(range(0, len(source_metadata), files_per_chunk))
    ]
    return {
        "version": PLAN_VERSION,
        "subject": subject,
        "files_per_chunk": files_per_chunk,
        "source_file_count": len(source_metadata),
        "source_metadata_fingerprint": fingerprint(source_metadata),
        "source_files_metadata": source_metadata,
        "subject_works_file_count": len(works_metadata),
        "subject_works_metadata_fingerprint": fingerprint(works_metadata),
        "subject_works_files_metadata": works_metadata,
        "chunks": chunks,
    }


def reset_managed(tables_parts: Path, state_dir: Path) -> None:
    for path in tables_parts.glob("part_refbackfill_*_work_references.csv.gz"):
        path.unlink()
    for path in tables_parts.glob(".part_refbackfill_*_work_references.csv.gz.*.tmp"):
        path.unlink()
    for child in state_dir.iterdir():
        if child.name == "lock":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def run_subject(args: argparse.Namespace, subject: str, source_paths: list[Path]) -> dict[str, Any]:
    tables_parts = args.subject_root / subject / "tables_parts"
    if not tables_parts.is_dir():
        raise SystemExit(f"Missing table parts for subject={subject}: {tables_parts}")
    works_paths = sorted(tables_parts.glob("part_*_works.csv.gz"))
    if not works_paths:
        raise SystemExit(f"No works parts for subject={subject}: {tables_parts}")
    state_dir = args.subject_root / subject / ".reference_backfill"
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(f"Reference backfill already running for subject={subject}")
        if args.reset:
            log(f"subject={subject} reset managed outputs and state")
            reset_managed(tables_parts, state_dir)

        proposed = make_plan(subject, args.snapshot_works_dir, source_paths, works_paths, args.files_per_chunk)
        plan_path = state_dir / "plan.json"
        if plan_path.exists():
            existing = read_json(plan_path)
            if existing != proposed:
                raise SystemExit(
                    f"Plan mismatch for subject={subject}; inputs/options changed. Use --reset to restart."
                )
            plan = existing
        else:
            atomic_json(plan_path, proposed)
            plan = proposed
        plan_hash = hashlib.sha256(canonical_bytes(plan)).hexdigest()
        work_ids = load_work_ids(works_paths)
        pending: list[dict[str, Any]] = []
        completed: list[dict[str, Any]] = []
        for chunk in plan["chunks"]:
            chunk_id = chunk["chunk_id"]
            manifest_path = state_dir / "chunks" / f"{chunk_id:06d}.json"
            output = tables_parts / output_name(chunk_id)
            if validate_pair(manifest_path, output, plan_hash, chunk):
                completed.append(read_json(manifest_path))
            elif manifest_path.exists():
                raise SystemExit(
                    f"Invalid or damaged committed chunk {chunk_id:06d} for subject={subject}; "
                    "inspect storage and use --reset to rebuild managed outputs."
                )
            else:
                pending.append(chunk)
        log(
            f"subject={subject} work_ids={len(work_ids):,} files={len(source_paths):,} "
            f"chunks={len(plan['chunks']):,} resume_valid={len(completed):,} pending={len(pending):,}"
        )
        workers = min(args.workers, len(pending)) if pending else 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(process_chunk, chunk, args.snapshot_works_dir, tables_parts, state_dir, work_ids, plan_hash): chunk
                for chunk in pending
            }
            for future in as_completed(futures):
                result = future.result()
                completed.append(result)
                log(
                    f"subject={subject} chunk={result['chunk_id']:06d} "
                    f"files={len(result['source_files'])} seen={result['records_seen']:,} "
                    f"targets={result['target_records_seen']:,} references={result['references_written']:,}"
                )
        completed.sort(key=lambda item: item["chunk_id"])
        if len(completed) != len(plan["chunks"]):
            raise RuntimeError(f"incomplete chunk set for subject={subject}")
        summary = {
            "version": PLAN_VERSION,
            "status": "complete",
            "subject": subject,
            "plan_sha256": plan_hash,
            "chunks": len(completed),
            "source_files": len(source_paths),
            "target_work_ids": len(work_ids),
            "records_seen": sum(item["records_seen"] for item in completed),
            "target_records_seen": sum(item["target_records_seen"] for item in completed),
            "references_written": sum(item["references_written"] for item in completed),
            "output_bytes": sum(item["output_size"] for item in completed),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_json(state_dir / "summary.json", summary)
        log(f"subject={subject} complete chunks={len(completed):,} references={summary['references_written']:,}")
        return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-root", type=Path, default=DEFAULT_SUBJECT_ROOT)
    parser.add_argument("--snapshot-works-dir", type=Path, default=DEFAULT_SNAPSHOT_WORKS_DIR)
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--files-per-chunk", type=int, default=8)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-files", type=int, default=0, help="Use only the first N sorted snapshot files (pilot runs).")
    parser.add_argument("--reset", action="store_true", help="Remove only resumable backfill outputs/state before starting.")
    args = parser.parse_args()
    if args.files_per_chunk < 1 or args.workers < 1 or args.max_files < 0:
        parser.error("--files-per-chunk and --workers must be positive; --max-files cannot be negative")
    return args


def main() -> int:
    args = parse_args()
    if not args.snapshot_works_dir.is_dir():
        raise SystemExit(f"Missing snapshot works directory: {args.snapshot_works_dir}")
    subjects = args.subject or [path.parent.name for path in sorted(args.subject_root.glob("*/tables_parts"))]
    if not subjects:
        raise SystemExit("No subjects selected")
    source_paths = sorted(args.snapshot_works_dir.rglob("*.gz"))
    if args.max_files:
        source_paths = source_paths[:args.max_files]
    if not source_paths:
        raise SystemExit("No snapshot work files selected")
    summaries = [run_subject(args, subject, source_paths) for subject in subjects]
    print(json.dumps({"subjects": summaries}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
