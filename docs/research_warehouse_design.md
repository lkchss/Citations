# Research Warehouse Design And Execution Plan

## Research Objective

The warehouse supports a family of questions about citation spillovers across
an author's portfolio. The initial specification asks whether annual citations
to focal paper `j` increase when the same author's other papers receive
citations, after separating related from unrelated papers and controlling for
paper and calendar-year effects.

The database is not a regression panel. It preserves durable facts at their
lowest useful unit so samples, treatments, outcomes, networks, fixed effects,
and event studies can be redefined without rescanning the OpenAlex snapshot.

The governing rule is:

> Store durable facts once; construct econometric variables and panels as
> versioned downstream products.

## Logical Architecture

```text
OpenAlex snapshot
  -> canonical entities and relationships
  -> time-indexed citation and network facts
  -> versioned samples, relationship definitions, and events
  -> specification-specific panels
  -> estimates, diagnostics, and reports
```

### Canonical Fact Layer

The canonical layer should remain normalized and independent of a particular
econometric specification.

| Table | Unit | Required role |
|---|---|---|
| `works` | work | Publication metadata, work type, source, taxonomy, and lifetime counts |
| `authors` | author | Stable author identity and attributes |
| `work_authors` | work-author | Authorship order, position, institution, and country |
| `work_citations_by_year` | cited work-year | Annual outcomes with explicit coverage and missingness semantics |
| `work_references` | citing work-cited work | Directed citation network used for relatedness and citation reconstruction |
| `subjects` | taxonomy node | Stable OpenAlex domain, field, subfield, and topic identifiers |
| `work_subjects` | work-taxonomy node | Primary and secondary assignments with scores |
| `sources` | publication source | Journal or venue attributes used for controls and fixed effects |
| `institutions` | institution | Institution and country attributes |

Stable OpenAlex IDs are scientific keys. Display-name-derived subject slugs may
be used for physical partitions, but not as the only subject identifier.

Annual citation observations must distinguish a true zero from missing or
out-of-coverage data and record whether the count came from OpenAlex
`counts_by_year` or was reconstructed from citation edges.

### Research Definition Layer

Research choices must be versioned rather than embedded in canonical tables.

`research_samples` records a named sample, its parameters, snapshot version,
code commit, and creation time. `research_sample_works` records inclusion and a
machine-readable exclusion reason for every candidate work.

`relationship_definitions` records rules such as direct citation in either
direction, shared references, co-citation, same topic, shared coauthor, or
network distance. `work_relationships` materializes selected definitions with
focal work, other work, relationship type, strength, and effective year.

`event_definitions` and `research_events` store versioned shocks such as citation
hits, sudden citation increases, publications, retractions, awards, or
institutional moves. A citation hit is therefore one treatment definition, not
a permanent property of an author or paper.

### Exposure Layer

Store annual exposure components before imposing cumulative transformations:

```text
focal_work_id
author_id
year
exposure_definition_id
other_work_citations
related_citations
unrelated_citations
self_citations
number_of_exposure_papers
coverage_status
```

Lagged flows, cumulative stocks, moving averages, logarithms, thresholds, and
decay-weighted measures are derived from these components. Exposure in year
`t` must never use information first observed after `t`.

### Specification Layer

Paper-author-year, author-year, event-time, matched-control, and subject-year
panels are disposable, reproducible products. Each panel build records:

- sample and relationship definition IDs;
- outcome, exposure form, lags, and transformations;
- self-citation and authorship-weighting rules;
- event window and balance requirements;
- intended fixed effects and clustering dimensions;
- source fingerprints, code commit, and build run ID.

This supports linear fixed-effects models, Poisson models, event studies,
hazard models, matching, alternative relatedness rules, and different balanced
or unbalanced samples without changing the canonical warehouse.

## Physical Architecture

The current gzip CSV shards and DuckDB are the working implementation. The
target physical design is partitioned Parquet queried through DuckDB:

```text
warehouse/
  works/subject_id=.../publication_year=.../*.parquet
  work_authors/subject_id=.../*.parquet
  citations_by_year/subject_id=.../citation_year=.../*.parquet
  references/citing_subject_id=.../*.parquet
```

