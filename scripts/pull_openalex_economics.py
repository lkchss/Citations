#!/usr/bin/env python3
"""Pull OpenAlex works related to economics using cursor pagination."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


BASE_URL = "https://api.openalex.org/works"
ECONOMICS_FIELD_ID = "20"
DEFAULT_FILTER = f"primary_topic.field.id:{ECONOMICS_FIELD_ID}"
DEFAULT_OUTPUT_DIR = Path("/root/sdb1/openalex/economics_field20")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def iter_jsonl_gz(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def load_existing_work_ids(dirs: list[Path]) -> set[str]:
    existing_ids: set[str] = set()
    for directory in dirs:
        if not directory.exists():
            continue
        for record in iter_jsonl_gz(sorted(directory.glob("works_*.jsonl.gz"))):
            work_id = record.get("id")
            if work_id:
                existing_ids.add(str(work_id))
    return existing_ids


def request_json(params: dict[str, str], retries: int) -> dict[str, Any]:
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "lkchss-citations-openalex-puller/0.1",
    }
    request = urllib.request.Request(url, headers=headers)

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or 500 <= exc.code < 600:
                retry_after = exc.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(max(delay, 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt >= retries:
                raise
            time.sleep(max(2**attempt, 1))

    raise RuntimeError("request failed after retries")


def write_batch(output_dir: Path, batch_number: int, records: list[dict[str, Any]]) -> Path:
    path = output_dir / f"works_{batch_number:08d}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    return path


def build_filter(args: argparse.Namespace) -> str:
    filters = [args.openalex_filter or DEFAULT_FILTER]
    if args.from_publication_year:
        filters.append(f"publication_year:>{args.from_publication_year - 1}")
    if args.to_publication_year:
        filters.append(f"publication_year:<{args.to_publication_year + 1}")
    return ",".join(filters)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull economics-related OpenAlex works to compressed JSONL files."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=0, help="0 means run until exhausted.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds between successful pages.")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--mailto", default=os.getenv("OPENALEX_MAILTO", ""))
    parser.add_argument(
        "--filter",
        dest="openalex_filter",
        default="",
        help=f"Override the OpenAlex filter. Default: {DEFAULT_FILTER}.",
    )
    parser.add_argument("--from-publication-year", type=int, default=0)
    parser.add_argument("--to-publication-year", type=int, default=0)
    parser.add_argument(
        "--exclude-ids-dir",
        action="append",
        type=Path,
        default=[],
        help="Directory of existing works_*.jsonl.gz files whose OpenAlex IDs should be skipped.",
    )
    parser.add_argument(
        "--select",
        default="",
        help="Optional comma-separated root fields. Omit it to pull full OpenAlex Work records.",
    )
    parser.add_argument("--reset", action="store_true", help="Ignore any existing checkpoint.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)

    api_key = os.getenv("OPENALEX_API_KEY")
    if not api_key:
        print("OPENALEX_API_KEY is required. Put it in .env or export it.", file=sys.stderr)
        return 2

    if not (1 <= args.per_page <= 200):
        print("--per-page must be between 1 and 200", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    exclude_ids = load_existing_work_ids(args.exclude_ids_dir)
    if exclude_ids:
        print(f"{now_iso()} loaded {len(exclude_ids)} existing work IDs to skip", flush=True)

    checkpoint_path = args.output_dir / "checkpoint.json"
    checkpoint = {} if args.reset else read_checkpoint(checkpoint_path)

    cursor = checkpoint.get("next_cursor", "*")
    page_count = int(checkpoint.get("pages_completed", 0))
    total_records = int(checkpoint.get("records_written", 0))
    total_records_seen = int(checkpoint.get("records_seen", total_records))
    total_records_skipped = int(checkpoint.get("records_skipped_existing", 0))
    batch_number = int(checkpoint.get("next_batch_number", 1))
    openalex_filter = build_filter(args)

    checkpoint_filter = checkpoint.get("filter")
    if checkpoint_filter and checkpoint_filter != openalex_filter:
        print(
            f"Checkpoint filter {checkpoint_filter!r} does not match requested filter "
            f"{openalex_filter!r}. Use --reset or a different --output-dir.",
            file=sys.stderr,
        )
        return 2

    while True:
        if args.max_pages and page_count >= args.max_pages:
            break

        params = {
            "api_key": api_key,
            "filter": openalex_filter,
            "per_page": str(args.per_page),
            "cursor": cursor,
        }
        if args.select:
            params["select"] = args.select
        if args.mailto:
            params["mailto"] = args.mailto

        payload = request_json(params, args.retries)
        fetched_records = payload.get("results", [])
        meta = payload.get("meta", {})
        next_cursor = meta.get("next_cursor")

        if not fetched_records:
            checkpoint.update(
                {
                    "completed_at": now_iso(),
                    "next_cursor": next_cursor,
                    "pages_completed": page_count,
                    "records_written": total_records,
                    "records_seen": total_records_seen,
                    "records_skipped_existing": total_records_skipped,
                    "next_batch_number": batch_number,
                    "filter": openalex_filter,
                }
            )
            write_checkpoint(checkpoint_path, checkpoint)
            break

        records = []
        skipped_existing = 0
        for record in fetched_records:
            work_id = str(record.get("id") or "")
            if work_id and work_id in exclude_ids:
                skipped_existing += 1
                continue
            records.append(record)

        page_count += 1
        total_records_seen += len(fetched_records)
        total_records += len(records)
        total_records_skipped += skipped_existing
        batch_path = None
        if records:
            batch_path = write_batch(args.output_dir, batch_number, records)
            batch_number += 1
        cursor = next_cursor

        checkpoint = {
            "updated_at": now_iso(),
            "next_cursor": cursor,
            "pages_completed": page_count,
            "records_written": total_records,
            "records_seen": total_records_seen,
            "records_skipped_existing": total_records_skipped,
            "next_batch_number": batch_number,
            "last_batch": str(batch_path) if batch_path else checkpoint.get("last_batch"),
            "filter": openalex_filter,
            "per_page": args.per_page,
            "select": args.select or None,
            "exclude_ids_dirs": [str(path) for path in args.exclude_ids_dir],
        }
        write_checkpoint(checkpoint_path, checkpoint)
        if batch_path:
            print(
                f"{now_iso()} wrote {len(records)} records to {batch_path} "
                f"skipped_existing={skipped_existing}",
                flush=True,
            )
        else:
            print(
                f"{now_iso()} wrote 0 records skipped_existing={skipped_existing}",
                flush=True,
            )

        if not cursor:
            break
        time.sleep(args.sleep)

    print(f"Done. pages={page_count} records={total_records} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
