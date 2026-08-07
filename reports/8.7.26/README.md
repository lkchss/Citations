# Session Outputs — August 7, 2026

This folder compiles the economics citation-prominence outputs produced during
the August 7, 2026 project audit and exploratory analysis session.

## Canonical connected reports

- [`author_level_results.md`](author_level_results.md) connects the candidate
  screen, John List case study, Jensen/Arellano/Solow profiles, original
  figures, and matched-control specifications.
- [`subject_level_results.md`](subject_level_results.md) connects the original
  economics event study, panel-balance diagnosis, publication-risk correction,
  age standardization, and ingestion outputs.

## Ingestion-ready Package

Directory: [`ingestion_ready/`](ingestion_ready/)

This portable package can be rebuilt without the external SSD. It contains
tidy CSVs, combined JSONL records, five SVG figures, a data dictionary, and a
checksummed manifest. Start with
[`headline_results.csv`](ingestion_ready/headline_results.csv) for headline
values or [`results.jsonl`](ingestion_ready/results.jsonl) for direct ingestion.

## Additional Author Hit Profiles

Directory: [`author_hit_profiles/`](author_hit_profiles/)

API-based exploratory profiles compare Michael Jensen, Manuel Arellano, and
Robert Solow. The package includes all-field versus economics-only hit shares,
version-clustered prior-work cohorts, event-time CSV data, four SVG figures, and
an HTML report. Only Arellano's candidate exceeds 50% under the live all-field
OpenAlex author denominator; all three identities still require manual review.

## Age-adjusted Economics Results

Directory: [`economics_adjusted/`](economics_adjusted/)

Aggregate-cell adjustments exclude pre-publication pseudo-observations and
standardize mature focal papers to fixed age-bin weights. The standardized raw
pre/post difference falls to +0.213, compared with +0.348 in the unadjusted
headline series.

The [original unadjusted economics figure](economics_subject_level/economics_big_hit_event_time.svg)
is preserved alongside the adjusted specifications.

## Paper-level Normalized Economics Results

Directory: [`economics_paper_level_normalized/`](economics_paper_level_normalized/)

The recovered 191-million-row panel supports calendar-year, paper-age, and
document-type normalization. The at-risk sample remains positive, but the
genuinely balanced 14,076-unit -10:+10 cohort has a negative normalized
pre/post difference. This is the strongest current specification diagnostic.

## API-derived Matched Controls

Directory: [`author_matched_controls/`](author_matched_controls/)

Publication-year, work-type, and topic-matched OpenAlex controls are provided
for John List, Michael Jensen, Manuel Arellano, and Robert Solow. The output
includes matched-pair records, tidy event series, pretrend diagnostics, and four
SVG figures. These are exploratory comparisons rather than causal estimates.
The [original John List figure](john_list_case_study/unrelated_prior_citations.svg)
and the [original Jensen/Arellano/Solow figures](author_hit_profiles/) remain
available unchanged.

## John List Case Study

Directory: [`john_list_case_study/`](john_list_case_study/)

- [`john_list_case_study.md`](john_list_case_study/john_list_case_study.md):
  rendered exploratory report.
- [`author_works.csv`](john_list_case_study/author_works.csv): economics-classified
  portfolio and hit/focal eligibility flags.
- [`paper_year.csv`](john_list_case_study/paper_year.csv): reconstructed annual
  citations for eligible prior papers.
- [`event_time.csv`](john_list_case_study/event_time.csv): aggregate calendar- and
  event-time series.
- [`paper_contributions.csv`](john_list_case_study/paper_contributions.csv):
  paper-level contributions to the post-2002 increase.
- [`hit_variants.csv`](john_list_case_study/hit_variants.csv): threshold variants.
- [`provenance.json`](john_list_case_study/provenance.json): inputs, identifiers,
  definitions, and headline values.

John List is a gradual-prominence case rather than a literal 50% big-hit case.
His highest-cited economics paper accounts for 10.14% of his economics-portfolio
citations. For the fixed 49-paper prior-work cohort, mean annual citations rise
from 1.18 in 2002 to 3.02 in 2007–09, but the top five focal papers account for
87.4% of the net increase.

## Economics Big-Hit Screen

Directory: [`big_hit_screen/`](big_hit_screen/)

- [`economics_big_hit_candidates.md`](big_hit_screen/economics_big_hit_candidates.md):
  browsable candidate dashboard.
- [`economics_big_hit_candidates.csv`](big_hit_screen/economics_big_hit_candidates.csv):
  top 5,000 provisional candidates under the raw screen.
- [`economics_big_hit_research_shortlist.csv`](big_hit_screen/economics_big_hit_research_shortlist.csv):
  2,181 candidates with more substantial cited pre-hit histories and limited
  hit-paper author counts.
- [`economics_big_hit_screen_audit.json`](big_hit_screen/economics_big_hit_screen_audit.json):
  parameters and warnings.

The screen uses economics-classified articles, preprints, and reviews. It
requires at least 100 economics-portfolio citations, a strict top-paper share
above 50%, and at least three earlier research works. These are provisional
economics-portfolio shares, not final all-field author shares.

## Economics Subject-Level Summary

Directory: [`economics_subject_level/`](economics_subject_level/)

- [`economics_big_hit_subject_summary.md`](economics_subject_level/economics_big_hit_subject_summary.md):
  full economics publication-year event summary.
- [`economics_big_hit_event_time.csv`](economics_subject_level/economics_big_hit_event_time.csv):
  event-time estimates.
- [`economics_big_hit_event_time.svg`](economics_subject_level/economics_big_hit_event_time.svg):
  event-time figure.
- [`economics_big_hit_subject_summary.json`](economics_subject_level/economics_big_hit_subject_summary.json):
  counts, estimates, and caveats.

The deduplicated panel contains 75,882 author–focal-paper–hit units across
11,155 authors. Mean annual citations rise descriptively from 0.516 in event
years -5 through -1 to 0.864 in years 0 through +4, a difference of 0.348.

## John List Citation Reconciliation

[`john_list_citation_reconciliation.md`](john_list_citation_reconciliation.md)
explains why the current 46,684-citation OpenAlex author total does not match
the local economics portfolio. The OpenAlex author entity contains 900 works
and appears merged; the local work-level and reconstructed economics totals
agree within 0.44%.

## Audit And Plan

[`exploratory_audit_2026-08-07.md`](exploratory_audit_2026-08-07.md) records the
research objective, working definitions, database-quality findings, current
outputs, and immediate execution plan.

## Important Caveats

- Candidate portfolios are truncated to works classified in economics.
- OpenAlex contains visible authorship errors and subject leakage.
- Article/preprint and edition duplicates require scholarly-output
  deduplication.
- Candidate authors must be checked against complete all-field portfolios.
- Absence of a hit-to-focal citation is usable only after reference
  completeness is validated.
- All results in this folder are exploratory and descriptive, not causal
  estimates.

## Reproduction Scripts

- [`scripts/build_author_case_study.py`](../../scripts/build_author_case_study.py)
- [`scripts/screen_economics_big_hit_authors.py`](../../scripts/screen_economics_big_hit_authors.py)
- [`scripts/build_economics_subject_big_hit_summary.py`](../../scripts/build_economics_subject_big_hit_summary.py)
