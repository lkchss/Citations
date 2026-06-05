# Subject Hit-Effect Comparison

This report compares the same descriptive hit-effect design across completed subject panels. The three non-economics subjects use OpenAlex `counts_by_year` and therefore still have sparse citation-year rows. Economics is shown both with the earlier sparse `counts_by_year` run and with the corrected recalculated-reference citation run.

## Summary

| Subject / run | Citation source | Works | Hit events | Pairs | Rows | Missing overall | Missing pre | Missing post | Mean pre | Mean post | Added, zero-filled | Added, observed-only | Observed pairs |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Economics, old OpenAlex counts_by_year | openalex_counts_by_year | 7,924,745 | 11,158 | 76,074 | 1,597,554 | 70.27% | 52.04% | 86.85% | 0.1612 | 0.5000 | 0.3388 | 2.0412 | 26,092 |
| Economics, recalculated references | calculated_references | 7,924,745 | 11,158 | 76,074 | 1,597,554 | 0.00% | 0.00% | 0.00% | 0.3515 | 0.6688 | 0.3172 | 0.3172 | 76,074 |
| Agricultural and Biological Sciences | openalex_counts_by_year | 13,802,779 | 32,578 | 233,060 | 4,894,260 | 70.60% | 56.62% | 83.31% | 0.1814 | 0.5783 | 0.3969 | 1.9318 | 87,996 |
| Biochemistry, Genetics, and Molecular Biology | openalex_counts_by_year | 13,360,774 | 93,752 | 578,505 | 12,148,605 | 63.97% | 49.04% | 77.53% | 0.4465 | 1.1795 | 0.7330 | 2.7697 | 266,187 |
| Physics and Astronomy | openalex_counts_by_year | 11,592,579 | 33,345 | 301,816 | 6,338,136 | 69.48% | 53.42% | 84.08% | 0.2568 | 0.7278 | 0.4710 | 2.5493 | 102,927 |

## Interpretation

- The economics recalculated-reference run is the only run here with the zero-count citation fix applied.
- The three new subject runs are intentionally pre-recalculation baselines. Their observed-only estimates should be treated cautiously when missing rates are high or asymmetric around the hit year.
- Large event panels remain on the SSD. GitHub contains only compact summaries and event-time tables.

## Output Folders

- Economics, Econometrics, and Finance: `reports/economics/`
- Agricultural and Biological Sciences: `reports/subjects/agricultural_and_biological_sciences/hit_effects_counts_by_year/`
- Biochemistry, Genetics, and Molecular Biology: `reports/subjects/biochemistry_genetics_and_molecular_biology/hit_effects_counts_by_year/`
- Physics and Astronomy: `reports/subjects/physics_and_astronomy/hit_effects_counts_by_year/`
