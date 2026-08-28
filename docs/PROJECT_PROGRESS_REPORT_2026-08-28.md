# Citation Project Progress Report

**Status date:** August 28, 2026  
**Workstreams:** related/unrelated citation regressions; contextual citation-importance triangles

## Executive summary

- The full WoS economics and full OpenAlex economics regressions are compared using the same related/unrelated citation-exposure models.
- The triangles project is constructing a rigorously screened set of 500 pairwise citation-importance comparisons: 50 focal papers, 10 triangles per focal, and at least five distinct citing papers per focal.
- The current PDF gate admits 1,581 candidate triangles backed by 2,990 lawful, identity-verified documents. Thirty-seven focal papers currently meet the structural requirement of at least 10 triangles from at least five distinct citing papers. Citation-occurrence and cited-paper-evidence screening are still in progress, so the final 500-triangle dataset has not yet been selected.

## Related versus unrelated citations: full WoS economics compared with full OpenAlex economics

### Model 1

```text
annual focal-paper citations
    ~ lagged accumulated unrelated citations
    + paper fixed effects
    + year fixed effects
```

| Result | Full WoS economics | Full OpenAlex economics | OpenAlex − WoS |
|---|---:|---:|---:|
| Unrelated coefficient | -0.00007762 | 0.00004077 | +0.00011839 |
| Standard error | 0.000006891 | 0.00001327 | +0.00000638 |
| p-value | <0.001 | 0.00212 | — |
| Within R² | 0.000693 | 0.000109 | -0.000584 |
| Observations | 15,733,536 | 27,213,454 | +11,479,918 |

### Model 2

```text
annual focal-paper citations
    ~ lagged accumulated unrelated citations
    + lagged accumulated related citations
    + paper fixed effects
    + year fixed effects
```

| Result | Full WoS economics | Full OpenAlex economics | OpenAlex − WoS |
|---|---:|---:|---:|
| Unrelated coefficient | -0.00007488 | -0.00004036 | +0.00003452 |
| Unrelated standard error | 0.00001001 | 0.00002064 | +0.00001063 |
| Unrelated p-value | <0.001 | 0.05058 | — |
| Related coefficient | -0.00005398 | 0.00152136 | +0.00157534 |
| Related standard error | 0.0002033 | 0.0003915 | +0.0001882 |
| Related p-value | ≈0.791 | 0.000102 | — |
| Within R² | 0.000698 | 0.004443 | +0.003745 |
| Observations | 15,733,536 | 27,213,454 | +11,479,918 |

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

The full WoS economics and full OpenAlex economics results are now reported side by side under the same two model specifications. The triangles work has moved from graph construction into full-text qualification and occurrence/evidence validation, but it is not complete: the current pool is 13 structurally qualifying focal papers short before accounting for further occurrence and evidence attrition.

## Supporting project artifacts

- `reports/openalex_comparison/full_openalex_two_model_regressions.summary.json`
- `wos_regressions.md` (`origin/main`)
- `docs/FOCAL_CITATION_IMPORTANCE_PILOT.md`
- `workspace/wave14_pdf_pre_admission_full_v3/summary.json`
- `workspace/wave15_focal_tranche_resolver_adapter_v1/manifest.json`
