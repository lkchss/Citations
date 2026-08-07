# Ingestion-ready exploratory results

This directory is generated entirely from small, committed CSV outputs and does
not require the external SSD. `headline_results.csv` contains one row per key
result; the two `*_tidy.csv` files contain long-form event-time data;
`results.jsonl` combines them for direct ingestion. SVG files are portable
figures. `data_dictionary.json` documents table grain and keys, while
`manifest.json` records definitions, warnings, hashes, and provenance.

All estimates are descriptive. Do not label the pre/post difference as a causal
effect. The current hit definition uses an economics-only portfolio denominator,
not an author's complete OpenAlex career citation total.
