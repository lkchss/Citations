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
/root/sdb1/openalex/economics
```

The script writes gzip-compressed JSONL batch files and a `checkpoint.json`, so it can resume after stopping.
