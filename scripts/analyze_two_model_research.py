#!/usr/bin/env python3
"""Independent analysis of the two economics fixed-effects models."""

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
    parser.add_argument("--coefficient-svg", type=Path, required=True)
    parser.add_argument("--relationship-svg", type=Path, required=True)
    parser.add_argument("--bins", type=int, default=20)
    return parser.parse_args()


def load_panel(path: Path) -> dict[str, np.ndarray]:
    values: dict[str, list[object]] = {
        "author_id": [],
        "work_id": [],
        "year": [],
        "paper_age": [],
        "y": [],
        "unrelated": [],
        "related": [],
    }
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            values["author_id"].append(row["author_id"])
            values["work_id"].append(row["work_id"])
            values["year"].append(int(row["year"]))
            values["paper_age"].append(int(row["paper_age"]))
            values["y"].append(float(row["citations_jt"]))
            values["unrelated"].append(float(row["accumulated_unrelated_citations_jt"]))
            values["related"].append(float(row["accumulated_related_citations_jt"]))
    return {
        "author_id": np.asarray(values["author_id"], dtype=object),
        "work_id": np.asarray(values["work_id"], dtype=object),
        "year": np.asarray(values["year"], dtype=np.int16),
        "paper_age": np.asarray(values["paper_age"], dtype=np.int16),
        "y": np.asarray(values["y"], dtype=np.float64),
        "unrelated": np.asarray(values["unrelated"], dtype=np.float64),
        "related": np.asarray(values["related"], dtype=np.float64),
    }


def encode(values: np.ndarray) -> tuple[np.ndarray, int]:
    _, result = np.unique(values, return_inverse=True)
    return result.astype(np.int32), int(result.max()) + 1 if len(result) else 0


def residualize(
    source: np.ndarray,
    work_idx: np.ndarray,
    year_idx: np.ndarray,
    work_count: int,
    year_count: int,
    *,
    tolerance: float = 1e-9,
    max_iter: int = 100,
) -> np.ndarray:
    result = source.astype(np.float64, copy=True)
    result -= result.mean()
    work_n = np.bincount(work_idx, minlength=work_count)
    year_n = np.bincount(year_idx, minlength=year_count)
    for _ in range(max_iter):
        work_mean = np.bincount(work_idx, weights=result, minlength=work_count) / work_n
        result -= work_mean[work_idx]
        year_mean = np.bincount(year_idx, weights=result, minlength=year_count) / year_n
        result -= year_mean[year_idx]
        if max(float(np.abs(work_mean).max()), float(np.abs(year_mean).max())) < tolerance:
            break
    return result


def fit(
    y: np.ndarray,
    xs: list[np.ndarray],
    work_idx: np.ndarray,
    work_count: int,
    year_count: int,
) -> dict[str, object]:
    x = np.column_stack(xs)
    inv = np.linalg.pinv(x.T @ x)
    beta = inv @ (x.T @ y)
    error = y - x @ beta
    score = np.zeros((work_count, len(xs)), dtype=np.float64)
    for index in range(len(xs)):
        score[:, index] = np.bincount(
            work_idx, weights=x[:, index] * error, minlength=work_count
        )
    df_absorbed = work_count + year_count - 1
    df_resid = max(1, len(y) - df_absorbed - len(xs))
    correction = (work_count / max(1, work_count - 1)) * ((len(y) - 1) / df_resid)
    vcov = correction * inv @ (score.T @ score) @ inv
    se = np.sqrt(np.maximum(0, np.diag(vcov)))
    p = [math.erfc(abs(float(b / s)) / math.sqrt(2)) if s else 1.0 for b, s in zip(beta, se)]
    sse = float(error @ error)
    yty = float(y @ y)
    return {
        "beta": beta.tolist(),
        "se": se.tolist(),
        "p": p,
        "ci_low": (beta - 1.96 * se).tolist(),
        "ci_high": (beta + 1.96 * se).tolist(),
        "sse": sse,
        "within_r2": 1 - sse / yty if yty else None,
    }


