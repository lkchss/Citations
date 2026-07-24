#!/usr/bin/env python3
"""Render full-sample prevalence regressions with absorbed paper/year effects."""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import math
from pathlib import Path

import numpy as np


def log(message: str) -> None:
    print(message, flush=True)


def int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def float_or_zero(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def read_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def count_rows(path: Path) -> int:
    rows = 0
    for _ in read_rows(path):
        rows += 1
    return rows


def create_memmaps(
    input_path: Path, work_dir: Path, row_count: int, *, transform: str
) -> dict[str, object]:
    work_dir.mkdir(parents=True, exist_ok=True)
    y = np.memmap(work_dir / "y.float64", dtype="float64", mode="w+", shape=(row_count,))
    x_unrelated = np.memmap(
        work_dir / "x_unrelated.float64", dtype="float64", mode="w+", shape=(row_count,)
    )
    x_related = np.memmap(
        work_dir / "x_related.float64", dtype="float64", mode="w+", shape=(row_count,)
    )
    work_idx = np.memmap(work_dir / "work_idx.int32", dtype="int32", mode="w+", shape=(row_count,))
    year_idx = np.memmap(work_dir / "year_idx.int16", dtype="int16", mode="w+", shape=(row_count,))

    work_codes: dict[str, int] = {}
    year_codes: dict[int, int] = {}
    author_ids: set[str] = set()
    idx = 0
    for row in read_rows(input_path):
        work_id = row["work_id"]
        year = int_or_zero(row["year"])
        if work_id not in work_codes:
            work_codes[work_id] = len(work_codes)
        if year not in year_codes:
            year_codes[year] = len(year_codes)
        author_id = row.get("author_id") or ""
        if author_id:
            author_ids.add(author_id)
        raw_values = [
            float_or_zero(row["citations_jt"]),
            float_or_zero(row["accumulated_unrelated_citations_jt"]),
            float_or_zero(row["accumulated_related_citations_jt"]),
        ]
        if transform == "log1p":
            raw_values = [float(np.log1p(value)) for value in raw_values]
        y[idx], x_unrelated[idx], x_related[idx] = raw_values
        work_idx[idx] = work_codes[work_id]
        year_idx[idx] = year_codes[year]
        idx += 1
        if idx % 10_000_000 == 0:
            log(f"loaded {idx:,} rows")

    for array in (y, x_unrelated, x_related, work_idx, year_idx):
        array.flush()
    return {
        "y": y,
        "x_unrelated": x_unrelated,
        "x_related": x_related,
        "work_idx": work_idx,
        "year_idx": year_idx,
        "works": len(work_codes),
        "years": len(year_codes),
        "authors": len(author_ids),
    }


def demean_inplace(
    residual: np.memmap,
    group_idx: np.memmap,
    group_count: np.ndarray,
    *,
    chunk_size: int,
) -> float:
    sums = np.bincount(group_idx, weights=residual, minlength=len(group_count))
    means = sums / group_count
    max_abs_mean = float(np.max(np.abs(means)))
    for start in range(0, len(residual), chunk_size):
        end = min(start + chunk_size, len(residual))
        residual[start:end] -= means[group_idx[start:end]]
    residual.flush()
    return max_abs_mean


def residualize(
    source: np.memmap,
    name: str,
    work_idx: np.memmap,
    year_idx: np.memmap,
    work_count: np.ndarray,
    year_count: np.ndarray,
    work_dir: Path,
    *,
    max_iter: int,
    tolerance: float,
    chunk_size: int,
) -> np.memmap:
    residual = np.memmap(
        work_dir / f"{name}_residual.float64", dtype="float64", mode="w+", shape=source.shape
    )
    grand_mean = float(np.mean(source))
    for start in range(0, len(source), chunk_size):
        end = min(start + chunk_size, len(source))
        residual[start:end] = source[start:end] - grand_mean
    residual.flush()

    for iteration in range(1, max_iter + 1):
        max_work = demean_inplace(residual, work_idx, work_count, chunk_size=chunk_size)
        max_year = demean_inplace(residual, year_idx, year_count, chunk_size=chunk_size)
        log(f"{name}: iteration {iteration}, max paper mean={max_work:.6g}, max year mean={max_year:.6g}")
        if max(max_work, max_year) < tolerance:
            break
    return residual


def crossprod(y: np.memmap, xs: list[np.memmap], *, chunk_size: int) -> tuple[np.ndarray, np.ndarray, float]:
    k = len(xs)
    xtx = np.zeros((k, k), dtype="float64")
    xty = np.zeros(k, dtype="float64")
    yty = 0.0
    for start in range(0, len(y), chunk_size):
        end = min(start + chunk_size, len(y))
        y_chunk = np.asarray(y[start:end])
        x_chunk = np.column_stack([np.asarray(x[start:end]) for x in xs])
        xtx += x_chunk.T @ x_chunk
        xty += x_chunk.T @ y_chunk
        yty += float(y_chunk.T @ y_chunk)
    return xtx, xty, yty


def estimate(
    y: np.memmap,
    xs: list[np.memmap],
    *,
    df_absorbed: int,
    cluster_idx: np.memmap | None,
    cluster_count: int,
    chunk_size: int,
) -> dict[str, object]:
    k = len(xs)
    xtx, xty, yty = crossprod(y, xs, chunk_size=chunk_size)
    inv_xtx = np.linalg.pinv(xtx)
    beta = inv_xtx @ xty
    sse = float(yty - beta.T @ xty)
    df_resid = max(1, len(y) - df_absorbed - len(xs))
    if cluster_idx is None:
        sigma2 = sse / df_resid
        vcov = sigma2 * inv_xtx
        inference = "normal-approximation, non-clustered"
    else:
        scores = np.zeros((cluster_count, k), dtype="float64")
        for start in range(0, len(y), chunk_size):
            end = min(start + chunk_size, len(y))
            group = np.asarray(cluster_idx[start:end])
            residual = np.asarray(y[start:end]) - np.column_stack(
                [np.asarray(x[start:end]) for x in xs]
            ) @ beta
            for column, x in enumerate(xs):
                scores[:, column] += np.bincount(
                    group, weights=np.asarray(x[start:end]) * residual,
                    minlength=cluster_count,
                )
        meat = scores.T @ scores
        correction = (cluster_count / max(1, cluster_count - 1)) * (
            (len(y) - 1) / max(1, df_resid)
        )
        vcov = correction * inv_xtx @ meat @ inv_xtx
        inference = f"work-clustered ({cluster_count:,} clusters)"
    se = np.sqrt(np.diag(vcov))
    t_stats = beta / se
    p_values = np.array([math.erfc(abs(float(t)) / math.sqrt(2.0)) for t in t_stats])
    r2 = 1.0 - sse / yty if yty else float("nan")
    return {
        "beta": beta.tolist(),
        "se": se.tolist(),
        "t": t_stats.tolist(),
        "p": p_values.tolist(),
        "n": len(y),
        "df_resid": df_resid,
        "r2_within": r2,
        "sse": sse,
        "inference": inference,
    }


def stars(p_value: float) -> str:
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.1:
        return "*"
    return ""


def fmt(value: float) -> str:
    if not math.isfinite(value):
        return ""
    if abs(value) < 0.0001 and value != 0:
        return f"{value:.3e}"
    return f"{value:.6f}"


def model_table(title: str, model1: dict[str, object], model2: dict[str, object]) -> str:
    names = [
        "Accumulated unrelated citations j,t",
        "Accumulated related citations j,t",
    ]
    rows = []
    for index, name in enumerate(names):
        cells = [html.escape(name)]
        if index == 0:
            cells.append(
                f"{fmt(model1['beta'][0])}{stars(model1['p'][0])}<br>"
                f"({fmt(model1['se'][0])})"
            )
            cells.append(
                f"{fmt(model2['beta'][0])}{stars(model2['p'][0])}<br>"
                f"({fmt(model2['se'][0])})"
            )
        else:
            cells.append("")
            cells.append(
                f"{fmt(model2['beta'][1])}{stars(model2['p'][1])}<br>"
                f"({fmt(model2['se'][1])})"
            )
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")

    rows.extend(
        [
            f"<tr><td>Observations</td><td>{model1['n']:,}</td><td>{model2['n']:,}</td></tr>",
            f"<tr><td>Within R-squared</td><td>{fmt(model1['r2_within'])}</td><td>{fmt(model2['r2_within'])}</td></tr>",
            "<tr><td>Paper fixed effects</td><td>Absorbed</td><td>Absorbed</td></tr>",
            "<tr><td>Year fixed effects</td><td>Absorbed</td><td>Absorbed</td></tr>",
        ]
    )
    return f"""
<h2>{html.escape(title)}</h2>
<table>
  <thead>
    <tr><th></th><th>Regression 1</th><th>Regression 2</th></tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
<p class="note">Standard errors in parentheses. Variables are residualized by paper and year before OLS. {html.escape(str(model2['inference']))}. Significance uses normal-approximation p-values: * p&lt;0.1, ** p&lt;0.05, *** p&lt;0.01.</p>
"""


def render_html(output: Path, summary: dict[str, object], model1: dict[str, object], model2: dict[str, object]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    content = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Full Economics Prevalence Regressions</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #111; }}
    table {{ border-collapse: collapse; margin: 16px 0 24px; min-width: 760px; }}
    th, td {{ border: 1px solid #bbb; padding: 8px 10px; text-align: right; vertical-align: top; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f2f2f2; }}
    .note {{ max-width: 900px; color: #444; font-size: 0.92rem; }}
  </style>
</head>
<body>
  <h1>Full Economics Prevalence Regressions</h1>
  <table>
    <tbody>
      <tr><td>Subject</td><td>{html.escape(str(summary["subject"]))}</td></tr>
      <tr><td>Observations</td><td>{summary["rows"]:,}</td></tr>
      <tr><td>Papers</td><td>{summary["works"]:,}</td></tr>
      <tr><td>Authors</td><td>{summary["authors"]:,}</td></tr>
      <tr><td>Citation source</td><td>{html.escape(str(summary["citation_source"]))}</td></tr>
      <tr><td>Transform</td><td>{html.escape(str(summary["transform"]))}</td></tr>
    </tbody>
  </table>
  {model_table("Economics", model1, model2)}
</body>
</html>
"""
    output.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--row-count", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=5_000_000)
    parser.add_argument("--max-iter", type=int, default=30)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    parser.add_argument(
        "--cluster-by-work",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use work-clustered standard errors (default: enabled)",
    )
    parser.add_argument("--transform", choices=("levels", "log1p"), default="levels")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    row_count = args.row_count or count_rows(args.input)
    log(f"row_count={row_count:,}")
    arrays = create_memmaps(args.input, args.work_dir, row_count, transform=args.transform)
    y = arrays["y"]
    x_unrelated = arrays["x_unrelated"]
    x_related = arrays["x_related"]
    work_idx = arrays["work_idx"]
    year_idx = arrays["year_idx"]
    work_count = np.bincount(work_idx, minlength=int(arrays["works"]))
    year_count = np.bincount(year_idx, minlength=int(arrays["years"]))

    y_res = residualize(
        y, "y", work_idx, year_idx, work_count, year_count, args.work_dir,
        max_iter=args.max_iter, tolerance=args.tolerance, chunk_size=args.chunk_size
    )
    x1_res = residualize(
        x_unrelated, "x_unrelated", work_idx, year_idx, work_count, year_count, args.work_dir,
        max_iter=args.max_iter, tolerance=args.tolerance, chunk_size=args.chunk_size
    )
    x2_res = residualize(
        x_related, "x_related", work_idx, year_idx, work_count, year_count, args.work_dir,
        max_iter=args.max_iter, tolerance=args.tolerance, chunk_size=args.chunk_size
    )

    df_absorbed = int(arrays["works"]) + int(arrays["years"]) - 1
    cluster_idx = work_idx if args.cluster_by_work else None
    model1 = estimate(
        y_res, [x1_res], df_absorbed=df_absorbed, cluster_idx=cluster_idx,
        cluster_count=int(arrays["works"]), chunk_size=args.chunk_size,
    )
    model2 = estimate(
        y_res, [x1_res, x2_res], df_absorbed=df_absorbed, cluster_idx=cluster_idx,
        cluster_count=int(arrays["works"]), chunk_size=args.chunk_size,
    )
    summary = {
        "subject": "economics_econometrics_and_finance",
        "rows": row_count,
        "works": int(arrays["works"]),
        "years": int(arrays["years"]),
        "authors": int(arrays["authors"]),
        "citation_source": "calculated_references",
        "inference": "work-clustered" if args.cluster_by_work else "non-clustered",
        "transform": args.transform,
        "model1": model1,
        "model2": model2,
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    render_html(args.output, summary, model1, model2)
    log(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
