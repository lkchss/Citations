# All Web of Science (WoS) Regressions

This document consolidates every regression run on **Web of Science** citation data across the codebase (`/fsr/citations/code/`). It excludes the parallel OpenAlex-based "hit effects" analyses, which live under `Projects2/Citations/docs/` and `reports/subjects/*/hit_effects_counts_by_year/`.

Three research questions were studied on WoS data:
1. **Author Prominence → Paper Citations** (completed, two field studies: Fisheries and Economics-adjacent)
2. **Related vs. Unrelated Citation Spillovers** (completed — the "related"/"unrelated" citations-on-RHS models; economics + agricultural economics, plus a combined same-field/cross-field breakdown)
3. **Big-Hit Spillover / Regression Discontinuity** (incomplete — blocked by sample size / data gaps)

---

## 1. Author Prominence → Paper Citations: Fisheries

Source: `/fsr/citations/code/ANALYSIS_WRITEUP.md`
Data: WoS fisheries category, 12,812 papers, 1981–2025.

### Model 1: Cross-Sectional OLS (Basic)
```
log(Citations_ij) = β₀ + β₁·AuthorProminence_j + β₂·log(CoauthorCount_i) + ε_ij
```
- Unit: author-paper pair (*j*, *i*); SEs clustered at paper level
- N = 49,092
- **β₁ = 0.1054** — 10% more citations to author's other work → 1.05% more citations to focal paper
- Limitation: no year control, mixes selection with causal effect

### Model 2: Cross-Sectional OLS + Publication Year FE
```
log(Citations_ij) = β₀ + β₁·AuthorProminence_j + β₂·log(CoauthorCount_i) + β₃·PubYear_i + ε_ij
```
- SEs clustered at paper level
- **β₁ = 0.1028** (also reported elsewhere as 0.103, t=46.4, p<0.001), R² = 0.066
- Within-cohort comparison; still cross-sectional

### Model 3: Multi-Paper Authors Subsample
```
log(Citations_ij) = β₀ + β₁·AuthorProminence_j + β₂·log(CoauthorCount_i) + β₃·PubYear_i + ε_ij
    WHERE: has_other_papers_j = 1
```
- N = 27,646 (56% of sample, authors with ≥2 papers)
- **β₁ = 0.3959** — 4× larger than Model 2; R² jumps from 6.6% → 27.9%
- 1-SD increase in prominence → ~99% increase in citations for established authors

### Model 4: Paper-Year Panel with Publication Year FE
```
log(Citations_it) = β₀ + β₁·MaxAuthorProminence_it + β₂·PaperAge_it + β₃·PaperAge²_it
                    + β₄·log(CoauthorCount_i) + δ_s + ε_it
```
- Unit: paper-year; δ_s = publication-year fixed effects; SEs clustered at paper level
- N = 193,047 paper-year observations
- **β₁ = 0.1226** (also reported as 0.123, t=109.3), R² = 0.173
- Within-cohort, papers with more prominent authors accumulate citations 12.3% faster
- β₂, β₃ ≈ 0 mechanically (absorbed by year FE)

---

## 2. Author Prominence → Paper Citations: Economics-Adjacent Fields

Source: `/fsr/citations/code/panel_output/ECONOMICS_ANALYSIS_WRITEUP.md`
Data: WoS, 4 fields — Economics, Operations Research & Management Science, Business Finance, Agricultural Economics & Policy. 46,972,785 author-paper-year records; 2,832,137 unique author-paper pairs.

### Model 1: Cross-Sectional OLS (Basic)
```
log(Citations_ij) = β₀ + β₁·AuthorProminence_j + β₂·log(CoauthorCount_i) + ε_ij
```
- N = 2,832,137, SEs clustered at paper level
- **β₁ = 0.183** (SE=0.0003, t=619.6***), R² = 0.133

### Model 2: Cross-Sectional OLS + Publication Year *(preferred spec)*
```
log(Citations_ij) = β₀ + β₁·AuthorProminence_j + β₂·log(CoauthorCount_i) + β₃·PubYear_i + ε_ij
```
- **β₁ = 0.171** (SE=0.0003, t=603.9***), R² = 0.209 (all fields pooled)
- Economics-only subsample: N = 1,702,754, **β₁ = 0.210** (SE=0.0004, t=537.3***), R² = 0.250
- Marked "preferred specification for comparability across studies"