def balanced_age_mask(data: dict[str, np.ndarray], first: int, last: int) -> np.ndarray:
    unit = np.char.add(
        np.char.add(data["author_id"].astype(str), "|"),
        data["work_id"].astype(str),
    )
    eligible = (data["paper_age"] >= first) & (data["paper_age"] <= last)
    ages_by_unit: dict[str, set[int]] = {}
    for unit_id, age in zip(unit[eligible], data["paper_age"][eligible]):
        ages_by_unit.setdefault(str(unit_id), set()).add(int(age))
    required = set(range(first, last + 1))
    balanced = {unit_id for unit_id, ages in ages_by_unit.items() if ages == required}
    return eligible & np.fromiter((str(unit_id) in balanced for unit_id in unit), dtype=bool)


def analyze_variant(
    name: str,
    label: str,
    data: dict[str, np.ndarray],
    mask: np.ndarray,
    *,
    winsorize: tuple[str, ...] = (),
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    work_idx, work_count = encode(data["work_id"][mask])
    year_idx, year_count = encode(data["year"][mask])
    raw = {
        key: data[key][mask].astype(np.float64, copy=True)
        for key in ("y", "unrelated", "related")
    }
    cutoffs = {}
    if winsorize:
        for key in winsorize:
            cutoff = float(np.quantile(raw[key], 0.99))
            raw[key] = np.minimum(raw[key], cutoff)
            cutoffs[key] = cutoff
    residuals = {
        key: residualize(value, work_idx, year_idx, work_count, year_count)
        for key, value in raw.items()
    }
    model1 = fit(
        residuals["y"], [residuals["unrelated"]], work_idx, work_count, year_count
    )
    model2 = fit(
        residuals["y"],
        [residuals["unrelated"], residuals["related"]],
        work_idx,
        work_count,
        year_count,
    )
    partial_r2_related = (
        (float(model1["sse"]) - float(model2["sse"])) / float(model1["sse"])
        if float(model1["sse"])
        else None
    )
    result = {
        "name": name,
        "label": label,
        "rows": int(mask.sum()),
        "works": work_count,
        "years": year_count,
        "winsor_cutoffs": cutoffs,
        "within_correlation_exposures": float(
            np.corrcoef(residuals["unrelated"], residuals["related"])[0, 1]
        ),
        "partial_r2_related": partial_r2_related,
        "model1": model1,
        "model2": model2,
    }
    residuals["work_idx"] = work_idx
    return result, residuals


def quantile_bins(x: np.ndarray, y: np.ndarray, bins: int) -> list[dict[str, float | int]]:
    order = np.argsort(x)
    output = []
    for indices in np.array_split(order, bins):
        if len(indices):
            output.append(
                {
                    "x": float(x[indices].mean()),
                    "y": float(y[indices].mean()),
                    "n": int(len(indices)),
                }
            )
    return output


def partial_out(target: np.ndarray, control: np.ndarray) -> np.ndarray:
    denominator = float(control @ control)
    return target - control * (float(control @ target) / denominator) if denominator else target.copy()


def flatten(variants: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for variant in variants:
        for model_name, variables in (("model1", ["unrelated"]), ("model2", ["unrelated", "related"])):
            model = variant[model_name]
            for index, variable in enumerate(variables):
                rows.append(
                    {
                        "variant": variant["name"],
                        "label": variant["label"],
                        "model": model_name,
                        "variable": variable,
                        "coefficient": model["beta"][index],
                        "standard_error": model["se"][index],
                        "p_value": model["p"][index],
                        "ci_low": model["ci_low"][index],
                        "ci_high": model["ci_high"][index],
                        "within_r2": model["within_r2"],
                        "rows": variant["rows"],
                        "works": variant["works"],
                    }
                )
    return rows


def coefficient_svg(path: Path, rows: list[dict[str, object]]) -> None:
    panels = [("unrelated", "Unrelated exposure"), ("related", "Related exposure")]
    colors = {"model1": "#1769aa", "model2": "#c2410c"}
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="650" viewBox="0 0 1000 650" role="img">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>.title{font:700 20px sans-serif;fill:#111827}.panel{font:700 15px sans-serif;fill:#111827}.axis{font:12px sans-serif;fill:#374151}.note{font:13px sans-serif;fill:#4b5563}.zero{stroke:#6b7280;stroke-dasharray:4 4}.ci{stroke-width:2}</style>',
        '<text x="38" y="34" class="title">Two-model coefficient stability</text>',
        '<text x="38" y="57" class="note">95% work-clustered intervals; the balanced panel contains paper ages 1–5 for every retained paper-author unit</text>',
    ]
    for panel_index, (variable, title) in enumerate(panels):
        px = 38 + panel_index * 485
        panel_rows = [row for row in rows if row["variable"] == variable]
        if variable == "related":
            panel_rows = [row for row in panel_rows if row["model"] == "model2"]
        values = [float(row[key]) for row in panel_rows for key in ("ci_low", "ci_high")]
        lo, hi = min(values + [0]), max(values + [0])
        span = max(1e-8, hi - lo)
        lo -= span * 0.1
        hi += span * 0.1
        left, right, top, bottom = px + 150, px + 450, 105, 530

        def x(value: float) -> float:
            return left + (value - lo) / (hi - lo) * (right - left)

        elements.append(f'<text x="{px}" y="88" class="panel">{title}</text>')
        elements.append(f'<line x1="{x(0):.1f}" y1="{top}" x2="{x(0):.1f}" y2="{bottom}" class="zero"/>')
        variants = list(dict.fromkeys(str(row["label"]) for row in panel_rows))
        for variant_index, label in enumerate(variants):
            base_y = top + 45 + variant_index * 82
            elements.append(f'<text x="{px + 138}" y="{base_y + 4}" text-anchor="end" class="axis">{label}</text>')
            matches = [row for row in panel_rows if row["label"] == label]
            for match_index, match in enumerate(matches):
                y = base_y + (match_index - (len(matches) - 1) / 2) * 16
                color = colors[str(match["model"])]
                elements.append(
                    f'<line x1="{x(float(match["ci_low"])):.1f}" y1="{y:.1f}" '
                    f'x2="{x(float(match["ci_high"])):.1f}" y2="{y:.1f}" '
                    f'class="ci" stroke="{color}"/>'
                )
                elements.append(
                    f'<circle cx="{x(float(match["coefficient"])):.1f}" cy="{y:.1f}" '
                    f'r="4.5" fill="{color}"/>'
                )
        elements.append(f'<text x="{left}" y="558" class="axis">{lo:.4g}</text>')
        elements.append(f'<text x="{right}" y="558" text-anchor="end" class="axis">{hi:.4g}</text>')
    elements.extend(
        [
            '<circle cx="345" cy="612" r="4" fill="#1769aa"/><text x="357" y="616" class="note">Model 1</text>',
            '<circle cx="485" cy="612" r="4" fill="#c2410c"/><text x="497" y="616" class="note">Model 2</text>',
            "</svg>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def relationship_svg(path: Path, relationships: list[dict[str, object]]) -> None:
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1110" height="460" viewBox="0 0 1110 460" role="img">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>.title{font:700 20px sans-serif;fill:#111827}.panel{font:700 14px sans-serif;fill:#111827}.axis{font:11px sans-serif;fill:#374151}.note{font:13px sans-serif;fill:#4b5563}.grid{stroke:#e5e7eb}.line{stroke:#c2410c;stroke-width:2}.point{fill:#1769aa}</style>',
        '<text x="38" y="34" class="title">Within-paper exposure relationships</text>',
        '<text x="38" y="57" class="note">Equal-count bins after absorbing paper and year effects; Model 2 panels partial out the other exposure</text>',
    ]
    for panel_index, relationship in enumerate(relationships):
        px = 30 + panel_index * 360
        points = relationship["points"]
        xs = [float(point["x"]) for point in points]
        ys = [float(point["y"]) for point in points]
        x_lo, x_hi = min(xs), max(xs)
        y_lo, y_hi = min(ys), max(ys)
        x_span = max(1e-8, x_hi - x_lo)
        y_span = max(1e-8, y_hi - y_lo)
        x_lo -= x_span * 0.08
        x_hi += x_span * 0.08
        y_lo -= y_span * 0.12
        y_hi += y_span * 0.12
        left, right, top, bottom = px + 48, px + 335, 108, 375

        def sx(value: float) -> float:
            return left + (value - x_lo) / (x_hi - x_lo) * (right - left)

        def sy(value: float) -> float:
            return bottom - (value - y_lo) / (y_hi - y_lo) * (bottom - top)

        elements.append(f'<text x="{px + 12}" y="88" class="panel">{relationship["title"]}</text>')
        for index in range(5):
            gy = top + index * (bottom - top) / 4
            elements.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{right}" y2="{gy:.1f}" class="grid"/>')
        slope = float(relationship["slope"])
        line_x = [x_lo, x_hi]
        line_y = [slope * value for value in line_x]
        elements.append(
            f'<line x1="{sx(line_x[0]):.1f}" y1="{sy(line_y[0]):.1f}" '
            f'x2="{sx(line_x[1]):.1f}" y2="{sy(line_y[1]):.1f}" class="line"/>'
        )
        for point in points:
            elements.append(
                f'<circle cx="{sx(float(point["x"])):.1f}" cy="{sy(float(point["y"])):.1f}" '
                f'r="3.5" class="point"/>'
            )
        elements.append(f'<text x="{left}" y="399" class="axis">{x_lo:.3g}</text>')
        elements.append(f'<text x="{right}" y="399" text-anchor="end" class="axis">{x_hi:.3g}</text>')
        elements.append(f'<text x="{px + 190}" y="428" text-anchor="middle" class="axis">{relationship["x_label"]}</text>')
    elements.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    data = load_panel(args.input)
    full_mask = np.ones(len(data["y"]), dtype=bool)
    balanced_mask = balanced_age_mask(data, 1, 5)
    full, full_residuals = analyze_variant("full", "Full panel", data, full_mask)
    balanced, _ = analyze_variant(
        "balanced_age_1_5", "Balanced ages 1–5", data, balanced_mask
    )
    outcome_winsorized, _ = analyze_variant(
        "outcome_winsorized_99", "Outcome capped 99%", data, full_mask,
        winsorize=("y",),
    )
    exposure_winsorized, _ = analyze_variant(
        "exposure_winsorized_99", "Exposures capped 99%", data, full_mask,
        winsorize=("unrelated", "related"),
    )
    all_winsorized, _ = analyze_variant(
        "all_winsorized_99", "All capped 99%", data, full_mask,
        winsorize=("y", "unrelated", "related"),
    )
    variants = [full, balanced, outcome_winsorized, exposure_winsorized, all_winsorized]
    rows = flatten(variants)

    y = full_residuals["y"]
    unrelated = full_residuals["unrelated"]
    related = full_residuals["related"]
    model1_points = quantile_bins(unrelated, y, args.bins)
    y_given_related = partial_out(y, related)
    unrelated_given_related = partial_out(unrelated, related)
    model2_unrelated_points = quantile_bins(
        unrelated_given_related, y_given_related, args.bins
    )
    y_given_unrelated = partial_out(y, unrelated)
    related_given_unrelated = partial_out(related, unrelated)
    model2_related_points = quantile_bins(
        related_given_unrelated, y_given_unrelated, args.bins
    )
    relationships = [
        {
            "title": "Model 1: unrelated",
            "x_label": "Within unrelated exposure",
            "slope": full["model1"]["beta"][0],
            "points": model1_points,
        },
        {
            "title": "Model 2: unrelated | related",
            "x_label": "Partial unrelated exposure",
            "slope": full["model2"]["beta"][0],
            "points": model2_unrelated_points,
        },
        {
            "title": "Model 2: related | unrelated",
            "x_label": "Partial related exposure",
            "slope": full["model2"]["beta"][1],
            "points": model2_related_points,
        },
    ]
    summary = {
        "input": str(args.input),
        "sample": {
            "rows": len(data["y"]),
            "works": int(len(np.unique(data["work_id"]))),
            "authors": int(len(np.unique(data["author_id"]))),
            "paper_author_units": int(
                len(
                    np.unique(
                        np.char.add(
                            np.char.add(data["author_id"].astype(str), "|"),
                            data["work_id"].astype(str),
                        )
                    )
                )
            ),
            "outcome_zero_share": float(np.mean(data["y"] == 0)),
            "unrelated_zero_share": float(np.mean(data["unrelated"] == 0)),
            "related_zero_share": float(np.mean(data["related"] == 0)),
        },
        "models": {
            "model1": "citations_jt ~ unrelated_exposure + paper FE + year FE",
            "model2": "citations_jt ~ unrelated_exposure + related_exposure + paper FE + year FE",
            "inference": "work-clustered standard errors",
        },
        "variants": variants,
        "relationships": relationships,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    coefficient_svg(args.coefficient_svg, rows)
    relationship_svg(args.relationship_svg, relationships)
    print(json.dumps({"sample": summary["sample"], "variants": len(variants)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
