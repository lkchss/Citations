#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
LOG_DIR="${LOG_DIR:-/root/sdb1/openalex/subjects/reference_backfill_logs}"
BACKFILL_WORKERS="${BACKFILL_WORKERS:-4}"

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
  python3 scripts/backfill_subject_work_references.py \
    --subject "$subject" \
    --workers "$BACKFILL_WORKERS" \
    --overwrite \
    > "$LOG_DIR/${subject}.backfill.log" 2>&1
  echo "subject_complete $subject $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/sequential.log"
done

echo "sequential_backfill_complete $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/sequential.log"
