# Database Project Direction

This is the concise project-status reference for presentations. The audience is
assumed to know the research question.

## What The Database Is

A relational database stores information in separate tables and connects those
tables through shared identifiers. Each table records one kind of fact, and a
key such as `work_id` or `author_id` tells us how facts in different tables
refer to the same paper or person.

For example, `works` has one row per paper. `work_authors` links papers to
authors, and `work_citations_by_year` records how many citations a paper
received in each year. We can join those tables to ask questions such as which
authors are associated with a paper, how their other papers performed, and how
those outcomes changed over time. `work_references` adds the paper-to-paper
network needed to identify related and unrelated work.

This structure avoids copying the same paper metadata into every author-year
observation. It also keeps the underlying facts separate from choices made for
one regression. New samples, exposure measures, fixed effects, and event-study
panels can therefore be generated from the same source tables.

## Current Data State

The OpenAlex structured snapshot is the source of truth: 596 GB across 2,127
compressed work files. The subject extraction is complete for 27 subjects and currently
contains:

| Dataset | Rows |
|---|---:|
| Works | 266,352,099 |
| Work-author links | 654,286,310 |
| Work-year citation counts | 413,082,787 |
| Reference edges | 70,839,054; economics complete, other subjects incomplete |

These tables are stored as bounded subject shards and queried through a 44 GB
DuckDB database. Economics contains 7,924,745 works. Its annual citation
counts have already been reconstructed from citation edges.

The pipeline uses Python for streaming JSONL extraction, normalization,
validation, and checkpointed processing. It is a structured-data ingestion
system, not a web-scraping or search-engine workflow. DuckDB is the local
analytical database and query engine.

The database is deliberately layered:

1. Canonical facts: works, authors, authorships, annual citations, references,
   subjects, sources, and institutions.
2. Versioned research definitions: samples, relatedness rules, events, and
   exclusion decisions.
3. Annual exposure components: focal-paper outcomes and related/unrelated
   author exposure by year.
4. Specification-specific panels: generated for each econometric design rather
   than stored as the permanent database.

See the [database architecture drawing](assets/subject_database_architecture.svg).

## Current Engineering State

The economics reference layer is complete. The replacement backfill used 266
deterministic eight-file checkpoints with atomic outputs, checksums, manifests,
locking, and restart support. All 2,127 snapshot files were scanned, producing
47,277,988 economics reference edges for 7,924,745 economics works.

The reference shards have been imported into DuckDB. Post-import checks match
the shard manifest and report zero orphan citing-paper IDs. The code and
recovery tests are committed as `8c86669`; all 11 tests pass.

A relation-aware economics panel now builds directly from the DuckDB-backed
reference shards. The first substantive construction contains 211,825
post-publication paper-author-year rows, 2,853 authors, and 14,675 focal works.
It is a sample construction product pending citation-coverage and econometric
diagnostics, not yet a final estimate.

A provisional fixed-effects diagnostic has now been run on this panel using
reconstructed annual citations. With paper and year effects absorbed, the
joint specification gives a related-exposure coefficient of 0.00492 and an
unrelated-exposure coefficient of -0.000511. These are engineering diagnostics,
not research estimates: the current renderer uses normal-approximation,
work-clustered standard errors, and the citation-total reconciliation below is
not yet closed.

Initial outcome validation finds exact lifetime-total agreement for 14,544 of
14,675 sampled focal works. The remaining 131 works have reconstructed totals
that exceed OpenAlex totals by 277 citations in aggregate; this discrepancy is
being investigated before the panel is used for substantive estimates. A
repeatable coverage validator confirms that all sampled focal works have a
reconstructed total; the remaining issue is the 131-work overcount discrepancy.

The research-layer entry point is
`scripts/build_economics_exposure_from_duckdb.py`. It performs sampling, joins,
relatedness classification, and lagged exposure aggregation in DuckDB, then
writes only the final compressed panel in bounded Python batches.
The current baseline definition is recorded in
`configs/economics_baseline_exposure.json`; it remains marked pending until the
citation reconciliation is resolved.

## Plan And Timeline

| Stage | Expected duration | Completion condition |
|---|---:|---|
| Freeze economics sample | 0.5 day | Versioned sample and exclusion report |
| Build annual exposure components | 1–2 days | Related/unrelated exposure table with timing checks |
| Descriptive diagnostics and baseline models | 1–2 days | Reproducible panels and baseline estimates |
| Robustness and identification | 2–4 days | Leads/lags, alternative relations, self-citation and placebo tests |
| Extend to other subjects | 1–2 weeks | Same validated pipeline produces comparable estimates |

The immediate research milestone is to close citation reconciliation, freeze
the economics sample, and replace the provisional regression renderer with a
specification-aware estimator that supports clustered inference and explicit
identification checks. The resulting fact layer should generate multiple
specifications without rescanning the raw snapshot.
