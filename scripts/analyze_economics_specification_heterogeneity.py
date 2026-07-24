#!/usr/bin/env python3
"""Estimate the two economics exposure models across age and cohort groups."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-svg", type=Path, required=True)
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    return parser.parse_args()


def load_panel(path: Path) -> dict[str, np.ndarray]:
    columns: dict[str, list[object]] = {
        "work_id": [],
        "year": [],
        "publication_year": [],
        "paper_age": [],
        "y": [],
        "unrelated": [],
        "related": [],
    }
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            columns["work_id"].append(row["work_id"])
            columns["year"].append(int(row["year"]))
            columns["publication_year"].append(int(row["publication_year"]))
            columns["paper_age"].append(int(row["paper_age"]))
            columns["y"].append(float(row["citations_jt"]))
            columns["unrelated"].append(float(row["accumulated_unrelated_citations_jt"]))
            columns["related"].append(float(row["accumulated_related_citations_jt"]))
    return {
        "work_id": np.asarray(columns["work_id"], dtype=object),
        "year": np.asarray(columns["year"], dtype=np.int16),
        "publication_year": np.asarray(columns["publication_year"], dtype=np.int16),
        "paper_age": np.asarray(columns["paper_age"], dtype=np.int16),
        "y": np.asarray(columns["y"], dtype=np.float64),
        "unrelated": np.asarray(columns["unrelated"], dtype=np.float64),
        "related": np.asarray(columns["related"], dtype=np.float64),
    }


def codes(values: np.ndarray) -> tuple[np.ndarray, int]:
    _, encoded = np.unique(values, return_inverse=True)
    return encoded.astype(np.int32), int(encoded.max()) + 1 if len(encoded) else 0


def residualize(
    source: np.ndarray,
    work_idx: np.ndarray,
    year_idx: np.ndarray,
    work_count: int,
    year_count: int,
    *,
    max_iter: int,
    tolerance: float,
) -> np.ndarray:
    residual = source.astype(np.float64, copy=True)
    residual -= residual.mean()
    work_n = np.bincount(work_idx, minlength=work_count)
    year_n = np.bincount(year_idx, minlength=year_count)
    for _ in range(max_iter):
        work_means = np.bincount(work_idx, weights=residual, minlength=work_count) / work_n
        residual -= work_means[work_idx]
        year_means = np.bincount(year_idx, weights=residual, minlength=year_count) / year_n
        residual -= year_means[year_idx]
        if max(float(np.max(np.abs(work_means))), float(np.max(np.abs(year_means)))) < tolerance:
            break
    return residual


def estimate(
    y: np.ndarray,
    xs: list[np.ndarray],
    work_idx: np.ndarray,
    work_count: int,
    df_absorbed: int,
) -> dict[str, object]:
    x = np.column_stack(xs)
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ (x.T @ y)
    error = y - x @ beta
    scores = np.zeros((work_count, len(xs)), dtype=np.float64)
    for column in range(len(xs)):
        scores[:, column] = np.bincount(
            work_idx, weights=x[:, column] * error, minlength=work_count
        )
    df_resid = max(1, len(y) - df_absorbed - len(xs))
    correction = (work_count / max(1, work_count - 1)) * ((len(y) - 1) / df_resid)
    vcov = correction * xtx_inv @ (scores.T @ scores) @ xtx_inv
    se = np.sqrt(np.maximum(0.0, np.diag(vcov)))
    p = [math.erfc(abs(float(b / s)) / math.sqrt(2.0)) if s else 1.0 for b, s in zip(beta, se)]
    return {
        "beta": beta.tolist(),
        "se": se.tolist(),
        "p": p,
        "ci_low": (beta - 1.96 * se).tolist(),
        "ci_high": (beta + 1.96 * se).tolist(),
    }


def analyze_group(
    data: dict[str, np.ndarray],
    mask: np.ndarray,
    *,
    dimension: str,
    group: str,
    max_iter: int,
    tolerance: float,
) -> dict[str, object]:
    work_ids = data["work_id"][mask]
    work_idx, work_count = codes(work_ids)
    year_idx, year_count = codes(data["year"][mask])
    y = residualize(
        data["y"][mask], work_idx, year_idx, work_count, year_count,
        max_iter=max_iter, tolerance=tolerance,
    )
    unrelated = residualize(
        data["unrelated"][mask], work_idx, year_idx, work_count, year_count,
        max_iter=max_iter, tolerance=tolerance,
    )
    related = residualize(
        data["related"][mask], work_idx, year_idx, work_count, year_count,
        max_iter=max_iter, tolerance=tolerance,
    )
    df_absorbed = work_count + year_count - 1
    model1 = estimate(y, [unrelated], work_idx, work_count, df_absorbed)
    model2 = estimate(y, [unrelated, related], work_idx, work_count, df_absorbed)
    return {
        "dimension": dimension,
        "group": group,
        "rows": int(mask.sum()),
        "works": work_count,
        "years": year_count,
        "model1": model1,
        "model2": model2,
    }


def flatten(results: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for result in results:
        for model_name, names in (("model1", ["unrelated"]), ("model2", ["unrelated", "related"])):
            model = result[model_name]
            for index, variable in enumerate(names):
                rows.append(
                    {
                        "dimension": result["dimension"],
                        "group": result["group"],
                        "model": model_name,
                        "variable": variable,
                        "coefficient": model["beta"][index],
                        "standard_error": model["se"][index],
                        "p_value": model["p"][index],
                        "ci_low": model["ci_low"][index],
                        "ci_high": model["ci_high"][index],
                        "rows": result["rows"],
                        "works": result["works"],
                    }
                )
    return rows


def write_svg(path: Path, rows: list[dict[str, object]]) -> None:
    panels = [
        ("paper_age", "Unrelated coefficient by paper age", "unrelated"),
        ("paper_age", "Related coefficient by paper age", "related"),
        ("publication_cohort", "Unrelated coefficient by cohort", "unrelated"),
        ("publication_cohort", "Related coefficient by cohort", "related"),
    ]
    colors = {"model1": "#1769aa", "model2": "#c2410c"}
    width, height = 1040, 700
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>.title{font:700 20px sans-serif;fill:#111827}.panel{font:700 15px sans-serif;fill:#111827}.axis{font:12px sans-serif;fill:#374151}.grid{stroke:#e5e7eb}.zero{stroke:#6b7280;stroke-dasharray:4 4}.ci{stroke-width:2}.note{font:13px sans-serif;fill:#4b5563}</style>',
        '<text x="38" y="34" class="title">Economics exposure heterogeneity</text>',
        '<text x="38" y="56" class="note">Paper and year fixed effects re-estimated within each group; 95% work-clustered intervals</text>',
    ]
    for panel_index, (dimension, title, variable) in enumerate(panels):
        col = panel_index % 2
        row_index = panel_index // 2
        px = 38 + col * 500
        py = 92 + row_index * 285
        panel_rows = [r for r in rows if r["dimension"] == dimension and r["variable"] == variable]
        if variable == "related":
            panel_rows = [r for r in panel_rows if r["model"] == "model2"]
        values = [float(r[key]) for r in panel_rows for key in ("ci_low", "ci_high")]
        lo, hi = min(values + [0.0]), max(values + [0.0])
        span = max(1e-8, hi - lo)
        lo -= span * 0.12
        hi += span * 0.12
        left, right, top, bottom = px + 138, px + 462, py + 34, py + 226

        def x(value: float) -> float:
            return left + (value - lo) / (hi - lo) * (right - left)

        groups = list(dict.fromkeys(str(r["group"]) for r in panel_rows))
        elements.append(f'<text x="{px}" y="{py}" class="panel">{title}</text>')
        elements.append(f'<line x1="{x(0):.1f}" y1="{top}" x2="{x(0):.1f}" y2="{bottom}" class="zero"/>')
        for group_index, group in enumerate(groups):
            gy = top + 35 + group_index * 48
            elements.append(f'<text x="{px + 128}" y="{gy + 4}" text-anchor="end" class="axis">{group}</text>')
            matches = [r for r in panel_rows if r["group"] == group]
            for match_index, match in enumerate(matches):
                y = gy + (match_index - (len(matches) - 1) / 2) * 13
                color = colors[str(match["model"])]
                elements.append(
                    f'<line x1="{x(float(match["ci_low"])):.1f}" y1="{y:.1f}" '
                    f'x2="{x(float(match["ci_high"])):.1f}" y2="{y:.1f}" '
                    f'class="ci" stroke="{color}"/>'
                )
                elements.append(
                    f'<circle cx="{x(float(match["coefficient"])):.1f}" cy="{y:.1f}" '
                    f'r="4" fill="{color}"/>'
                )
        elements.append(f'<text x="{left}" y="{bottom + 24}" class="axis">{lo:.4g}</text>')
        elements.append(f'<text x="{right}" y="{bottom + 24}" text-anchor="end" class="axis">{hi:.4g}</text>')
    elements.extend(
        [
            '<circle cx="390" cy="674" r="4" fill="#1769aa"/><text x="402" y="678" class="note">Model 1: unrelated only</text>',
            '<circle cx="590" cy="674" r="4" fill="#c2410c"/><text x="602" y="678" class="note">Model 2: unrelated + related</text>',
            "</svg>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    data = load_panel(args.input)
    groups = [
        ("paper_age", "1-5", (data["paper_age"] >= 1) & (data["paper_age"] <= 5)),
        ("paper_age", "6-10", (data["paper_age"] >= 6) & (data["paper_age"] <= 10)),
        ("paper_age", "11+", data["paper_age"] >= 11),
        ("publication_cohort", "1990s", (data["publication_year"] >= 1990) & (data["publication_year"] <= 1999)),
        ("publication_cohort", "2000s", (data["publication_year"] >= 2000) & (data["publication_year"] <= 2009)),
        ("publication_cohort", "2010s", (data["publication_year"] >= 2010) & (data["publication_year"] <= 2019)),
    ]
    results = [
        analyze_group(
            data, mask, dimension=dimension, group=group,
            max_iter=args.max_iter, tolerance=args.tolerance,
        )
        for dimension, group, mask in groups
    ]
    rows = flatten(results)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps({"input": str(args.input), "results": results}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    write_svg(args.output_svg, rows)
    print(json.dumps({"groups": len(results), "rows": len(rows), "output": str(args.output_json)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
