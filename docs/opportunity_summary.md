# Technical Opportunity Summary

This project develops a reusable research data infrastructure for large-scale
scholarly communication research. The system ingests OpenAlex's structured
scholarly metadata and citation snapshot, rather than scraping web pages or
search-engine results.

The current data pipeline uses Python for streaming extraction, normalization,
validation, and checkpointed processing of compressed JSONL records. The raw
OpenAlex works snapshot is partitioned into subject-level tables containing:

- paper metadata;
- paper-author and author-position relationships;
- annual citation outcomes; and
- directed paper-to-paper reference edges.

The normalized tables are stored as bounded compressed shards and imported into
DuckDB for typed, local analytical queries. DuckDB is used as the analytical
database and query engine; it is not a web-search or scraping tool. The design
preserves source facts separately from research definitions, such as samples,
relatedness rules, event definitions, and self-citation policies.

This separation allows researchers to generate many econometric datasets from
the same validated source layer. Alternative exposure measures, lags,
cumulative citation stocks, paper or author fixed effects, event-study windows,
subject restrictions, and robustness definitions can be changed without
re-downloading or repeatedly rescanning the raw snapshot.

The current warehouse covers 27 subjects and contains approximately 266 million
works, 654 million work-author links, and 413 million work-year citation rows.
The economics subject contains approximately 7.9 million works. Its reference
network is being completed through a resumable Python backfill that scans the
OpenAlex snapshot in deterministic chunks, publishes atomic compressed outputs,
records checksums and manifests, and resumes after interruption.

The next technical milestones are to complete and validate the economics
reference layer, import it transactionally into DuckDB, construct annual
related and unrelated exposure components, and then generate specification-
specific panels for the research analyses. Once validated in economics, the
same pipeline can be extended across subjects and used for comparable
cross-disciplinary estimates.

The project therefore offers a durable, extensible alternative to ad hoc
web-scraping workflows: a reproducible snapshot-to-database pipeline with
explicit provenance, bounded-memory processing, restartable computation, and
flexible downstream econometric design.

