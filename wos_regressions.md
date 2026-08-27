# All Web of Science (WoS) Regressions

This document consolidates every regression run on **Web of Science** citation data across the codebase (`/fsr/citations/code/`). It excludes the parallel OpenAlex-based "hit effects" analyses, which live under `Projects2/Citations/docs/` and `reports/subjects/*/hit_effects_counts_by_year/`.

Two research questions were studied on WoS data:
1. **Author Prominence → Paper Citations** (completed, two field studies: Fisheries and Economics-adjacent)
2. **Big-Hit Spillover / Regression Discontinuity** (incomplete — blocked by sample size / data gaps)

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

## 3. Big-Hit Spillover / Regression Discontinuity (Economics, Biology, Physics)

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

### Earlier/preliminary version of this design: cross-field spillover regressions

Source: `/fsr/citations/code/analyze_econ_adjacent.R` (lines ~429–450), run against `panel_output/regression_panel_combined_econ_agecon.parquet` (Economics + Agricultural Economics combined panel). These appear to be an earlier iteration of the same spillover question, at the paper-year level rather than the balanced-author-panel/RD design above.

```
cm1: log_cites_jt ~ log_acc_unrelated
cm2: log_cites_jt ~ log_acc_unrelated_samefield + log_acc_unrelated_crossfield
cm3: log_cites_jt ~ log_acc_unrelated_samefield + log_acc_unrelated_crossfield + factor(year)
cm4_econ:   same as cm3, subset to subject == "economics"
cm4_agecon: same as cm3, subset to subject == "agricultural_economics_policy"
```
No results writeup was found for these models (no corresponding `*_WRITEUP.md`); check `econ_analysis.log` / `economics_panel_build.log` in `/fsr/citations/code/` for raw run output if coefficients are needed.

---

## Summary

| # | Study | Data | Models | Status |
|---|-------|------|--------|--------|
| 1 | Author prominence (Fisheries) | WoS fisheries | 4 (OLS ×3, panel ×1) | Complete |
| 2 | Author prominence (Economics-adjacent) | WoS econ/finance/OR/ag-econ | 5 (OLS ×4, panel ×1) | Complete |
| 3 | Big-hit spillover / RD (Econ, Bio, Physics) | WoS 3 fields | Slope-change regression | Incomplete — sample size / data gap |
| 3b | Cross-field spillover (early version) | WoS econ + ag-econ | cm1–cm4 (OLS, paper-year) | Run but no writeup found |