### Model 3: Multi-Paper Authors Subsample
```
log(Citations_ij) = β₀ + β₁·AuthorProminence_j + β₂·log(CoauthorCount_i) + β₃·PubYear_i + ε_ij
    WHERE: has_other_papers_j = 1
```
- N = 2,139,580 (76% of sample)
- **β₁ = 0.377** (SE=0.0004, t=1026.2***), R² = 0.401 — 2.2× larger than Model 2

### Model 4: Field Fixed Effects
```
log(Citations_ij) = β₀ + β₁·AuthorProminence_j + β₂·log(CoauthorCount_i) + β₃·PubYear_i + δ_field + ε_ij
```
- Adds 4 field dummies
- **β₁ = 0.179** (SE=0.0003, t=649.5***), R² = 0.252 — stable vs. Model 2, so effect not driven by field composition

### Model 5: Paper-Year Panel
```
log(Citations_it) = β₀ + β₁·MaxAuthorProminence_it + β₂·PaperAge_it + β₃·PaperAge²_it
                    + β₄·log(CoauthorCount_i) + δ_s + ε_it
```
- N = 3,956,742 paper-year observations (20% sample for computational efficiency), SEs clustered at paper level
- **β₁ = 0.205** (SE=0.0002, t=864.8***), R² = 0.241 — papers with more prominent authors accumulate citations ~20.5% faster over their lifetime

### Field-Specific Results (Model 2, re-estimated per field)

| Field | N | β₁ | SE | t-stat | R² |
|-------|---|-----|-----|--------|-----|
| Economics | 1,702,754 | **0.210** | 0.0004 | 537.3*** | 0.250 |
| Business Finance | 457,314 | **0.153** | 0.0005 | 283.0*** | 0.394 |
| Operations Research | 559,941 | **0.069** | 0.0004 | 165.5*** | 0.212 |
| Agricultural Economics | 112,128 | **0.060** | 0.0012 | 48.6*** | 0.426 |

Prominence effect is ~3.5× stronger in economics than in operations research.

---

## 3. Related vs. Unrelated Citation Spillovers (RHS variables)

Source: `/fsr/citations/code/run_regression_analysis.R`, results in `/fsr/citations/code/regression_results.md`, `/fsr/citations/data/standalone_econ_results.csv`, `/fsr/citations/data/standalone_ag_results.csv`, `/fsr/citations/data/regression_results_combined.csv`.

This is the study that defines **`accumulated_related_jt`** (citations accumulated to the author's papers that ARE cited by / related to the focal paper) and **`accumulated_unrelated_jt`** (citations to the author's other, unrelated papers) as separate right-hand-side regressors — same underlying panel-building pipeline as the big-hit spillover work in §4, but at the full paper-year panel level rather than a balanced-author RD design. Estimated with `fixest::feols`, paper and year fixed effects, clustered SEs by paper.

### 3a. Standalone: Agricultural Economics

```
Model 1: cites_jt ~ accumulated_unrelated_jt | paper_id + year
Model 2: cites_jt ~ accumulated_unrelated_jt + accumulated_related_jt | paper_id + year
Model 3: cites_jt ~ accumulated_unrelated_jt + accumulated_related_jt + paper_age | paper_id
```

| Variable | Model 1 | Model 2 | Model 3 |
|----------|---------|---------|---------|
| accumulated_unrelated_jt | 6.922e-04*** (6.206e-05) | 4.619e-04*** (5.738e-05) | 4.626e-04*** (5.697e-05) |
| accumulated_related_jt | — | 3.217e-03*** (5.483e-04) | 3.205e-03*** (5.469e-04) |
| paper_age | — | — | -1.756e-03*** (7.054e-05) |
| N | 888,901 | 888,901 | 888,901 |
| R² | 0.472 | 0.473 | 0.472 |
| Within R² | 0.001875 | 0.002772 | 0.003390 |
| Paper FE / Year FE | Yes / Yes | Yes / Yes | Yes / No |

