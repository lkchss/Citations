#!/usr/bin/env python3
"""Create streaming descriptive diagnostics for an exposure panel."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path


FIELDS = (
    "citations_jt",
    "accumulated_unrelated_citations_jt",
    "accumulated_related_citations_jt",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def summarize(values: list[float]) -> dict[str, float | int]:
    values.sort()
    n = len(values)
    if not n:
        return {"n": 0, "sum": 0, "mean": 0, "min": 0, "p50": 0, "p90": 0, "p99": 0, "max": 0, "zero_share": 0}

    def quantile(q: float) -> float:
        index = min(n - 1, int(q * (n - 1)))
        return values[index]

    return {
        "n": n,
        "sum": sum(values),
        "mean": sum(values) / n,
        "min": values[0],
        "p50": quantile(0.50),
        "p90": quantile(0.90),
        "p99": quantile(0.99),
        "max": values[-1],
        "zero_share": sum(value == 0 for value in values) / n,
    }


def main() -> int:
    parsed = parse_args()
    values = {field: [] for field in FIELDS}
    years: defaultdict[str, dict[str, object]] = defaultdict(lambda: {"rows": 0, "works": set(), "authors": set(), "paper_ages": []})
    works: set[str] = set()
    authors: set[str] = set()
    rows = 0
    prepublication = 0
    negative = 0
    with gzip.open(parsed.input, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            work_id = row.get("work_id", "")
            author_id = row.get("author_id", "")
            works.add(work_id)
            authors.add(author_id)
            year = row.get("year", "")
            bucket = years[year]
            bucket["rows"] += 1
            bucket["works"].add(work_id)
            bucket["authors"].add(author_id)
            age = int(row.get("paper_age") or 0)
            bucket["paper_ages"].append(age)
            if age < 0:
                prepublication += 1
            for field in FIELDS:
                value = float(row.get(field) or 0)
                values[field].append(value)
                if value < 0:
                    negative += 1

    year_summary = {}
    for year, bucket in sorted(years.items()):
        ages = sorted(bucket["paper_ages"])
        year_summary[year] = {
            "rows": bucket["rows"],
            "works": len(bucket["works"]),
            "authors": len(bucket["authors"]),
            "min_paper_age": ages[0] if ages else 0,
            "max_paper_age": ages[-1] if ages else 0,
        }
    result = {
        "input": str(parsed.input),
        "rows": rows,
        "works": len(works),
        "authors": len(authors),
        "prepublication_rows": prepublication,
        "negative_values": negative,
        "fields": {field: summarize(field_values) for field, field_values in values.items()},
        "by_year": year_summary,
    }
    parsed.output.parent.mkdir(parents=True, exist_ok=True)
    parsed.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("rows", "works", "authors", "prepublication_rows", "negative_values")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
