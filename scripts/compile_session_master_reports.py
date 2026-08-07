#!/usr/bin/env python3
"""Compile author- and subject-level August 7 outputs into two Markdown reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "reports" / "8.7.26"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def author_report() -> str:
    profiles = read_csv(ROOT / "author_hit_profiles/author_hit_profiles.csv")
    controls = {row["author_name"]: row for row in read_csv(ROOT / "author_matched_controls/matched_control_summary.csv")}
    john = json.loads((ROOT / "john_list_case_study/provenance.json").read_text())
    profile_table = "\n".join(
        f"| {row['openalex_name']} | {row['hit_year']} | {float(row['local_economics_hit_share']):.1%} | {float(row['live_all_field_hit_share']):.1%} | {row['eligible_prior_unrelated_clusters']} | {float(row['raw_difference']):+.3f} | {'yes' if row['baseline_big_hit_all_field']=='1' else 'no'} |"
        for row in profiles
    )
    control_table = "\n".join(
        f"| {name} | {int(row['focal_papers'])} | {float(row['focal_change']):+.3f} | {float(row['control_change']):+.3f} | {float(row['difference_in_changes']):+.3f} | {float(row['pretrend_slope_gap']):+.3f} | {'yes' if row['parallel_pretrend_flag']=='1' else 'no'} |"
        for name, row in controls.items()
    )
    return f"""# Author-level citation-prominence results

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
for {john['hit_share']:.1%} of {john['portfolio_citations']:,} local economics
citations. The fixed cohort contains {john['eligible_unrelated_prior_papers']}
older papers not referenced by the 2003 candidate.

- Mean citations per focal paper: **{john['fixed_cohort_mean_2002']:.2f}** in
  2002 and **{john['fixed_cohort_mean_2007_2009']:.2f}** in 2007–09.
- The top five focal papers account for
  **{john['growth_concentration_top_5']:.1%}** of the net increase.
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
{profile_table}

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
{control_table}

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
"""


def subject_report() -> str:
    raw = json.loads((ROOT / "economics_subject_level/economics_big_hit_subject_summary.json").read_text())
    adjusted = json.loads((ROOT / "economics_adjusted/summary.json").read_text())
    normalized_meta = json.loads((ROOT / "economics_paper_level_normalized/metadata.json").read_text())
    normalized_rows = read_csv(ROOT / "economics_paper_level_normalized/normalized_pre_post_summary.csv")
    normalized = {(row["sample"],row["metric"]):row for row in normalized_rows}
    risk = read_csv(ROOT / "economics_adjusted/at_risk_event_time.csv")
    risk_by_event = {int(row["event_time"]): row for row in risk}
    comparison = "\n".join([
        f"| Original row-balanced | {raw['pre_mean_event_minus_5_to_minus_1']:.3f} | {raw['post_mean_event_0_to_4']:.3f} | {raw['difference']:+.3f} | Includes pre-publication pseudo-observations |",
        f"| Mature-paper age standardized | {adjusted['pre_mean']:.3f} | {adjusted['post_mean']:.3f} | {adjusted['raw_difference']:+.3f} | Fixed t=-1 weights; ages 3+ |",
    ])
    return f"""# Economics subject-level citation-prominence results

This document connects the raw economics event study, balance diagnosis,
risk-set correction, and age-standardized specification. Results are
descriptive and do not identify a causal effect.

## Baseline economics result

The deduplicated panel contains **{raw['focal_pairs']:,}** author–focal–hit
units across **{raw['authors']:,}** OpenAlex author entities. Mean annual
citations rise from **{raw['pre_mean_event_minus_5_to_minus_1']:.3f}** in event
years -5:-1 to **{raw['post_mean_event_0_to_4']:.3f}** in 0:+4, a raw difference
of **{raw['difference']:+.3f}**.

![Original economics event-time figure](economics_subject_level/economics_big_hit_event_time.svg)

- [Original subject writeup](economics_subject_level/economics_big_hit_subject_summary.md)
- [Original event-time data](economics_subject_level/economics_big_hit_event_time.csv)

## Balance and risk-set diagnosis

The panel is row-balanced—each event year contains the same nominal units—but
it is not publication-risk balanced. At event time -10,
**{float(risk_by_event[-10]['prepublication_share_original']):.1%}** of nominal
rows occur before the focal paper was published. The share falls to
**{float(risk_by_event[-5]['prepublication_share_original']):.1%}** at event -5
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
{comparison}

Age standardization reduces the raw difference from **{raw['difference']:+.3f}**
to **{adjusted['raw_difference']:+.3f}**, a reduction of
**{1-adjusted['raw_difference']/raw['difference']:.1%}**.

- [Adjustment methodology](economics_adjusted/README.md)
- [Age-standardized event data](economics_adjusted/mature_age_standardized_event_time.csv)
- [Adjustment summary](economics_adjusted/summary.json)

## Paper-level lifecycle and calendar-year normalization

The recovered author–paper–year panel permits a stronger adjustment. Expected
citations are estimated from deduplicated economics works in the same calendar
year, paper age, and document type. The genuinely balanced cohort requires all
21 event years (-10:+10) to be observed for each author–focal–hit unit.

- Balanced units: **{normalized_meta['balanced_units']:,}**
- Balanced authors: **{normalized_meta['balanced_authors']:,}**
- Observations per balanced event year: **{normalized_meta['balanced_units']:,}**

| Sample | Excess-citation change | Observed/expected change |
|---|---:|---:|
| Publication at-risk | {float(normalized[('at_risk','mean_excess_citations')]['difference']):+.3f} | {float(normalized[('at_risk','observed_expected_ratio')]['difference']):+.3f} |
| Fully balanced -10:+10 | {float(normalized[('balanced_full_window','mean_excess_citations')]['difference']):+.3f} | {float(normalized[('balanced_full_window','observed_expected_ratio')]['difference']):+.3f} |

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
"""


def main() -> None:
    author_path = ROOT / "author_level_results.md"
    subject_path = ROOT / "subject_level_results.md"
    author_path.write_text(author_report(), encoding="utf-8")
    subject_path.write_text(subject_report(), encoding="utf-8")
    print(author_path)
    print(subject_path)


if __name__ == "__main__":
    main()
