# Citation Project Progress Report

**Status date:** August 28, 2026  
**Workstreams:** related/unrelated citation regressions; contextual citation-importance triangles

## Executive summary

- The reliable WoS agricultural-economics panel and the full OpenAlex panel both show a much larger coefficient for related than unrelated citation exposure. In WoS agricultural economics both coefficients are positive; in full OpenAlex the related coefficient is positive while the conditional unrelated coefficient is slightly negative.
- The WoS economics-only and combined economics/agricultural-economics panels are explicitly flagged as broken in the source report and should not be treated as reliable comparison estimates.
- The triangles project is constructing a rigorously screened set of 500 pairwise citation-importance comparisons: 50 focal papers, 10 triangles per focal, and at least five distinct citing papers per focal.
- The current PDF gate admits 1,581 candidate triangles backed by 2,990 lawful, identity-verified documents. Thirty-seven focal papers currently meet the structural requirement of at least 10 triangles from at least five distinct citing papers. Citation-occurrence and cited-paper-evidence screening are still in progress, so the final 500-triangle dataset has not yet been selected.

## Related versus unrelated citations: WoS compared with OpenAlex

The regressions ask whether an author's accumulated citations to earlier papers predict annual citations to a later focal paper. “Related” papers have a direct reference edge with the focal paper in either direction; other eligible prior papers are “unrelated.” Exposures are lagged through the prior year.

The two directly comparable specifications are:

1. Annual focal-paper citations on accumulated unrelated citations, with paper and year fixed effects.
2. Annual focal-paper citations on accumulated unrelated and related citations, with paper and year fixed effects.

Standard errors are clustered by focal work. Both comparisons use level outcomes and exposures.

| Estimate | WoS agricultural economics | Full OpenAlex economics panel |
|---|---:|---:|
| Model 1: unrelated | 0.0006922*** (0.0000621) | 0.0000408** (0.0000133) |
| Model 2: unrelated | 0.0004619*** (0.0000574) | -0.0000404† (0.0000206) |
| Model 2: related | 0.003217*** (0.000548) | 0.001521*** (0.000392) |
| Observations | 888,901 | 27,213,454 |
| Within R², Model 1 | 0.001875 | 0.000109 |
| Within R², Model 2 | 0.002772 | 0.004443 |

Parentheses contain paper-clustered standard errors. `*** p < 0.001`; `** p < 0.01`; `† p = 0.0506`. Per 100 accumulated citations, the Model 2 estimates imply approximately `+0.0462` unrelated and `+0.322` related annual citations in WoS agricultural economics, compared with `-0.00404` unrelated and `+0.152` related annual citations in full OpenAlex.

### Interpretation

The strongest common result is that related exposure matters more than unrelated exposure. In WoS agricultural economics, the Model 2 related coefficient is about seven times the unrelated coefficient. In full OpenAlex, the related coefficient is positive and precisely estimated, while the unrelated coefficient becomes small and negative after related exposure is included.

The OpenAlex coefficients are smaller than the reliable WoS agricultural-economics coefficients: about 94.1% smaller for Model 1 unrelated exposure, 91.3% smaller in absolute value for Model 2 unrelated exposure, and 52.7% smaller for Model 2 related exposure. These are descriptive contrasts—not estimates of a database effect—because the panels differ in field coverage, construction, and sample size.

The full OpenAlex panel is much broader:

| Quantity | WoS agricultural economics | Full OpenAlex |
|---|---:|---:|
| Paper-year observations | 888,901 | 27,213,454 |
| Focal works | Not reported in the WoS summary | 1,253,129 |
| Authors | Not reported in the WoS summary | 197,777 |
| Model 1 within R² | 0.001875 | 0.000109 |
| Model 2 within R² | 0.002772 | 0.004443 |

The OpenAlex panel contains about 30.6 times as many observations. Unlike the earlier recovered OpenAlex benchmark, the WoS agricultural-economics model does not display an unusually high within R²; its within fit is low and comparable in scale to the full OpenAlex result.

### WoS economics quality warning

The WoS source also reports an economics-only panel with 15,733,536 observations, but labels it **“broken.”** Its Model 2 coefficients are `-0.0000749` for unrelated exposure and a statistically insignificant `-0.0000540` for related exposure. The combined economics/agricultural-economics panel is likewise dominated by the problematic economics data and produces mostly small negative coefficients. The source associates this behavior with a likely economics data or panel-construction problem. Those estimates are retained as diagnostics but excluded from the primary WoS/OpenAlex comparison above.

