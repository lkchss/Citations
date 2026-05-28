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
