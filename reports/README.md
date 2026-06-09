# Project Outputs

This directory contains GitHub-tracked outputs from the OpenAlex citation analysis.

## Literature

- [Author prevalence literature review](literature/author_prevalence_literature_review.md)
- [Author prevalence BibTeX file](literature/author_prevalence.bib)

## Prevalence Regressions

- [Subject prevalence regression stargazer tables](subjects/prevalence_regression_stargazer_tables.html)
- [Lifetime pilot prevalence regressions](subjects/lifetime_pilot_prevalence_regressions.html)

These tables estimate, separately by subject pool:

```text
citations_jt ~ accumulated_unrelated_citations_jt + FE_j + FE_t
citations_jt ~ accumulated_unrelated_citations_jt + accumulated_related_citations_jt + FE_j + FE_t
```

Paper and year fixed effects are absorbed by two-way demeaning before rendering the stargazer output.

## Subject Comparisons

- [Subject trend regression comparison page](subjects/trend_regression_comparison.html)
- [Subject trend regression stargazer tables](subjects/trend_regression_stargazer_tables.html)
- [Subject hit-effect comparison markdown](subjects/subject_hit_effects_comparison.md)
- [Subject hit-effect comparison CSV](subjects/subject_hit_effects_comparison.csv)

## Economics Outputs

- [Economics hit effects report](economics/economics_hit_effects_report.md)
- [Economics zero-count fix comparison](economics/citation_zero_count_fix_comparison.md)
- [Economics event-time summary](economics/event_time_summary.csv)
- [Economics event-time plot](economics/event_time_means.svg)
- [Economics econometric summary tables](economics/econometrics_summaries/)

## Subject Hit-Effect Outputs

- [Agricultural and Biological Sciences](subjects/agricultural_and_biological_sciences/hit_effects_counts_by_year/)
- [Biochemistry, Genetics, and Molecular Biology](subjects/biochemistry_genetics_and_molecular_biology/hit_effects_counts_by_year/)
- [Physics and Astronomy](subjects/physics_and_astronomy/hit_effects_counts_by_year/)

## Data Location

Large raw and derived data files are stored on the mounted SSD under `/root/sdb1/openalex/` and are intentionally not committed to GitHub. GitHub stores the scripts, literature files, summary tables, plots, and rendered reports.
