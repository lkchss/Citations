# Project Context

Last updated: 2026-07-17 UTC.

This file is the GitHub-tracked context entry point for future agents and
models. Keep it current whenever workflow, outputs, running jobs, or data
structure changes.

## Operating Rules

- Push new durable content to GitHub: scripts, docs, report indexes, rendered
  HTML/Markdown/CSV summaries, and project context updates.
- Do not commit large raw or derived data. Those live on the SSD under
  `/root/sdb1/openalex/`.
- Keep `PROJECT_CONTEXT.md` and `AGENT_HANDOFF.md` synchronized with any
  meaningful state change that another model would need to continue the work.
- Prefer digestible normalized tables over repeated raw snapshot scans.

## Repository And Data

- Repo: `/root/sdb1/projects/Citations`
- Remote: `https://github.com/lkchss/Citations.git`
- OpenAlex root: `/root/sdb1/openalex/`
- Snapshot works: `/root/sdb1/openalex/snapshot/data/works/`
- Subject tables: `/root/sdb1/openalex/subjects/<subject>/tables_parts/`

Temporary staging repo while the original OpenAlex disk is offline:

```text
/root/projects/Citations
```

Staging notes:

```text
STAGING_CONTEXT.md
docs/recovery_after_data_disk_return.md
```

The raw snapshot is gzip JSONL partitioned by `updated_date`, not by subject or
publication year:

```text
/root/sdb1/openalex/snapshot/data/works/updated_date=YYYY-MM-DD/part_XXXX.gz
```

Each work record contains nested authorship, topic, citation, and reference
metadata. Repeated JSON snapshot scans are very expensive.

## Current Research Goal

The main analysis asks whether annual citations to paper `j` rise with citations
to an author's other papers. Current prevalence regressions estimate:

```text
citations_jt ~ accumulated_unrelated_citations_jt + paper FE + year FE
citations_jt ~ accumulated_unrelated_citations_jt + accumulated_related_citations_jt + paper FE + year FE
```

Papers are related if `i = j`, `i cites j`, or `j cites i`. For the fast
lifetime pilot below, relation lookup was deliberately skipped, so related means
self-only.

The canonical database architecture and research-linked execution plan are
documented in `docs/research_warehouse_design.md`. The durable warehouse keeps
normalized facts separate from versioned samples, relationship definitions,
annual exposure components, and disposable specification-specific panels.

## Completed Outputs

### Lifetime Pilot

Report:

```text
reports/subjects/lifetime_pilot_prevalence_regressions.html
```

Data root:

```text
/root/sdb1/openalex/subjects/prevalence_regressions_lifetime_pilot/
```

This pilot samples authors across 10 diverse fields, keeps each sampled
author's full subject-paper history for exposure stocks, then samples focal
papers and writes each retained focal paper's full lifetime rows.

Pilot subjects:

- `economics_econometrics_and_finance`
- `social_sciences`
- `psychology`
- `arts_and_humanities`
- `agricultural_and_biological_sciences`
- `medicine`
- `physics_and_astronomy`
- `computer_science`
- `environmental_science`
- `mathematics`

Important caveat: the completed fast pilot used `--skip-reference-scan` and
should be treated as a pipeline/data-shape diagnostic, not as a substantive
estimate. Therefore:

- full paper lifetimes are preserved;
- author exposure stocks are computed;
- related papers are self-only;
- citation-network relatedness exclusions are not yet applied.

Highly significant negative coefficients in this report are not reliable
evidence against the hypothesis. The self-only related stock is the focal
paper's own lagged cumulative citations, so after paper and year fixed effects
it can mostly capture citation lifecycle/mean-reversion dynamics. Non-economics
subjects also still use sparse OpenAlex `counts_by_year` rather than
recalculated annual citations.

### Economics Citation Fix

Economics annual citations were recalculated from OpenAlex `referenced_works`:

```text
/root/sdb1/openalex/subjects/economics_econometrics_and_finance/calculated_citations/calculated_citations_by_year.csv.gz
```

Economics panel rebuilt with calculated citation counts:

```text
/root/sdb1/openalex/subjects/economics_econometrics_and_finance/panels/paper_author_year.csv.gz
```

## Current Running Job / Disk State

