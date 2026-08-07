# Author-level results

## Question

Does an author's rise in prominence increase citations to their older papers
that are unrelated to the work producing the rise?

The current operational definition treats an older paper as unrelated when the
candidate hit does not reference it. Treatment begins in the hit paper's
publication year.

## Candidate classification depends on the denominator

The initial screen defined a big hit as a paper receiving more than 50% of an
author's economics-portfolio citations. OpenAlex's author-page total instead
covers all works attributed to the author entity across fields.

| Author | Candidate hit | Economics share | Live all-field share | Passes all-field 50% rule? |
|---|---|---:|---:|---|
| Michael Jensen | *Theory of the Firm* (1976) | 69.5% | 35.2% | No |
| Manuel Arellano | *Some Tests of Specification for Panel Data* (1991) | 57.7% | 52.8% | Yes, provisionally |
| Robert Solow | *A Contribution to the Theory of Economic Growth* (1956) | 56.0% | 35.8% | No |

Only Arellano remains above 50% using the live all-field author denominator.
Even that classification is provisional because his OpenAlex entity contains
an obvious 1912 namesake record.

![Hit-share denominator comparison](../8.7.26/author_hit_profiles/hit_share_denominator_comparison.svg)

Underlying results:
[author profiles](../8.7.26/author_hit_profiles/author_hit_profiles.csv).

## John List

John List is a gradual-prominence case rather than a baseline big-hit case.

- Local economics works: 187
- Local economics work citations: 11,977
- Reconstructed economics citations: 12,030
- Difference between local calculations: 53 citations, or 0.44%
- Live OpenAlex author total: 46,684 citations across 900 attributed works
- Top economics-paper share: 10.1%

The local work-level and reconstructed totals agree closely. The difference
from the OpenAlex author page reflects the economics-only universe plus likely
author-entity contamination, not a failure of the local citation summation.

For the fixed cohort of 49 older papers, mean annual citations rise from 1.18
in 2002 to 3.02 in 2007–09. The increase is concentrated: the top five focal
papers account for 87.4% of the net change.

![John List original profile](../8.7.26/john_list_case_study/unrelated_prior_citations.svg)

This pattern is not clean evidence of spillovers. Citations were already
rising, the breakthrough consisted of several papers rather than a single
event, and List moved to Chicago in 2005.

## Original profiles for Jensen, Arellano, and Solow

The unadjusted author profiles compare mean annual citations to
version-clustered older papers before and after the candidate hit.

| Author | Older-paper clusters | Pre mean | Post mean | Raw change |
|---|---:|---:|---:|---:|
| Michael Jensen | 10 | 3.100 | 8.840 | +5.740 |
| Manuel Arellano | 12 | 0.167 | 0.317 | +0.150 |
| Robert Solow | 15 | 0.187 | 0.280 | +0.093 |

![Michael Jensen original profile](../8.7.26/author_hit_profiles/michael_c_jensen_event_time.svg)

![Manuel Arellano original profile](../8.7.26/author_hit_profiles/manuel_arellano_event_time.svg)

![Robert Solow original profile](../8.7.26/author_hit_profiles/robert_m_solow_event_time.svg)

These are before/after descriptions. Jensen in particular has a strong upward
pre-event trajectory.

## Matched-control comparisons

Each focal paper was paired with one unique OpenAlex control matching
publication year and document type, plus primary topic when available. Changes
compare event years −5:−1 with 0:+4.

| Author | Focal change | Control change | Difference in changes | Pretrend check |
|---|---:|---:|---:|---|
| John List | +1.686 | +0.710 | +0.976 | Fails |
| Michael Jensen | +5.740 | +0.520 | +5.220 | Fails |
| Manuel Arellano | +0.150 | +0.400 | −0.250 | Passes loose check |
| Robert Solow | +0.093 | −0.013 | +0.107 | Passes loose check |

![John List matched controls](../8.7.26/author_matched_controls/john_a_list_matched.svg)

![Michael Jensen matched controls](../8.7.26/author_matched_controls/michael_c_jensen_matched.svg)

![Manuel Arellano matched controls](../8.7.26/author_matched_controls/manuel_arellano_matched.svg)

![Robert Solow matched controls](../8.7.26/author_matched_controls/robert_m_solow_matched.svg)

The large positive differences for List and Jensen cannot be interpreted as
effects because their focal and control pretrends are not parallel. Arellano's
comparison is negative. Solow's is slightly positive, but the matched controls
have extremely low citation levels.

Underlying results:
[matched-control summary](../8.7.26/author_matched_controls/matched_control_summary.csv)
and [matched pairs](../8.7.26/author_matched_controls/matched_pairs.csv).

## Current conclusion

The author cases are useful diagnostics but do not yet provide persuasive
causal evidence. They establish three priorities:

1. Use complete all-field portfolios when classifying big hits.
2. Validate author identities and cluster versions before selecting cases.
3. Match controls on pre-event citation trajectories, not metadata alone.