DuckDB serves as query engine, catalog, validation surface, and materialization
engine. A single permanently expanded paper-author-year table is intentionally
not the warehouse: it duplicates facts and commits the project to one exposure
definition.

Every materialized dataset must record `snapshot_version`, `schema_version`,
`build_run_id`, `source_fingerprint`, `code_commit`, `created_at`, and
`validation_status`. Publication is atomic and retains the previous valid
version for rollback.

## Required Validation

Before a dataset is marked complete, validate:

- expected partitions, gzip or Parquet readability, exact schema, and rows;
- unique work IDs and expected work-author and work-year keys;
- logical foreign-key coverage from authorships, citations, and references;
- nonnegative counts and valid publication and citation years;
- source-to-import row reconciliation and numeric cast failures;
- reference-edge counts against available `referenced_works_count` values;
- explicit classification as complete, partial, stale, or invalid.

File existence alone is never a completion criterion.

## Research Execution Plan

### Phase 1: Complete The Economics Fact Layer

Build restartable economics reference edges, validate all economics fact
tables, and import them transactionally. Economics is the prototype because
its annual citations have already been reconstructed from citation edges.

Completion criterion: works, authorships, annual citations, and references are
complete, reconciled, versioned, and queryable for economics.

### Phase 2: Freeze The Economics Research Population

Define eligible publication and observation years, work types, author-history
requirements, citation coverage, team sizes, and truncation rules. Publish a
sample-flow report and retain exclusion reasons.

Completion criterion: a versioned `research_sample_works` table whose population
can be reproduced exactly.

### Phase 3: Build Annual Exposure Components

For every focal paper-author-year, construct annual citations to the focal
paper and to the author's other papers. Separate self, direct-citation-related,
and unrelated exposure. Retain alternative topic, coauthor, bibliographic
coupling, and co-citation definitions for robustness.

Completion criterion: a sharded annual exposure table with temporal leakage,
coverage, and reconciliation checks.

### Phase 4: Descriptive Validation

Report citation coverage by cohort and paper age, related/unrelated shares,
extreme authors and papers, self-citation sensitivity, team-size and author-
position differences, career-age patterns, and exposure concentration.

Completion criterion: an economics construction report demonstrating that the
variables have credible timing, support, and missingness behavior.

### Phase 5: Main Estimates

Estimate the baseline family:

```text
citations_jat = beta * unrelated_exposure_ja,t-1
              + gamma * related_exposure_ja,t-1
              + paper_FE + year_FE + error_jat
```

Then vary annual flows versus cumulative stocks, add paper-age and career-age
controls, transform outcomes and exposures, and use clustering appropriate to
the paper-author structure.

Completion criterion: versioned model inputs and a reproducible baseline table.

### Phase 6: Identification And Robustness

Test leads and lags, field-year and paper-age controls, author-year effects when
identified, removal of self-citations, single-author restrictions, author
position, exposure trimming, placebo authors, leave-one-hit-out measures, and
alternative relationship definitions. Develop an event study around large
citation shocks to an author's paper and outcomes for previously published
unrelated papers.

Completion criterion: evidence separating portfolio spillovers from common
field trends, lifecycle dynamics, author reputation, and latent paper quality.

### Phase 7: Cross-Subject Extension

Only after economics passes construction and identification checks, apply the
same schemas and definitions to pilot subjects and then all fields. Compare
spillovers by collaboration intensity, citation lifecycle, author-name
recognition, and disciplinary structure.

Completion criterion: comparable subject-specific estimates and a pooled model
with explicit subject interactions.

## Current Priority Order

1. Replace the coarse economics reference scan with durable small checkpoints.
2. Validate and safely import economics references.
3. Freeze the economics research sample.
4. Build temporally valid annual related and unrelated exposure components.
5. Run descriptive diagnostics and baseline estimates.
6. Complete identification and robustness work.
7. Optimize a bounded-memory multi-subject reference pass before scaling.
8. Extend calculated annual citations and the validated analysis across fields.