As of 2026-07-17, the OpenAlex NTFS data disk is mounted at `/root/sdb1` and
the 44 GB subject DuckDB is present. The canonical working checkout is
`/root/projects/Citations`; the checkout stored on the data disk may lag it.

Check the environment with:

```bash
python3 scripts/check_openalex_environment.py \
  --repo-dir /root/projects/Citations \
  --openalex-root /root/sdb1/openalex
```

The resumable economics reference backfill was launched as systemd unit
`openalex-economics-reference-backfill.service`. It divides 2,127 snapshot
files into 266 deterministic eight-file chunks and publishes each chunk with
an atomic output and checksum-backed manifest. Progress survives interruption.

Check progress with:

```bash
pgrep -af 'backfill_subject_work_references_resumable'
tail -n 40 /root/sdb1/openalex/subjects/reference_backfill_logs/economics_reference_backfill_resumable.log
find /root/sdb1/openalex/subjects/economics_econometrics_and_finance/.reference_backfill/chunks \
  -maxdepth 1 -name '*.json' | wc -l
```

The low-memory sequential reference backfill should resume after the data disk
returns so future analyses can use digestible `work_references` table parts
rather than scanning the raw snapshot. It was restarted on 2026-06-10 after
earlier partial economics gzip outputs were found to be corrupt. The backfill writer now writes
`part_XXXX_work_references.csv.gz.tmp` and atomically renames it only after a
worker finishes cleanly, so interrupted runs should not leave invalid final
gzip files.

Check status:

```bash
pgrep -af 'run_reference_backfill_sequential|backfill_subject_work_references'
tail -n 40 /root/sdb1/openalex/subjects/reference_backfill_logs/sequential.log
tail -n 80 /root/sdb1/openalex/subjects/reference_backfill_logs/economics_econometrics_and_finance.backfill.log
```

Current command family:

```bash
env BACKFILL_WORKERS=4 ./scripts/run_reference_backfill_sequential.sh
```

This runs one subject at a time to avoid holding all subject work IDs in memory.
The earlier all-subject backfill loaded 158.9M work IDs into one Python dict,
used about 13.5 GiB RSS, and was stopped.

As of the latest status check, the active subject is
`economics_econometrics_and_finance`. It has loaded 7,924,745 subject work IDs
and opened four atomic temp output files. No valid final economics
`work_references` part should be expected until one worker finishes its snapshot
chunk and renames its temp file.

## Digestible Data Plan

Subject `tables_parts` should contain:

```text
part_XXXX_works.csv.gz
part_XXXX_work_authors.csv.gz
part_XXXX_work_citations_by_year.csv.gz
part_XXXX_work_references.csv.gz
```

`work_references` columns:

```text
work_id,referenced_work_id
```

Implemented:

- `scripts/build_subject_tables_from_snapshot.py` writes `work_references`
  parts in future table builds.
- `scripts/backfill_subject_work_references.py` backfills references for
  existing subject tables.
- `scripts/run_reference_backfill_sequential.sh` runs that backfill one subject
  at a time with bounded memory.
- `scripts/run_reference_backfill_sequential.sh` no longer overwrites final
  reference parts by default. Set `BACKFILL_OVERWRITE=1` only when deliberately
  rebuilding a partially completed subject.
- `scripts/build_subject_prevalence_regression_data.py` prefers
  `work_references` table parts under `--reference-source auto`.

## Next Recommended Steps

1. Let the sequential reference backfill finish for the 10 pilot subjects.
2. Rerun the lifetime pilot with real relation edges using the new table parts:

   ```bash
   SKIP_REFERENCE_SCAN=0 SHARED_REFERENCE_SCAN=1 bash scripts/run_pilot_lifetime_prevalence_regressions.sh
   ```

   Once all selected subjects have `work_references` parts, this should avoid
   raw snapshot scans.

3. Compare the self-only fast pilot against the relation-aware pilot.
4. Continue non-economics calculated citation backfills for annual citation
   counts from `referenced_works`.

## Key Scripts

- `scripts/run_pilot_lifetime_prevalence_regressions.sh`
- `scripts/build_subject_prevalence_regression_data.py`
- `scripts/build_subject_tables_from_snapshot.py`
- `scripts/backfill_subject_work_references.py`
- `scripts/run_reference_backfill_sequential.sh`
- `scripts/monitor_process_speed_agent.py`
- `scripts/pilot_pipeline_optimizer_agent.py`
