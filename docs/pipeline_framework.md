# OpenAlex Pipeline Framework

The project has two tracks:

1. Bulk OpenAlex ingestion from the public snapshot.
2. Research datasets for citation spillovers, starting with economics.

The snapshot is the source of truth for full-corpus work. API pulls are useful for fast filtered experiments, but they are credit- and request-latency-limited.

## Storage Layout

```text
/root/sdb1/openalex/
  snapshot/
    data/works/...
    download_manifest.json
    download_works.log
  derived/
    economics/
    panels/
    indexes/
```

## Phases

### Phase 1: Download Snapshot

Download works first:

```bash
python3 scripts/download_openalex_snapshot.py --entity works --workers 8 --largest-first
```

Then download support entities:

```bash
python3 scripts/download_openalex_snapshot.py --entity authors --entity sources --entity institutions --entity topics --entity fields --entity subfields --entity domains --entity publishers --entity funders --workers 8 --largest-first
```

### Phase 2: Inventory Snapshot

Create a manifest-level and local-file inventory:

```bash
python3 scripts/snapshot_inventory.py
```

### Phase 3: Extract Economics

Filter snapshot works locally:

```bash
python3 scripts/extract_economics_from_snapshot.py
```

Default filter:

```text
primary_topic.field.id == https://openalex.org/fields/20
```

### Phase 4: Build Analysis Tables

Build normalized research tables from extracted economics works:

```bash
python3 scripts/build_research_tables.py \
  --input-dir /root/sdb1/openalex/derived/economics/works \
  --output-dir /root/sdb1/openalex/derived/economics/tables \
  --include-references
```

The table builder creates:

```text
works.csv.gz
work_authors.csv.gz
work_citations_by_year.csv.gz
work_references.csv.gz
author_work_stats.csv.gz
hit_events.csv.gz
build_summary.json
```

Then build the event panel from those tables:

```bash
python3 scripts/build_panel_from_tables.py \
  --table-dir /root/sdb1/openalex/derived/economics/tables \
  --output /root/sdb1/openalex/derived/panels/paper_author_hit_year_panel.csv.gz
```

The older direct panel builder still works from OpenAlex JSONL gzip work files and can be pointed at the extracted economics directory:

```bash
python3 scripts/build_author_paper_year_panel.py --input-dir /root/sdb1/openalex/derived/economics/works
```

## Target Tables

First normalized layer:

| Table | Unit | Purpose |
|---|---|---|
| `works` | work | metadata, publication date, type, field/topic, citation totals |
| `work_authors` | work-author | authorship links and author position |
| `work_references` | citing work-cited work | unrelated-paper exclusions |
| `work_citations_by_year` | work-year | annual citation outcomes |
| `author_work_stats` | author | total works and citations within selected corpus |
| `hit_events` | author-hit work | treatment event definitions |
| `paper_author_year_panel` | paper-author-hit-year | event-study panel |

## Monitoring

Use:

```bash
python3 scripts/monitor_downloads.py
```

This reports snapshot bytes, completed files, current measured throughput, and API-shard status when present.
