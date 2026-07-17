# Citations

The canonical subject-level warehouse structure and research execution plan are
described in [docs/research_warehouse_design.md](docs/research_warehouse_design.md).

Tools for collecting OpenAlex citation metadata related to economics.

## Project Context

Agents and other models should start with [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md).
It records the current research goal, data layout, running jobs, completed
outputs, and operating rules for what should be committed to GitHub.

## Tests

Run the lightweight recovery and pipeline safety tests with:

```bash
python3 -m unittest discover -v
```

## Pull Economics Works

Set your OpenAlex API key locally:

```bash
cp .env.example .env
# edit .env and set OPENALEX_API_KEY
```

Then run:

```bash
python3 scripts/pull_openalex_economics.py
```

By default, data is written outside the Git repo to:

```text
/root/sdb1/openalex/economics_field20
```

The script writes gzip-compressed JSONL batch files and a `checkpoint.json`, so it can resume after stopping.

The default OpenAlex filter is:

```text
primary_topic.field.id:20
```

OpenAlex field `20` is `Economics, Econometrics and Finance`. This is broader than a narrow keyword search but avoids pulling papers where economics appears only as a weak or zero-score ancestor concept.

## Download The OpenAlex Snapshot

For full OpenAlex ingestion, use the public S3 snapshot instead of the API:

```bash
python3 scripts/download_openalex_snapshot.py --entity works --workers 8 --largest-first
```

Default output:

```text
/root/sdb1/openalex/snapshot
```

The downloader reads the official OpenAlex manifest, downloads gzip JSONL files concurrently, and skips files that already exist with the expected byte size. The API puller is useful for filtered experiments and incremental/API-only fields; the snapshot is the right path for full-corpus storage.

For parallel API shards, build a reusable skip-ID cache from already pulled files:

```bash
python3 scripts/build_openalex_id_cache.py \
  --input-dir /root/sdb1/openalex/economics_field20 \
  --input-dir /root/sdb1/openalex/economics_field20_shards/to_2009 \
  --input-dir /root/sdb1/openalex/economics_field20_shards/from_2010 \
  --output-file /root/sdb1/openalex/economics_existing_ids.txt
```

Then start balanced economics year shards:

```bash
./scripts/start_economics_shards.sh
```

Build normalized research tables from extracted economics works:

```bash
python3 scripts/build_research_tables.py \
  --input-dir /root/sdb1/openalex/derived/economics/works \
  --output-dir /root/sdb1/openalex/derived/economics/tables \
  --include-references
```

Build the subject-level paper-author-year panel from those tables:

```bash
python3 scripts/build_subject_paper_author_year_panel.py \
  --table-dir /root/sdb1/openalex/derived/economics/tables \
  --output /root/sdb1/openalex/derived/economics/panels/paper_author_year.csv.gz
```

Build the hit-event analysis panel from those tables:

```bash
python3 scripts/build_panel_from_tables.py \
  --table-dir /root/sdb1/openalex/derived/economics/tables \
  --output /root/sdb1/openalex/derived/panels/paper_author_hit_year_panel.csv.gz
```

## Build A First Event Panel

The first econometrics dataset is a balanced paper-author-year panel around author hit papers:

```bash
python3 scripts/build_author_paper_year_panel.py
```

Default output:

```text
/root/sdb1/openalex/econometrics_panels/author_paper_year_event_panel.csv.gz
```

The first simple hit definition is any included article, preprint, or review with at least 500 total OpenAlex citations and publication year 1990 or later. A focal paper is included for an author-hit event only when it was published before the hit and the hit paper does not cite it. The panel is balanced over event years `-5` through `+5` around the hit publication year, with annual citations from OpenAlex `counts_by_year`.

To tighten hits to papers that account for at least half of the author's included-work citations:

```bash
python3 scripts/build_author_paper_year_panel.py --min-hit-author-citation-share 0.5 --min-author-included-works 3 --min-unrelated-focal-works 3
```

To inspect the hit candidates before building a panel:

```bash
python3 scripts/list_hit_candidates.py --min-hit-author-citation-share 0.5 --min-author-included-works 3 --min-unrelated-focal-works 3
```

Useful options:

```bash
python3 scripts/build_author_paper_year_panel.py --max-files 100
python3 scripts/build_author_paper_year_panel.py --min-hit-citations 1000 --pre-years 10 --post-years 10
```
