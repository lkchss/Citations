#!/usr/bin/env python3
"""Download OpenAlex snapshot files from the public S3 manifests."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_MANIFEST_URL = "https://openalex.s3.amazonaws.com/data/{entity}/manifest"
DEFAULT_OUTPUT_DIR = Path("/root/sdb1/openalex/snapshot")
DEFAULT_ENTITIES = (
    "works",
    "authors",
    "sources",
    "institutions",
    "topics",
    "fields",
    "subfields",
    "domains",
    "publishers",
    "funders",
)


@dataclass(frozen=True)
class SnapshotFile:
    url: str
    relative_path: Path
    size: int | None


def s3_to_https(url: str) -> str:
    if url.startswith("s3://openalex/"):
        return "https://openalex.s3.amazonaws.com/" + url.removeprefix("s3://openalex/")
    return url


def url_path(url: str) -> str:
    if url.startswith("s3://openalex/"):
        return url.removeprefix("s3://openalex/")
    prefix = "https://openalex.s3.amazonaws.com/"
    if url.startswith(prefix):
        return url.removeprefix(prefix)
    raise ValueError(f"Unsupported snapshot URL: {url}")


def fetch_json(url: str, timeout: int = 120) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def content_length(url: str, timeout: int = 120) -> int | None:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = response.headers.get("Content-Length")
            return int(value) if value else None
    except urllib.error.HTTPError:
        return None


def load_manifest(entity: str) -> list[SnapshotFile]:
    manifest_url = BASE_MANIFEST_URL.format(entity=entity)
    manifest = fetch_json(manifest_url)
    files: list[SnapshotFile] = []
    for entry in manifest.get("entries", []):
        raw_url = str(entry["url"])
        https_url = s3_to_https(raw_url)
        relative_path = Path(url_path(raw_url))
        size = entry.get("meta", {}).get("content_length")
        files.append(SnapshotFile(https_url, relative_path, int(size) if size else None))
    return files


def download_file(item: SnapshotFile, output_dir: Path, retries: int) -> dict[str, Any]:
    target = output_dir / item.relative_path
    target.parent.mkdir(parents=True, exist_ok=True)

    expected_size = item.size if item.size is not None else content_length(item.url)
    if target.exists() and expected_size is not None and target.stat().st_size == expected_size:
        return {"status": "skipped", "path": str(target), "bytes": expected_size}

    tmp_path = target.with_suffix(target.suffix + ".tmp")
    for attempt in range(retries + 1):
        try:
            downloaded = 0
            with urllib.request.urlopen(item.url, timeout=180) as response:
                with tmp_path.open("wb") as handle:
                    while True:
                        chunk = response.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
            if expected_size is not None and downloaded != expected_size:
                raise IOError(f"downloaded {downloaded} bytes, expected {expected_size}")
            tmp_path.replace(target)
            return {"status": "downloaded", "path": str(target), "bytes": downloaded}
        except Exception as exc:  # noqa: BLE001 - CLI should retry transient network errors.
            if attempt >= retries:
                return {"status": "failed", "path": str(target), "error": str(exc)}
            time.sleep(min(2**attempt, 30))

    return {"status": "failed", "path": str(target), "error": "unreachable"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download OpenAlex snapshot files.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--entity",
        action="append",
        choices=DEFAULT_ENTITIES,
        help="Entity to download. Repeat for multiple. Default: works only.",
    )
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-files", type=int, default=0, help="0 means all manifest files.")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument(
        "--largest-first",
        action="store_true",
        help="Download larger manifest files first so the worker queue stays balanced.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entities = args.entity or ["works"]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    files: list[SnapshotFile] = []
    for entity in entities:
        entity_files = load_manifest(entity)
        print(f"{entity}: {len(entity_files)} files in manifest", flush=True)
        files.extend(entity_files)

    if args.start_index:
        files = files[args.start_index :]
    if args.largest_first:
        files = sorted(files, key=lambda item: item.size or 0, reverse=True)
    if args.max_files:
        files = files[: args.max_files]

    manifest_path = args.output_dir / "download_manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "url": item.url,
                    "relative_path": str(item.relative_path),
                    "size": item.size,
                }
                for item in files
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    total_size = sum(item.size or 0 for item in files)
    print(f"selected_files={len(files)} known_bytes={total_size}", flush=True)
    print(f"manifest={manifest_path}", flush=True)
    if args.manifest_only:
        return 0

    completed = 0
    downloaded = 0
    skipped = 0
    failed = 0
    bytes_done = 0
    start = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_item = {
            executor.submit(download_file, item, args.output_dir, args.retries): item
            for item in files
        }
        for future in concurrent.futures.as_completed(future_to_item):
            result = future.result()
            completed += 1
            bytes_done += int(result.get("bytes") or 0)
            status = result["status"]
            if status == "downloaded":
                downloaded += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1

            elapsed = max(time.monotonic() - start, 0.001)
            mbps = bytes_done / elapsed / 1024 / 1024
            print(
                " ".join(
                    [
                        f"completed={completed}/{len(files)}",
                        f"downloaded={downloaded}",
                        f"skipped={skipped}",
                        f"failed={failed}",
                        f"mbps={mbps:.2f}",
                        f"last_status={status}",
                        f"path={result.get('path')}",
                    ]
                ),
                flush=True,
            )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
