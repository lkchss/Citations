#!/usr/bin/env python3
"""Fail fast on malformed or internally inconsistent ingestion outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise AssertionError(f"empty CSV: {path}")
    return rows


def finite(rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
    for row_number, row in enumerate(rows, 2):
        for column in columns:
            if not math.isfinite(float(row[column])):
                raise AssertionError(f"non-finite {column} at row {row_number}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory

    econ = csv_rows(root / "economics_event_time_tidy.csv")
    john = csv_rows(root / "john_list_fixed_cohort_tidy.csv")
    headline = csv_rows(root / "headline_results.csv")
    finite(econ, ("event_time", "estimate", "observations", "authors"))
    finite(john, ("year", "event_time", "mean_citations", "zero_share"))
    finite(headline, ("value",))
    assert len(econ) == 63, "expected 21 event years x 3 economics outcomes"
    assert {int(row["event_time"]) for row in econ} == set(range(-10, 11))
    assert all(row["causal"] == "0" for row in econ + john)
    assert all(0 <= float(row["zero_share"]) <= 1 for row in john)
    assert all(0 <= float(row["estimate"]) <= 1 for row in econ if row["outcome"] == "share_positive")
    for path in root.glob("*.svg"):
        ET.parse(path)

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    dictionary = json.loads((root / "data_dictionary.json").read_text(encoding="utf-8"))
    jsonl = [json.loads(line) for line in (root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(jsonl) == len(econ) + len(john) + len(headline)
    assert set(dictionary) >= {"headline_results.csv", "economics_event_time_tidy.csv", "john_list_fixed_cohort_tidy.csv"}
    assert manifest["causal_claim"] is False
    assert manifest["status"] == "exploratory_descriptive"
    names = {item["name"] for item in manifest["files"]}
    actual = {path.name for path in root.iterdir() if path.is_file() and path.name != "manifest.json"}
    assert names == actual, f"manifest mismatch: missing={actual-names}, extra={names-actual}"
    print(json.dumps({"status":"ok", "economics_rows":len(econ), "john_rows":len(john), "headline_rows":len(headline), "figures":len(list(root.glob('*.svg')))}, indent=2))


if __name__ == "__main__":
    main()
