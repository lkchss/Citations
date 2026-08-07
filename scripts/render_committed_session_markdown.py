#!/usr/bin/env python3
"""Render committed August 7 session CSV/JSON outputs as Markdown."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "reports" / "8.7.26"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def clean(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_subject() -> None:
    directory = ROOT / "economics_subject_level"
    data = rows(directory / "economics_big_hit_event_time.csv")
    summary = json.loads((directory / "economics_big_hit_subject_summary.json").read_text())
    table = "\n".join(f"| {int(r['event_time']):+d} | {float(r['mean_citations']):.3f} | {float(r['mean_change_from_t_minus_1']):+.3f} | {float(r['share_with_positive_citations']):.1%} |" for r in data)
    text = f"""# Economics subject-level big-hit summary

> **Descriptive, not causal.** The treatment denominator is restricted to the
> economics portfolio. Author identity, work versions, and a counterfactual
> group remain unresolved.

- Authors: **{summary['authors']:,}**
- Author-hit events: **{summary['author_hit_events']:,}**
- Focal pairs: **{summary['focal_pairs']:,}**
- Mean citations, event -5:-1 versus 0:+4: **{summary['pre_mean_event_minus_5_to_minus_1']:.3f} → {summary['post_mean_event_0_to_4']:.3f}**
- Raw difference: **{summary['difference']:+.3f}**

![Economics event-time figure](economics_big_hit_event_time.svg)

| Event time | Mean citations | Change from -1 | Positive share |
|---:|---:|---:|---:|
{table}
"""
    (directory / "economics_big_hit_subject_summary.md").write_text(text, encoding="utf-8")


def render_screen() -> None:
    directory = ROOT / "big_hit_screen"
    audit = json.loads((directory / "economics_big_hit_screen_audit.json").read_text())
    data = rows(directory / "economics_big_hit_research_shortlist.csv")[:250]
    table = "\n".join(f"| {clean(r['author_name'])} | {clean(r['hit_title'])} | {r['hit_publication_year']} | {int(r['hit_cited_by_count']):,} | {int(r['economics_portfolio_citations']):,} | {float(r['hit_share']):.1%} | {r['prior_works']} |" for r in data)
    text = f"""# Economics big-hit author candidates

> **Screening output, not final classification.** Shares use economics research
> works rather than complete all-field portfolios.

- Raw rows written: **{audit['rows_written']:,}**
- Research shortlist: **{audit['shortlist_rows']:,}**
- Minimum economics citations: **{audit['minimum_author_citations']:,}**
- Strict minimum hit share: **>{audit['minimum_hit_share_strict']:.0%}**

The table displays the first 250 shortlisted rows. The complete shortlist is in
[`economics_big_hit_research_shortlist.csv`](economics_big_hit_research_shortlist.csv).

| Author | Candidate hit | Year | Hit cites | Portfolio cites | Share | Prior works |
|---|---|---:|---:|---:|---:|---:|
{table}
"""
    (directory / "economics_big_hit_candidates.md").write_text(text, encoding="utf-8")


def render_john() -> None:
    directory = ROOT / "john_list_case_study"
    p = json.loads((directory / "provenance.json").read_text())
    contributions = rows(directory / "paper_contributions.csv")[:10]
    works = rows(directory / "author_works.csv")[:20]
    ctable = "\n".join(f"| {clean(r['title'])} | {r['publication_year']} | {float(r['citations_2002']):.1f} | {float(r['mean_citations_2007_2009']):.1f} | {float(r['change']):+.1f} |" for r in contributions)
    wtable = "\n".join(f"| {r['citation_rank']} | {clean(r['title'])} | {r['publication_year']} | {int(r['cited_by_count']):,} | {float(r['portfolio_citation_share']):.1%} | {'yes' if r['eligible_unrelated_prior']=='1' else 'no'} |" for r in works)
    text = f"""# John List: exploratory citation-spillover case study

OpenAlex author: `{p['author_id']}`. Descriptive output; not a causal estimate.

> **Baseline diagnostic:** The top paper accounts for only
> {p['hit_share']:.1%} of the economics portfolio, so John List is not treated
> under the baseline 50% definition.

- Economics works: **{p['works']}**
- Economics-portfolio citations: **{p['portfolio_citations']:,}**
- Unrelated prior papers: **{p['eligible_unrelated_prior_papers']}**

## Fixed-cohort timeline

The fixed cohort rises from **{p['fixed_cohort_mean_2002']:.2f}** citations per
paper in 2002 to **{p['fixed_cohort_mean_2007_2009']:.2f}** in 2007–09.

![Citation time series](unrelated_prior_citations.svg)

## Where the increase comes from

The top 1, 5, and 10 focal papers account for
{p['growth_concentration_top_1']:.1%}, {p['growth_concentration_top_5']:.1%},
and {p['growth_concentration_top_10']:.1%} of the net increase.

| Prior paper | Year | 2002 | 2007–09 mean | Change |
|---|---:|---:|---:|---:|
{ctable}

## Top portfolio works

| Rank | Title | Year | Citations | Share | Eligible focal |
|---:|---|---:|---:|---:|---|
{wtable}

## Data notes

- Annual outcomes use reconstructed economics citations.
- Portfolio shares are economics-only, not all-field career shares.
- Same-year and post-hit papers are excluded.
- All citations, including later self-citations, are counted.
- Work versions and OpenAlex identity errors remain unresolved.
"""
    (directory / "john_list_case_study.md").write_text(text, encoding="utf-8")


def main() -> None:
    render_subject(); render_screen(); render_john()
    print("rendered 3 Markdown reports")


if __name__ == "__main__":
    main()
