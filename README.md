# Citations

Tools for collecting OpenAlex citation metadata related to economics.

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

Useful options:

```bash
python3 scripts/build_author_paper_year_panel.py --max-files 100
python3 scripts/build_author_paper_year_panel.py --min-hit-citations 1000 --pre-years 10 --post-years 10
```
