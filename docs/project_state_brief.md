# Database Project Direction

This is the concise project-status reference for presentations. The audience is
assumed to know the research question.

## Current Data State

The OpenAlex structured snapshot is the source of truth: 596 GB across 2,127
compressed work files. The subject extraction is complete for 27 subjects and currently
contains:

| Dataset | Rows |
|---|---:|
| Works | 266,352,099 |
| Work-author links | 654,286,310 |
| Work-year citation counts | 413,082,787 |
| Existing reference edges | 23,561,066, incomplete by subject |

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

The economics reference backfill is the active blocker. The previous process
used four long-running outputs and lost nearly all progress after interruption.
It has been replaced with 266 deterministic eight-file checkpoints, atomic
outputs, checksums, manifests, locking, and restart support.

As of 2026-07-17, the persistent process is running with 51/266 checkpoints
complete. The code and recovery tests are committed as `8c86669`; all 11 tests
pass. The existing DuckDB has not been overwritten during this backfill.

## Plan And Timeline

| Stage | Expected duration | Completion condition |
|---|---:|---|
| Finish economics reference scan | ~1–2 days | All 266 checkpoints valid |
| Validate and import economics references | 0.5–1 day | Transactional DuckDB import passes checks |
| Freeze economics sample | 0.5 day | Versioned sample and exclusion report |
| Build annual exposure components | 1–2 days | Related/unrelated exposure table with timing checks |
| Descriptive diagnostics and baseline models | 1–2 days | Reproducible panels and baseline estimates |
| Robustness and identification | 2–4 days | Leads/lags, alternative relations, self-citation and placebo tests |
| Extend to other subjects | 1–2 weeks | Same validated pipeline produces comparable estimates |

The immediate research milestone is not a finished regression. It is a
complete, validated economics fact layer from which multiple specifications can
be generated without rescanning the raw snapshot.
