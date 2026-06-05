#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
DATA_ROOT="${DATA_ROOT:-/root/sdb1/openalex/subjects/prevalence_regressions}"
LOG_DIR="${LOG_DIR:-/root/sdb1/openalex/subjects/prevalence_regressions_logs}"
MAX_AUTHORS="${MAX_AUTHORS:-5000}"
SAMPLE_MOD="${SAMPLE_MOD:-2000}"
SAMPLE_KEEP="${SAMPLE_KEEP:-1}"
MIN_AUTHOR_PAPERS="${MIN_AUTHOR_PAPERS:-2}"
MAX_SNAPSHOT_FILES="${MAX_SNAPSHOT_FILES:-0}"
REFERENCE_WORKERS="${REFERENCE_WORKERS:-12}"

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

python3 scripts/build_subject_prevalence_regression_data.py \
  --output-root "$DATA_ROOT" \
  --max-authors "$MAX_AUTHORS" \
  --sample-mod "$SAMPLE_MOD" \
  --sample-keep "$SAMPLE_KEEP" \
  --min-author-papers "$MIN_AUTHOR_PAPERS" \
  --max-snapshot-files "$MAX_SNAPSHOT_FILES" \
  --reference-workers "$REFERENCE_WORKERS" \
  > "$LOG_DIR/build.log" 2>&1

Rscript scripts/render_prevalence_regressions_stargazer.R \
  "$DATA_ROOT" \
  "$REPO_DIR" \
  "$REPO_DIR/reports/subjects/prevalence_regression_stargazer_tables.html" \
  > "$LOG_DIR/render.log" 2>&1

git add \
  scripts/build_subject_prevalence_regression_data.py \
  scripts/render_prevalence_regressions_stargazer.R \
  scripts/run_prevalence_regressions_then_publish.sh \
  reports/subjects/prevalence_regression_stargazer_tables.html

if ! git diff --cached --quiet; then
  git commit -m "Add subject prevalence fixed effect regressions"
  git push
fi