Related citations have a ~7× larger coefficient than unrelated citations — same-paper "relatedness" carries much more of the spillover.

### 3b. Standalone: Economics ("broken" — flagged by the analyst in the source file)

Same three specifications, N = 15,733,536.

| Variable | Model 1 | Model 2 | Model 3 |
|----------|---------|---------|---------|
| accumulated_unrelated_jt | -7.762e-05*** (6.891e-06) | -7.488e-05*** (1.001e-05) | -8.208e-05*** (1.002e-05) |
| accumulated_related_jt | — | -5.398e-05, n.s. (2.033e-04) | -4.637e-05, n.s. (2.032e-04) |
| paper_age | — | — | -3.384e-03*** (5.897e-05) |
| R² | 0.655 | 0.655 | 0.653 |
| Within R² | 0.000693 | 0.000698 | 0.002864 |

The header labels this panel **"(broken)"** in the source markdown — coefficients are negative/near-zero and the related-citations coefficient is not significant, inconsistent with the ag-econ results and with the positive prominence effects found elsewhere (§2). No explanation of the break was found in the repo; likely a data/panel construction issue with the economics-only panel (consistent with the known economics data-collection gap noted in §4). Treat these economics coefficients as unreliable pending investigation.

### 3c. Combined Economics + Ag Econ: Same-Field vs. Cross-Field Spillovers

From `run_regression_analysis.R` lines 189–334, run on `panel_output/regression_panel_combined_econ_agecon.parquet` (N = 15,733,536 combined; 14,799,164 economics; 934,372 ag econ):

```
cm1:  cites_jt ~ accumulated_unrelated_jt | paper_id + year
cm2:  cites_jt ~ accumulated_unrelated_jt + accumulated_related_jt | paper_id + year
cm3:  cites_jt ~ accumulated_unrelated_samefield_jt + accumulated_unrelated_crossfield_jt | paper_id + year   [KEY MODEL]
cm4:  cites_jt ~ accumulated_unrelated_samefield_jt + accumulated_unrelated_crossfield_jt
                + accumulated_related_samefield_jt + accumulated_related_crossfield_jt | paper_id + year
cm5_econ/cm8_agecon:   cm1 subset by field
cm6_econ/cm9_agecon:   cm2 subset by field
cm7_econ/cm10_agecon:  cm3 subset by field
```

**Selected coefficients** (`/fsr/citations/data/regression_results_combined.csv`):

| Model | Coefficient | Value | N |
|-------|-------------|-------|-----|
| Combined: Total Unrelated (cm1) | accumulated_unrelated_jt | -7.081e-05 | 15,733,536 |
| Combined: Total Related (cm2) | accumulated_related_jt | -6.638e-05 | 15,733,536 |
| Combined: Same-Field Unrelated (cm3) | accumulated_unrelated_samefield_jt | -5.746e-05 | 15,733,536 |
| Combined: Cross-Field Unrelated (cm3) | accumulated_unrelated_crossfield_jt | -2.919e-04 | 15,733,536 |
| Combined: Same-Field Related (cm4) | accumulated_related_samefield_jt | -3.214e-06 | 15,733,536 |
| Combined: Cross-Field Related (cm4) | accumulated_related_crossfield_jt | -3.179e-03 | 15,733,536 |
| Econ: Total Unrelated (cm5) | accumulated_unrelated_jt | -5.899e-05 | 14,799,164 |
| Econ: Total Related (cm6) | accumulated_related_jt | 3.613e-05 | 14,799,164 |
| Econ: Same-Field (cm7) | accumulated_unrelated_samefield_jt | -5.391e-05 | 14,799,164 |
| Econ: Cross-Field (cm7) | accumulated_unrelated_crossfield_jt | -2.099e-04 | 14,799,164 |
| AgEcon: Total Unrelated (cm8) | accumulated_unrelated_jt | -2.036e-04 | 934,372 |
| AgEcon: Total Related (cm9) | accumulated_related_jt | -2.769e-03 | 934,372 |
| AgEcon: Same-Field (cm10) | accumulated_unrelated_samefield_jt | -2.319e-04 | 934,372 |
| AgEcon: Cross-Field (cm10) | accumulated_unrelated_crossfield_jt | -1.531e-04 | 934,372 |

