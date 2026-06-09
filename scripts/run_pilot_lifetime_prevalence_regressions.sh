#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
DATA_ROOT="${DATA_ROOT:-/root/sdb1/openalex/subjects/prevalence_regressions_lifetime_pilot}"
LOG_DIR="${LOG_DIR:-/root/sdb1/openalex/subjects/prevalence_regressions_lifetime_pilot_logs}"
REPORT="${REPORT:-${REPO_DIR}/reports/subjects/lifetime_pilot_prevalence_regressions.html}"

# Sampling design:
# - SAMPLE_MOD/SAMPLE_KEEP hashes authors, then keeps every retained author's
#   complete subject-paper history for exposure stocks.
# - FOCAL_SAMPLE_MOD/FOCAL_SAMPLE_KEEP hashes papers within that history and
#   writes full 1900-2026 lifetimes only for retained focal papers.
SAMPLE_MOD="${SAMPLE_MOD:-1000}"
SAMPLE_KEEP="${SAMPLE_KEEP:-1}"
FOCAL_SAMPLE_MOD="${FOCAL_SAMPLE_MOD:-4}"
FOCAL_SAMPLE_KEEP="${FOCAL_SAMPLE_KEEP:-1}"
MIN_AUTHOR_PAPERS="${MIN_AUTHOR_PAPERS:-2}"
REFERENCE_WORKERS="${REFERENCE_WORKERS:-12}"
REFERENCE_BACKEND="${REFERENCE_BACKEND:-thread}"
MAX_SNAPSHOT_FILES="${MAX_SNAPSHOT_FILES:-0}"
SHARED_REFERENCE_SCAN="${SHARED_REFERENCE_SCAN:-1}"
SKIP_REFERENCE_SCAN="${SKIP_REFERENCE_SCAN:-0}"

SUBJECTS=(
  "economics_econometrics_and_finance"
  "social_sciences"
  "psychology"
  "arts_and_humanities"
  "agricultural_and_biological_sciences"
  "medicine"
  "physics_and_astronomy"
  "computer_science"
  "environmental_science"
  "mathematics"
)

mkdir -p "$DATA_ROOT" "$LOG_DIR" "$(dirname "$REPORT")"
cd "$REPO_DIR"

subject_args=()
for subject in "${SUBJECTS[@]}"; do
  subject_args+=(--subject "$subject")
done
shared_reference_args=()
if [[ "$SKIP_REFERENCE_SCAN" == "1" ]]; then
  shared_reference_args+=(--skip-reference-scan)
elif [[ "$SHARED_REFERENCE_SCAN" == "1" ]]; then
  shared_reference_args+=(--shared-reference-scan)
fi

python3 scripts/build_subject_prevalence_regression_data.py \
  "${subject_args[@]}" \
  --output-root "$DATA_ROOT" \
  --sample-mod "$SAMPLE_MOD" \
  --sample-keep "$SAMPLE_KEEP" \
  --max-authors 0 \
  --min-author-papers "$MIN_AUTHOR_PAPERS" \
  --focal-sample-mod "$FOCAL_SAMPLE_MOD" \
  --focal-sample-keep "$FOCAL_SAMPLE_KEEP" \
  --reference-workers "$REFERENCE_WORKERS" \
  --reference-backend "$REFERENCE_BACKEND" \
  --max-snapshot-files "$MAX_SNAPSHOT_FILES" \
  "${shared_reference_args[@]}" \
  > "$LOG_DIR/build.log" 2>&1

Rscript scripts/render_prevalence_regressions_stargazer.R \
  "$DATA_ROOT" \
  "$REPO_DIR" \
  "$REPORT" \
  > "$LOG_DIR/render.log" 2>&1
