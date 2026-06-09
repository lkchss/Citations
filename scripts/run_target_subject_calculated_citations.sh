#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
SNAPSHOT_WORKS_DIR="${SNAPSHOT_WORKS_DIR:-/root/sdb1/openalex/snapshot/data/works}"
WORKERS="${WORKERS:-8}"
FILES_PER_PART="${FILES_PER_PART:-1}"

SUBJECTS=(
  "agricultural_and_biological_sciences"
  "biochemistry_genetics_and_molecular_biology"
  "physics_and_astronomy"
)

cd "$REPO_DIR"

for subject in "${SUBJECTS[@]}"; do
  subject_dir="${SUBJECT_ROOT}/${subject}"
  output_dir="${subject_dir}/calculated_citations"
  log_dir="${subject_dir}/calculated_citations_logs"
  mkdir -p "$output_dir" "$log_dir"

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] starting calculated citations for ${subject}" | tee -a "$log_dir/run.log"
  python3 scripts/build_calculated_citations_by_year.py \
    --snapshot-works-dir "$SNAPSHOT_WORKS_DIR" \
    --subject-dir "$subject_dir" \
    --output-dir "$output_dir" \
    --output "${output_dir}/calculated_citations_by_year.csv.gz" \
    --work-ids-cache "${output_dir}/target_work_ids.txt.gz" \
    --workers "$WORKERS" \
    --files-per-part "$FILES_PER_PART" \
    >> "$log_dir/run.log" 2>&1
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] finished calculated citations for ${subject}" | tee -a "$log_dir/run.log"
done
