# Agent Handoff: Citations Project

Last updated: 2026-06-08 UTC.

## Repository and Data Locations

- Repo: `/root/sdb1/projects/Citations`
- GitHub remote: `https://github.com/lkchss/Citations.git`
- Large OpenAlex data: `/root/sdb1/openalex/`
- Subject data root: `/root/sdb1/openalex/subjects/`
- Snapshot works JSONL gzip files: `/root/sdb1/openalex/snapshot/data/works/`

Large raw/derived data stays on the SSD and is not committed. Scripts, reports, literature review, summary outputs, plots, and HTML tables should be committed/pushed to GitHub.

## User's Current Intended Workflow

The user clarified two main workstreams:

1. Fix missing annual citation counts for non-economics subjects by recalculating citations from OpenAlex `referenced_works`, the way economics was fixed.
2. Run author-prevalence regressions:
   - Regression 1: total citations to paper `j` in year `t` on accumulated unrelated citations, paper fixed effects, and year fixed effects.
   - Regression 2: total citations to paper `j` in year `t` on accumulated unrelated citations, accumulated related citations, paper fixed effects, and year fixed effects.
   - Papers `i` and `j` are related if `i = j`, `i cites j`, or `j cites i`.

Before continuing with other-subject citation recalculation, the user specifically requested:

> first, run the economics regressions on the whole sample then print the outputs in a new html, then continue

So the immediate priority is the full-sample economics prevalence regression HTML.

## Current Running Job

As of this handoff, the full-sample economics prevalence regression pipeline has been relaunched and is running.

Command used:

```bash
setsid -f env REFERENCE_WORKERS=12 REFERENCE_BACKEND=thread \
  bash scripts/run_full_economics_prevalence_regressions.sh \
  > /root/sdb1/openalex/subjects/prevalence_regressions_full_logs/launch.log 2>&1
```

Current process at handoff:

- Runner PID: `102086`
- Build PID: `102088`
- Build command includes:
  - `--subject economics_econometrics_and_finance`
  - `--sample-mod 1`
  - `--sample-keep 1`
  - `--max-authors 0`
  - `--min-author-papers 2`
  - `--reference-workers 12`
  - `--reference-backend thread`

Current log path:

- `/root/sdb1/openalex/subjects/prevalence_regressions_full_logs/build.log`

At handoff the log had just restarted and showed:

```text
[economics_econometrics_and_finance] sampling authors
```

Check status with:

```bash
pgrep -af 'run_full_economics_prevalence|build_subject_prevalence|render_full_prevalence'
tail -n 120 /root/sdb1/openalex/subjects/prevalence_regressions_full_logs/build.log
tail -n 120 /root/sdb1/openalex/subjects/prevalence_regressions_full_logs/render.log
```

Expected outputs if successful:

- Data:
  `/root/sdb1/openalex/subjects/prevalence_regressions_full/economics_econometrics_and_finance/paper_author_year_prevalence_regression.csv.gz`
- Memmap work directory:
  `/root/sdb1/openalex/subjects/prevalence_regressions_full_work/`
- HTML report:
  `/root/sdb1/projects/Citations/reports/subjects/full_economics_prevalence_regressions.html`
- JSON summary:
  `/root/sdb1/projects/Citations/reports/subjects/full_economics_prevalence_regressions.summary.json`

The runner should commit and push the full economics HTML and summary automatically if it reaches the end.

## Why the Full Economics Job Was Restarted

The first full-economics attempt failed during reference scanning:

```text
concurrent.futures.process.BrokenProcessPool: A process in the process pool was terminated abruptly
```

Reason: with the full economics sample, the target set had about `3,934,328` works and the process backend duplicated a large target set into 12 processes. This likely hit memory pressure.

Fix committed and pushed:

- Commit: `f90f0fb Use shared reference scan for full economics`
- It adds `--reference-backend {auto,process,thread}` to `scripts/build_subject_prevalence_regression_data.py`.
- Full economics runner now defaults to `REFERENCE_BACKEND=thread`, so the large target work set is shared within one process.

