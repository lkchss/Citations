# Recovery After Data Disk Return

This runbook is for the case where the original OpenAlex disk disappears and
later reappears. It keeps recovery focused on read-only checks first, then
resumes only the missing steps.

## 1. Identify and mount the data disk

Check visible block devices:

```bash
lsblk -f
blkid
```

The expected data tree should contain:

```text
/root/sdb1/openalex/
/root/sdb1/projects/Citations/
```

Mount the correct data partition at `/root/sdb1`. Do not mount the 1 MiB
`bios_grub` partition. Verify before running jobs:

```bash
df -h /root/sdb1
ls /root/sdb1/openalex /root/sdb1/projects/Citations
```

## 2. Run the environment checker

From any checkout of this repo:

```bash
python3 scripts/check_openalex_environment.py \
  --repo-dir /root/sdb1/projects/Citations \
  --openalex-root /root/sdb1/openalex
```

Useful JSON form:

```bash
python3 scripts/check_openalex_environment.py --json \
  > /root/sdb1/openalex/recovery_status.json
```

## 3. Confirm the completed subject DuckDB

The subject database previously completed successfully at:

```text
/root/sdb1/openalex/subjects/subject_level.duckdb
```

Expected validated row counts from the completed build:

```text
subject_works: 266,352,099
subject_work_authors: 654,286,310
subject_work_citations_by_year: 413,082,787
subject_work_references: 23,561,066
```

If DuckDB is available:

```bash
.venv-duckdb/bin/python - <<'PY'
import duckdb
con = duckdb.connect('/root/sdb1/openalex/subjects/subject_level.duckdb', read_only=True)
for table in [
    'subject_works',
    'subject_work_authors',
    'subject_work_citations_by_year',
    'subject_work_references',
]:
    print(table, con.execute(f'select count(*) from {table}').fetchone()[0])
PY
```

## 4. Inspect economics reference backfill state

The economics reference backfill was the active task when the disk disappeared.
Check whether final files exist or only temp files remain:

```bash
find /root/sdb1/openalex/subjects/economics_econometrics_and_finance/tables_parts \
  -maxdepth 1 -name '*work_references*' -printf '%s %TY-%Tm-%TdT%TH:%TM %p\n' \
  | sort -n | tail -n 40
```

Final files look like:

```text
part_0000_work_references.csv.gz
```

Incomplete atomic temp files look like:

```text
part_0000_work_references.csv.gz.tmp
```

If only temp files exist, restart the sequential backfill:

```bash
cd /root/sdb1/projects/Citations
setsid -f env BACKFILL_WORKERS=4 ./scripts/run_reference_backfill_sequential.sh \
  >> /root/sdb1/openalex/subjects/reference_backfill_logs/sequential.launch.log 2>&1
```

## 5. Import newly completed references into DuckDB

After economics final `work_references` parts exist, update just that table in
the subject DuckDB:

```bash
cd /root/sdb1/projects/Citations
bash scripts/run_subject_duckdb_build.sh \
  --subject economics_econometrics_and_finance \
  --table work_references \
  --replace-subject
```

Then rerun the environment checker and continue relation-aware prevalence work.
