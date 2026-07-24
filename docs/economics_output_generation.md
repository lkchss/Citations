# Economics Output Generation

This note records how the current economics diagnostics were generated.

## Panel

1. Read the economics subject tables from `/root/sdb1/openalex/subjects/subject_level.duckdb`, including works, authorships, and reference edges.
2. Restricted author histories to article/review works published 1990–2020.
3. Kept authors with at least 5 subject papers and at least 3 papers before a focal paper.
4. Sampled 4/250 authors and retained at most 5,000 authors; focal works were sampled 1/2 through a stable hash.
5. Restricted focal publication years to 1990–2019 and excluded each focal work from its own author history.
6. Built author-paper-year rows for publication years 1990–2025, beginning at paper age 1.
7. Defined related work as a direct reference edge in either direction between an author's history and the focal work. All other eligible history papers contributed to unrelated exposure.
8. Aggregated lagged cumulative citations through years before each row year. No pre-publication rows or negative exposures were retained.

The resulting panel contains 211,825 rows, 14,675 focal works, and 2,853 authors. Annual focal-paper citations were reconstructed from `referenced_works` across the full snapshot, not from sparse `counts_by_year` fields. The resulting citation file is `calculated_citations_by_year.csv.gz`. The panel uses those reconstructed counts as its outcome and records the source in `citation_source`.

## Outputs

The level diagnostic estimates:

```text
citations_jt ~ accumulated_unrelated_citations_jt + paper FE + year FE
citations_jt ~ accumulated_unrelated_citations_jt + accumulated_related_citations_jt + paper FE + year FE
```

The log1p robustness output applies `log(1 + x)` to the outcome and both exposure variables before absorbing the same paper and year effects. Both specifications use work-clustered standard errors. The renderer residualizes variables by paper and year, estimates OLS on the residuals, and reports normal-approximation p-values.

These outputs measure the conditional association between a focal paper's later annual citations and an author's accumulated citations to other subject papers, separated by direct reference relatedness. They are diagnostics, not causal estimates. The design remains sensitive to exposure definition, citation measurement, selection, timing, and inference choices.

Live outputs are stored under `/root/sdb1/openalex/subjects/prevalence_regressions_economics_duckdb_v3/`:

- `economics_exposure.csv.gz`
- `economics_prevalence_regressions.html`
- `economics_prevalence_regressions_log1p.html`
- `economics_exposure.diagnostics.json`