## Important Commits

Recent commits on `main`:

- `f90f0fb Use shared reference scan for full economics`
- `c68636f Add full economics prevalence regression runner`
- `689bc31 Add report output index`
- `17957bf Render prevalence regressions with absorbed fixed effects`
- `bd3feac Add author prevalence literature review`
- `047604c Parallelize prevalence reference scan`
- `93c4713 Add subject prevalence regression pipeline`

## What Is Already Done

### Economics missing-citations fix

Economics annual citations have been recalculated from `referenced_works`:

- `/root/sdb1/openalex/subjects/economics_econometrics_and_finance/calculated_citations/calculated_citations_by_year.csv.gz`
- Summary:
  `/root/sdb1/openalex/subjects/economics_econometrics_and_finance/calculated_citations/calculated_citations_by_year.csv.gz.summary.json`

Economics paper-author-year panel rebuilt using calculated citations:

- `/root/sdb1/openalex/subjects/economics_econometrics_and_finance/panels/paper_author_year.csv.gz`
- Summary says:
  - `works`: `7,924,745`
  - `paper_author_pairs`: `10,377,763`
  - `panel_rows`: `191,443,144`
  - `citation_source`: `calculated_references`

Economics reports are committed under:

- `/root/sdb1/projects/Citations/reports/economics/`

### Sampled subject prevalence regressions

Sampled related/unrelated prevalence data has been built for:

- Economics
- Agricultural and Biological Sciences
- Biochemistry, Genetics, and Molecular Biology
- Physics and Astronomy

Sampled stargazer report:

- `/root/sdb1/projects/Citations/reports/subjects/prevalence_regression_stargazer_tables.html`

Commit:

- `17957bf Render prevalence regressions with absorbed fixed effects`

Important caveat: the sampled non-economics regressions still use OpenAlex `counts_by_year`, not recalculated references.

### Literature review

Committed:

- `/root/sdb1/projects/Citations/reports/literature/author_prevalence_literature_review.md`
- `/root/sdb1/projects/Citations/reports/literature/author_prevalence.bib`

Commit:

- `bd3feac Add author prevalence literature review`

### Report index

Committed:

- `/root/sdb1/projects/Citations/reports/README.md`

Commit:

- `689bc31 Add report output index`

## What Is Not Done Yet

1. Non-economics missing-citation recalculation is not done.
   - Need recalculate annual citations from `referenced_works` for:
     - `agricultural_and_biological_sciences`
     - `biochemistry_genetics_and_molecular_biology`
     - `physics_and_astronomy`
   - Possibly also other subjects later, but the user specifically has been focusing on biology/physics/economics.

2. Graphs/report outputs have not been regenerated using fixed citations for the non-economics subjects.

3. Related/unrelated regressions have not yet been rerun on non-economics fixed-citation data, because that data does not exist yet.

4. Full-sample economics prevalence regression is currently running and not yet complete.

## Untracked Local File

There is an untracked helper script from an interrupted turn:

- `scripts/run_target_subject_calculated_citations.sh`

It was created to sequentially recalculate citations for:

- `agricultural_and_biological_sciences`
- `biochemistry_genetics_and_molecular_biology`
- `physics_and_astronomy`

It has not been committed because the user interrupted and asked to run full economics first. Review it before using or committing.

## Next Steps

1. Monitor the full economics job until it either finishes or fails.
2. If it fails:
   - inspect `/root/sdb1/openalex/subjects/prevalence_regressions_full_logs/build.log`
   - likely next fix is a truly author-sharded builder, because full sample may exceed memory during relation-set or row-writing phases.
3. If it succeeds:
   - verify the HTML report exists.
   - verify it was committed/pushed by the runner.
   - then resume non-economics citation recalculation.
4. For non-economics citation recalculation:
   - review `scripts/run_target_subject_calculated_citations.sh`
   - run subjects sequentially, not concurrently, to avoid rescanning the 596GB snapshot three times at once.
   - after recalculated citations exist, rebuild subject panels and regenerate graphs/regressions using fixed citation counts.