The WoS provenance is documented in `wos_regressions.md` on `origin/main`, which identifies `/fsr/citations/code/run_regression_analysis.R` and the result files under `/fsr/citations/data/`. Those original `/fsr` inputs are not present in this checkout, so the report can verify the repository's documented estimates but cannot independently rerun the WoS models here.

## Citation-importance triangles

### Goal

The project will estimate how important a cited paper was to the paper citing it. Each triangle gives an evaluator one citing paper and two papers it cites: a focal paper and an opponent. The evaluator compares their substantive importance to the citing paper. Pairwise shares will then be aggregated into focal-paper importance measures and, where coverage permits, author-level summaries.

The pilot target is exactly **500 triangles: 50 focal papers × 10 comparisons**, with at least **five distinct citing papers per focal**.

### Core rules

- Every triangle must contain three distinct works: one citing paper, one focal cited paper, and one opponent cited paper.
- The focal and opponent must each have an individually attributable citation in the body of the citing paper; grouped citation markers are excluded.
- Lawful, identity-verified full-text PDFs are required for all three works. Abstract-only records do not qualify, and Sci-Hub is not used.
- Evaluators receive every attributable occurrence and adequate evidence from both cited papers.
- Opponents are sampled from the citing paper's eligible reference pool, not merely from the focal citation's section.
- Exact focal–citing–opponent triples cannot repeat. Repeated focal–citing pairs may appear with different opponents but must be treated as clustered observations.
- Evaluator packets must hide structured prestige signals such as authors, journals, and citation counts. Advocates argue each side; a separate judge assigns shares in 0.05 increments that sum to one.
- Selection, PDF identity, occurrence resolution, evidence retrieval, blinding, scoring, and aggregation must retain auditable provenance.

### Progress

| Stage | Current state |
|---|---:|
| Stratified focal reserve | 3,000 focal candidates |
| Focals with verified PDFs in the passing pool | 202 |
| Deep candidate graph | 78,184 candidate triangles across 202 focals |
| Candidates with complete metadata and three OA-PDF candidates | 6,185 |
| Verified documents admitted by the current PDF gate | 2,990 |
| Candidate triangles passing all three PDF/identity checks | 1,581 |
| Focals represented after the PDF gate | 133 |
| Focals currently meeting ≥10 triangles and ≥5 distinct citers | 37 of 50 required |
| Resolver tranche prepared | 1,581 triangles; 3,162 directed citation events; 1,879 documents |

The current work is extracting page-aligned text, resolving the two citation events in each candidate triangle, retrieving cited-paper evidence, and measuring attrition under the occurrence/evidence gate. A targeted 21-document recovery attempt did not produce any new identity-passing PDFs; all 21 records remain excluded. Further expansion must use additional lawful repository sources or alternative candidates without weakening the admission rules.

### Remaining work

1. Complete occurrence resolution and cited-paper evidence retrieval for the PDF-qualified pool.
2. Quantify how many focal papers still satisfy the 10-triangle/five-citer rule after grouped, missing, or ambiguous occurrences are removed.
3. Expand lawful PDF and candidate coverage until at least 50 focal papers survive every gate.
4. Select exactly 500 triangles and run final uniqueness, diversity, checksum, identity, occurrence, evidence, and provenance audits.
5. Build metadata-blinded evaluator packets and validate the blinding boundary before subjective relevance grading begins.

## Bottom line

The reliable WoS agricultural-economics and full OpenAlex results agree that related citation exposure has the larger positive association with focal-paper citations, although they differ on the sign of conditional unrelated exposure. The triangles work has moved from graph construction into full-text qualification and occurrence/evidence validation, but it is not complete: the current pool is 13 structurally qualifying focal papers short before accounting for further occurrence and evidence attrition.

## Supporting project artifacts

- `reports/openalex_comparison/README.md`
- `reports/openalex_comparison/legacy_vs_full_openalex.csv`
- `reports/openalex_comparison/full_openalex_two_model_regressions.summary.json`
- `wos_regressions.md` (`origin/main`)
- `docs/FOCAL_CITATION_IMPORTANCE_PILOT.md`
- `workspace/wave14_pdf_pre_admission_full_v3/summary.json`
- `workspace/wave15_focal_tranche_resolver_adapter_v1/manifest.json`
