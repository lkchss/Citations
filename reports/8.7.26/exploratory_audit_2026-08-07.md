# Economics Citation-Prominence Exploratory Audit

Date: 2026-08-07 UTC

## Objective

Measure whether an author's rise in prominence is followed by additional
citations to the author's older papers that are unrelated to the
prominence-generating work. The current phase is descriptive: individual
author histories, time series, subject summaries, and simple regressions come
before a final causal design.

## Agreed Working Definitions

- A baseline big hit is an author-specific paper that accounts for more than
  50% of the author's citations, conditional on roughly 100 or more author
  citations.
- Treatment timing is the hit paper's publication year.
- Coauthors are classified separately; a paper can be a hit for one coauthor
  but not another.
- An older focal paper is unrelated when the hit paper does not cite it.
- All citations remain in the primary outcome. Excluding later self-citations
  is a robustness option.
- Threshold-crossing dates, field-normalized hits, fixed citation thresholds,
  and publication clusters are alternative definitions.

## John A. List Pilot

OpenAlex author: `A5083530241`.

- 187 economics-classified OpenAlex works.
- 11,977 current citations in the economics portfolio.
- Highest-cited candidate: *Does Market Experience Eliminate Market
  Anomalies?* (2003), 1,214 current citations.
- Candidate share: 10.14%, so List is not a literal 50% big-hit author under
  this economics-only denominator.
- 49 older economics papers are not cited by the 2003 candidate.
- Fixed-cohort mean annual citations per paper:
  - 2002: 1.18
  - 2003–04: 1.87
  - 2005–06: 2.24
  - 2007–09: 3.02
- The five largest focal-paper increases account for 87.4% of the net increase.

Interpretation: List is a useful gradual-prominence and mechanism case, not a
clean single-hit case. The 2003–06 publication cluster overlaps his 2005 move
to Chicago, citations were already rising, and most of the aggregate growth is
concentrated in a few focal papers.

## Economics-Wide Big-Hit Screen

The initial DuckDB screen uses articles, preprints, and reviews classified in
economics. It requires:

- economics-portfolio citations of at least 100;
- strict top-paper share above 50%; and
- at least three older research works.

The first output contains the top 5,000 raw candidates ordered by portfolio
citations. A research shortlist of 2,181 rows additionally requires at least
100 citations across earlier works, at least three cited earlier works, and no
more than ten authors on the candidate hit.

Promising high-citation records include Michael Jensen, Manuel Arellano,
Robert Solow, Burton Malkiel, Herbert Simon, Elinor Ostrom, Andrew Levin,
Sherwin Rosen, and others. These are candidates for validation, not confirmed
treatments.

## Database Quality Findings

1. **The denominator is subject-truncated.** The current economics tables do
   not necessarily contain every work by an author. Treatment classification
   therefore requires an all-field OpenAlex author portfolio before it can be
   labeled final.
2. **Authorship errors are visible.** Examples in the raw screen attach Joseph
   Schumpeter to Keynes's *General Theory* and Michael Munger to North's
   *Institutions*. Every finalist needs identity and work-authorship checks.
3. **Version duplication is visible.** Article/preprint or edition records can
   duplicate one scholarly output, inflating work counts and denominators.
4. **Subject leakage is substantial.** Medical guidelines and other
   cross-disciplinary works appear in the economics extraction through their
   assigned topics.
5. **Citation vintages differ slightly.** John List has 11,977 current
   `cited_by_count` citations but 12,030 reconstructed annual reference
   citations, a 0.44% difference that must be tracked.
6. **Reference completeness must be checked.** Absence of a hit→focal edge is
   meaningful only when the hit bibliography was captured completely.
7. **The DuckDB environment was not portable.** The saved virtual environment
   retained its former `/root/sdb1` path. DuckDB works after loading the package
   from an internal Linux path, and spill files must not be placed on NTFS.
8. **The SSD mount reset during the audit.** The device re-enumerated from
   `/dev/sdb1` to `/dev/sdc1`; mounting by UUID restored access. Persistent
   configuration should use UUID `3EA0CDF6A0CDB4A5`.

## Output Files

- `reports/economics/john_list_case_study/john_list_case_study.html`
- `reports/economics/john_list_case_study/author_works.csv`
- `reports/economics/john_list_case_study/paper_year.csv`
- `reports/economics/john_list_case_study/paper_contributions.csv`
- `reports/economics/john_list_case_study/event_time.csv`
- `reports/economics/big_hit_screen/economics_big_hit_candidates.html`
- `reports/economics/big_hit_screen/economics_big_hit_candidates.csv`
- `reports/economics/big_hit_screen/economics_big_hit_research_shortlist.csv`
- `reports/economics/big_hit_screen/economics_big_hit_screen_audit.json`

## Immediate Plan

1. Resolve full OpenAlex portfolios for the highest-value candidate authors.
2. Deduplicate versions/editions into scholarly outputs.
3. Verify candidate authorship and identity, beginning with a manually curated
   group rather than trusting the raw rank.
4. Recompute the hit share using the full-author denominator.
5. Validate hit bibliography completeness and construct unrelated focal sets.
6. Generate comparable author reports for confirmed hits.
7. Aggregate confirmed economics cases into descriptive event-time figures and
   simple regressions.
8. Repair the portable environment and canonical paths.
9. After economics outputs stabilize, complete annual citation and reference
   coverage for the remaining subjects.

## Related Evidence

- Brogaard, Engelberg, Eswar, and Van Wesep (2024), “The Effect of Fame on
  Citations,” *Management Science*:
  <https://ideas.repec.org/a/inm/ormnsc/v70y2024i10p7187-7214.html>
- Prior cross-field evidence on landmark work and citations to older papers:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC3087729/>
