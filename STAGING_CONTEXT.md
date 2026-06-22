# Staging Context

Last updated: 2026-06-22 UTC.

The original OpenAlex data disk is currently not visible to the OS. The prior
data root was:

```text
/root/sdb1/openalex/
```

The completed subject-level DuckDB database previously existed at:

```text
/root/sdb1/openalex/subjects/subject_level.duckdb
```

The current connected large disk is mounted at:

```text
/mnt/openalex_staging
```

In the sandbox view it may appear read-only, but escalated host commands can
write there. Use it for large temporary outputs under:

```text
/mnt/openalex_staging/work/
```

Editable repo while the original data disk is offline:

```text
/root/projects/Citations
```

The DuckDB subject database tooling has been restored here:

```text
scripts/build_subject_duckdb.py
scripts/run_subject_duckdb_build.sh
scripts/check_openalex_environment.py
```

Recovery instructions are in:

```text
docs/recovery_after_data_disk_return.md
```

When the original OpenAlex disk returns, copy or commit code changes from this
repo back to the canonical project and resume work against:

```text
/root/sdb1/projects/Citations
/root/sdb1/openalex/
```