Note: these combined-panel coefficients are all negative/small, inconsistent with the strongly positive ag-econ-only results in §3a — this combined panel inherits the same "broken" economics data issue as §3b (economics is 94% of the combined N and drags the pooled estimates negative). Cross-field spillover ratio calculations (cross-field coefficient ÷ same-field coefficient) are computed in the source script but not saved to CSV — see script output/logs if needed.

---

## 4. Big-Hit Spillover / Regression Discontinuity (Economics, Biology, Physics)

Source: `/fsr/citations/code/HANDOFF_ANALYSIS_OVERVIEW.md`
Data: WoS, three fields (Economics, Biology, Physics), seed/authors/cited files per field.

**Design**: 16-year balanced panel window (t-5 pre-hit to t+10 post-hit) around a "big hit" publication (≥50% of author's career citations, published ≥5 years into career). Outcome: `accumulated_unrelated_jt` — cumulative citations to the author's other papers not cited by the big hit and published before t-5. Slope-change test via:
```
cumulative_cites ~ years_since_hit   (fit separately pre- and post-hit; compare slopes)
```
(`analyze_slope_change_balanced_[field].R`, `analyze_slope_change_FULL.R`)

**Status: incomplete.** The "published before t-5" balance requirement eliminates 96%+ of candidate authors.

| Field | Threshold | Starting Authors | With Unrelated Papers | Final Balanced Sample |
|-------|-----------|------------------|------------------------|------------------------|
| Biology | ≥150 citations | 1,531 | 64 (4.2%) | 7 (0.5%) |
| Physics | ≥150 citations | 1,531 | 0 (0%) | 0 (0%) |
| Economics | ≥150 citations | 1,531 | — | Not run |
| Biology | ≥100 citations | 3,524 | 140 (4.0%) | 16 (0.5%) |
| Physics | ≥100 citations | 3,524 | 1 (0.03%) | 0 (0%) |
| Economics | ≥100 citations | 3,524 | — | Not run |

- Economics run blocked separately by a data-collection gap (original collection skipped iterations 0–188 / top 189,000 papers by citations; recollection attempt found 0 cited references — cause unresolved).
- No slope/RD coefficients were ever produced due to insufficient sample size (biology 7–16 authors, physics 0–1 authors).

### Earlier/preliminary version of §3c

Source: `/fsr/citations/code/analyze_econ_adjacent.R` (lines ~429–450), run against the same `panel_output/regression_panel_combined_econ_agecon.parquet`. Simple `lm()` OLS precursor to the `feols` same/cross-field models in §3c, using logged versions of the same variables (no paper FE, plain OLS instead of `feols`):

```
cm1: log_cites_jt ~ log_acc_unrelated
cm2: log_cites_jt ~ log_acc_unrelated_samefield + log_acc_unrelated_crossfield
cm3: log_cites_jt ~ log_acc_unrelated_samefield + log_acc_unrelated_crossfield + factor(year)
cm4_econ:   same as cm3, subset to subject == "economics"
cm4_agecon: same as cm3, subset to subject == "agricultural_economics_policy"
```
No results writeup was found for these specific `lm()` runs (superseded by the `feols` version in §3c); check `econ_analysis.log` / `economics_panel_build.log` in `/fsr/citations/code/` for raw output if the OLS-only coefficients are needed.

---

## Summary

| # | Study | Data | Models | Status |
|---|-------|------|--------|--------|
| 1 | Author prominence (Fisheries) | WoS fisheries | 4 (OLS ×3, panel ×1) | Complete |
| 2 | Author prominence (Economics-adjacent) | WoS econ/finance/OR/ag-econ | 5 (OLS ×4, panel ×1) | Complete |
| 3 | Related vs. unrelated citation spillovers | WoS econ + ag-econ | 3a: 3 models (ag econ) · 3b: 3 models (econ, flagged broken) · 3c: 10 models (`feols`, same/cross-field) | Complete (economics results flagged unreliable) |
| 4 | Big-hit spillover / RD (Econ, Bio, Physics) | WoS 3 fields | Slope-change regression | Incomplete — sample size / data gap |
