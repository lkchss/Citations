# Economics subject-level citation-prominence results

This document connects the raw economics event study, balance diagnosis,
risk-set correction, and age-standardized specification. Results are
descriptive and do not identify a causal effect.

## Baseline economics result

The deduplicated panel contains **75,882** author–focal–hit
units across **11,155** OpenAlex author entities. Mean annual
citations rise from **0.516** in event
years -5:-1 to **0.864** in 0:+4, a raw difference
of **+0.348**.

![Original economics event-time figure](economics_subject_level/economics_big_hit_event_time.svg)

- [Original subject writeup](economics_subject_level/economics_big_hit_subject_summary.md)
- [Original event-time data](economics_subject_level/economics_big_hit_event_time.csv)

## Balance and risk-set diagnosis

The panel is row-balanced—each event year contains the same nominal units—but
it is not publication-risk balanced. At event time -10,
**72.0%** of nominal
rows occur before the focal paper was published. The share falls to
**44.0%** at event -5
and reaches zero at event -1.

This mechanically depresses the early pre-period and explains a substantial
part of the apparent pre-trend.

![Original versus publication-at-risk series](economics_adjusted/raw_vs_at_risk.svg)

- [At-risk event-time data](economics_adjusted/at_risk_event_time.csv)

## Mature-paper age standardization

The adjusted specification uses focal papers aged 3–5, 6–10, 11–20, and 21+
over the common event window -5:+4. Age-bin weights are fixed to their event
time -1 distribution.

![Mature-paper age-standardized series](economics_adjusted/mature_age_standardized.svg)

| Specification | Pre mean | Post mean | Difference | Main qualification |
|---|---:|---:|---:|---|
| Original row-balanced | 0.516 | 0.864 | +0.348 | Includes pre-publication pseudo-observations |
| Mature-paper age standardized | 0.636 | 0.849 | +0.213 | Fixed t=-1 weights; ages 3+ |

Age standardization reduces the raw difference from **+0.348**
to **+0.213**, a reduction of
**38.8%**.

- [Adjustment methodology](economics_adjusted/README.md)
- [Age-standardized event data](economics_adjusted/mature_age_standardized_event_time.csv)
- [Adjustment summary](economics_adjusted/summary.json)

## Paper-level lifecycle and calendar-year normalization

The recovered author–paper–year panel permits a stronger adjustment. Expected
citations are estimated from deduplicated economics works in the same calendar
year, paper age, and document type. The genuinely balanced cohort requires all
21 event years (-10:+10) to be observed for each author–focal–hit unit.

- Balanced units: **14,076**
- Balanced authors: **3,667**
- Observations per balanced event year: **14,076**

| Sample | Excess-citation change | Observed/expected change |
|---|---:|---:|
| Publication at-risk | +0.114 | +0.146 |
| Fully balanced -10:+10 | -0.063 | -0.119 |

![Paper-level lifecycle-adjusted excess citations](economics_paper_level_normalized/paper_level_excess_citations.svg)

![Paper-level observed/expected ratio](economics_paper_level_normalized/paper_level_observed_expected_ratio.svg)

The at-risk sample remains positive after lifecycle normalization, but the fully
balanced older-paper cohort is negative. This is a major specification result:
the positive aggregate pattern is not robust to requiring complete event-window
support.

- [Paper-level normalization report](economics_paper_level_normalized/README.md)
- [Normalized event-time data](economics_paper_level_normalized/normalized_event_time.csv)
- [Normalized pre/post summary](economics_paper_level_normalized/normalized_pre_post_summary.csv)
- [Normalization metadata](economics_paper_level_normalized/metadata.json)

## Additional ingestion outputs

- [Headline results](ingestion_ready/headline_results.csv)
- [Combined JSONL](ingestion_ready/results.jsonl)
- [Data dictionary](ingestion_ready/data_dictionary.json)
- [Checksummed manifest](ingestion_ready/manifest.json)
- [Positive-citation-share figure](ingestion_ready/economics_positive_citation_share.svg)

## Interpretation

- The original positive pre/post difference is not solely an artifact of
  pre-publication rows or shifting paper ages, but both materially affect it.
- The remaining +0.213 age-standardized difference is descriptive. It may
  reflect author prominence, continuing pre-trends, paper quality, cohort
  composition, calendar-year conditions, or selection into the hit sample.
- The economics hit definition still uses subject-restricted citation totals,
  and OpenAlex identity/version errors remain unresolved.

## Next subject-level improvements

1. Rebuild the paper-year panel with publication-risk eligibility enforced.
2. Add calendar-year, paper-age, and focal-paper fixed effects using PPML.
3. Construct comparable non-hit authors and stacked event-study controls.
4. Repeat across subjects after validating reference and citation coverage.
