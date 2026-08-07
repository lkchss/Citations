# Economics subject-level results

## Sample and baseline definition

The economics hit-event panel contains 75,882 author–focal-paper–hit units and
11,155 OpenAlex author entities. Candidate hits have at least 101 citations and
more than 50% of the author's economics-portfolio citations. Focal papers are
older works that the candidate hit does not reference.

This treatment definition is provisional because it uses economics-only
portfolios and unvalidated OpenAlex author identities.

## Original result

Mean annual citations to focal papers rise from 0.516 in event years −5:−1 to
0.864 in years 0:+4.

| Pre mean | Post mean | Raw change |
|---:|---:|---:|
| 0.516 | 0.864 | +0.348 |

![Original economics event profile](../8.7.26/economics_subject_level/economics_big_hit_event_time.svg)

The original graph is mechanically row-balanced: it reports the same nominal
units at every event time. It is not publication-risk balanced.

## Publication-risk problem

Many early event observations occur before the focal paper exists.

| Event time | Share of nominal rows before focal-paper publication |
|---:|---:|
| −10 | 72.0% |
| −5 | 44.0% |
| −2 | 13.4% |
| −1 | 0.0% |

Treating these rows as zero citations mechanically creates an upward pretrend.

![Original versus publication-at-risk profile](../8.7.26/economics_adjusted/raw_vs_at_risk.svg)

Underlying results:
[publication-risk table](../8.7.26/economics_adjusted/at_risk_event_time.csv).

## Aggregate age standardization

A first correction restricts attention to mature papers aged 3–5, 6–10,
11–20, or 21+ and fixes age-bin weights to their event −1 distribution.

| Specification | Pre mean | Post mean | Change |
|---|---:|---:|---:|
| Original | 0.516 | 0.864 | +0.348 |
| Mature-paper age standardized | 0.636 | 0.849 | +0.213 |

Age standardization reduces the raw difference by 38.8% but does not eliminate
it.

![Mature-paper age-standardized profile](../8.7.26/economics_adjusted/mature_age_standardized.svg)

## Paper-level lifecycle normalization

The recovered 191-million-row author–paper–year panel supports a stronger
benchmark. Expected citations are calculated from deduplicated economics works
with the same:

- Calendar year
- Paper age
- Document type

Two samples are reported.

1. **Publication at risk:** papers enter after publication, so composition may
   change across event time.
2. **Fully balanced:** every author–focal–hit unit has all 21 observations from
   event −10 through +10.

The fully balanced sample contains 14,076 units and 3,667 authors.

| Sample | Excess pre | Excess post | Excess change | O/E pre | O/E post | O/E change |
|---|---:|---:|---:|---:|---:|---:|
| Publication at risk | 0.137 | 0.252 | +0.114 | 1.260 | 1.406 | +0.146 |
| Fully balanced −10:+10 | −0.006 | −0.068 | **−0.063** | 0.989 | 0.871 | **−0.119** |

“Excess” is observed minus expected annual citations. “O/E” is the ratio of
observed to expected citations.

![Paper-level excess-citation profile](../8.7.26/economics_paper_level_normalized/paper_level_excess_citations.svg)

![Paper-level observed/expected profile](../8.7.26/economics_paper_level_normalized/paper_level_observed_expected_ratio.svg)

Underlying results:
[normalized event series](../8.7.26/economics_paper_level_normalized/normalized_event_time.csv)
and [pre/post summary](../8.7.26/economics_paper_level_normalized/normalized_pre_post_summary.csv).

## Interpretation

The positive result is sensitive to sample construction:

- The unadjusted changing-risk-set estimate is +0.348 citations.
- Controlling aggregate paper-age composition reduces it to +0.213.
- Paper-level lifecycle normalization reduces the at-risk estimate to +0.114.
- Requiring complete −10:+10 support changes the estimate to −0.063.

The balanced result does not support a positive average spillover for the older
papers that remain observable throughout the full event window. The difference
between at-risk and balanced estimates also indicates substantial selection or
composition effects.

This is still not a causal estimate. Remaining threats include author identity
errors, duplicated work versions, economics-only hit classification, endogenous
hit timing, and differential pretrends.

## Next empirical specification

The next preferred model should use the corrected paper-year panel and estimate
a count model with:

- Focal-paper fixed effects
- Calendar-year fixed effects
- Flexible paper-age effects
- Event-time coefficients
- Standard errors clustered by author
- A non-hit comparison group selected on pre-event trajectories
