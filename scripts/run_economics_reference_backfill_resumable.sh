#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/projects/Citations}"
SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
SNAPSHOT_WORKS_DIR="${SNAPSHOT_WORKS_DIR:-/root/sdb1/openalex/snapshot/data/works}"
BACKFILL_WORKERS="${BACKFILL_WORKERS:-8}"
FILES_PER_CHUNK="${FILES_PER_CHUNK:-8}"
MAX_FILES="${MAX_FILES:-0}"
RESET="${RESET:-0}"
LOG_DIR="${LOG_DIR:-${SUBJECT_ROOT}/reference_backfill_logs}"

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

args=(
  --subject economics_econometrics_and_finance
  --subject-root "$SUBJECT_ROOT"
  --snapshot-works-dir "$SNAPSHOT_WORKS_DIR"
  --workers "$BACKFILL_WORKERS"
  --files-per-chunk "$FILES_PER_CHUNK"
  --max-files "$MAX_FILES"
)
if [[ "$RESET" == "1" ]]; then
  args+=(--reset)
fi

exec python3 scripts/backfill_subject_work_references_resumable.py "${args[@]}" \
  >> "$LOG_DIR/economics_reference_backfill_resumable.log" 2>&1
