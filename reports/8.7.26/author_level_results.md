# Author-level citation-prominence results

This document connects the author-level outputs generated during the August 7,
2026 exploratory session. All estimates are descriptive and provisional.

## Research question and definitions

We ask whether an author's rise in prominence spills over into citations to
their older, unrelated papers.

- Candidate treatment begins in the hit paper's publication year.
- The baseline hit threshold is a paper with more than 50% of the author's
  citations and at least 101 citations.
- An older focal paper is “unrelated” when the candidate hit does not reference it.
- The current economics screen uses an economics-only portfolio denominator.
- Live all-field OpenAlex totals are reported separately and are not assumed to
  be ground truth because author entities can be merged or contaminated.

## Candidate screen

The economics screen produced 5,000 raw candidates and a 2,181-row research
shortlist. It is a lead generator rather than a validated treatment sample.

- [Candidate-screen writeup](big_hit_screen/economics_big_hit_candidates.md)
- [Complete research shortlist](big_hit_screen/economics_big_hit_research_shortlist.csv)
- [Screen audit](big_hit_screen/economics_big_hit_screen_audit.json)

## John List: gradual prominence case

John List is not a baseline 50% big-hit author. His top economics paper accounts
for 10.1% of 11,977 local economics
citations. The fixed cohort contains 49
older papers not referenced by the 2003 candidate.

- Mean citations per focal paper: **1.18** in
  2002 and **3.02** in 2007–09.
- The top five focal papers account for
  **87.4%** of the net increase.
- Local work citations and reconstructed citations agree within 0.44%, while
  the live OpenAlex author total is much larger and appears identity-contaminated.

![John List original unadjusted figure](john_list_case_study/unrelated_prior_citations.svg)

- [Full John List writeup](john_list_case_study/john_list_case_study.md)
- [Citation reconciliation](john_list_citation_reconciliation.md)
- [Paper-year data](john_list_case_study/paper_year.csv)
- [Paper-level contributions](john_list_case_study/paper_contributions.csv)

## Jensen, Arellano, and Solow

The denominator materially changes candidate classification.

![Economics versus all-field hit shares](author_hit_profiles/hit_share_denominator_comparison.svg)

| Author | Hit year | Economics share | All-field share | Prior clusters | Raw change | All-field >50%? |
|---|---:|---:|---:|---:|---:|---|
| Michael C. Jensen | 1976 | 69.5% | 35.2% | 10 | +5.740 | no |
| Manuel Arellano | 1991 | 57.7% | 52.8% | 12 | +0.150 | yes |
| Robert M. Solow | 1956 | 56.0% | 35.8% | 15 | +0.093 | no |

### Original unadjusted figures

![Michael Jensen original profile](author_hit_profiles/michael_c_jensen_event_time.svg)

![Manuel Arellano original profile](author_hit_profiles/manuel_arellano_event_time.svg)

![Robert Solow original profile](author_hit_profiles/robert_m_solow_event_time.svg)

- [Full three-author writeup](author_hit_profiles/author_hit_profiles.md)
- [Headline profile table](author_hit_profiles/author_hit_profiles.csv)
- [Event-time data](author_hit_profiles/author_hit_event_time.csv)
- [Version-clustered prior works](author_hit_profiles/eligible_prior_works.csv)

## Matched-control comparisons

Each focal paper is paired with a unique sampled OpenAlex work matching
publication year and document type, plus primary topic where available.

| Author | Focal papers | Focal change | Control change | Difference | Pretrend slope gap | Parallel flag |
|---|---:|---:|---:|---:|---:|---|
| John A. List | 49 | +1.686 | +0.710 | +0.976 | +0.169 | no |
| Michael C. Jensen | 10 | +5.740 | +0.520 | +5.220 | +0.630 | no |
| Manuel Arellano | 12 | +0.150 | +0.400 | -0.250 | +0.025 | yes |
| Robert M. Solow | 15 | +0.093 | -0.013 | +0.107 | +0.020 | yes |

![John List matched controls](author_matched_controls/john_a_list_matched.svg)

![Michael Jensen matched controls](author_matched_controls/michael_c_jensen_matched.svg)

![Manuel Arellano matched controls](author_matched_controls/manuel_arellano_matched.svg)

![Robert Solow matched controls](author_matched_controls/robert_m_solow_matched.svg)

- [Matched-control methodology and interpretation](author_matched_controls/README.md)
- [Matched-control summary](author_matched_controls/matched_control_summary.csv)
- [Matched event-time data](author_matched_controls/matched_control_event_time.csv)
- [All matched pairs](author_matched_controls/matched_pairs.csv)

## Interpretation

- John List and Michael Jensen show large positive focal-minus-control changes,
  but both fail the preliminary parallel-pretrend diagnostic.
- Manuel Arellano passes the loose pretrend check but has a negative
  focal-minus-control change; his OpenAlex entity also contains an obvious 1912
  namesake record.
- Robert Solow has a small positive difference and passes the loose pretrend
  check, but his control citation levels are extremely low.
- None of these comparisons should currently be described as causal effects.

## Next author-level improvements

1. Validate author identity and intellectual-work clusters manually.
2. Match multiple controls on pre-event citation trajectories, not only metadata.
3. Require common pre-event support and report uncertainty across control draws.
4. Estimate paper-level count models when the complete panel becomes available.
