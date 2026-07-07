#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
LOG_DIR="${LOG_DIR:-/root/sdb1/openalex/subjects/reference_backfill_logs}"
BACKFILL_WORKERS="${BACKFILL_WORKERS:-4}"
BACKFILL_OVERWRITE="${BACKFILL_OVERWRITE:-0}"
BACKFILL_CLEAN_TEMP="${BACKFILL_CLEAN_TEMP:-1}"
BACKFILL_SKIP_EXISTING_SUBJECTS="${BACKFILL_SKIP_EXISTING_SUBJECTS:-0}"

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

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

echo "sequential_backfill_start $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/sequential.log"

for subject in "${SUBJECTS[@]}"; do
  echo "subject_start $subject $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/sequential.log"
  args=(
    --subject "$subject"
    --workers "$BACKFILL_WORKERS"
  )
  if [[ "$BACKFILL_OVERWRITE" == "1" ]]; then
    args+=(--overwrite)
  fi
  if [[ "$BACKFILL_CLEAN_TEMP" == "1" ]]; then
    args+=(--clean-temp)
  fi
  if [[ "$BACKFILL_SKIP_EXISTING_SUBJECTS" == "1" ]]; then
    args+=(--skip-existing-subjects)
  fi
  python3 scripts/backfill_subject_work_references.py \
    "${args[@]}" \
    > "$LOG_DIR/${subject}.backfill.log" 2>&1
  echo "subject_complete $subject $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/sequential.log"
done

echo "sequential_backfill_complete $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/sequential.log"
