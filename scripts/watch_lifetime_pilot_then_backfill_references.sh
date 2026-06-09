#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
REPORT="${REPORT:-${REPO_DIR}/reports/subjects/lifetime_pilot_prevalence_regressions.html}"
LOG_DIR="${LOG_DIR:-/root/sdb1/openalex/subjects/reference_backfill_logs}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}"
BACKFILL_WORKERS="${BACKFILL_WORKERS:-8}"

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

echo "watch_start $(date -u +'%Y-%m-%dT%H:%M:%SZ') report=$REPORT" >> "$LOG_DIR/watch.log"

while [[ ! -s "$REPORT" ]]; do
  if ! pgrep -f 'scripts/run_pilot_lifetime_prevalence_regressions.sh|scripts/build_subject_prevalence_regression_data.py|render_prevalence_regressions_stargazer.R' >/dev/null; then
    echo "pilot_not_running_and_report_missing $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/watch.log"
    exit 1
  fi
  sleep "$INTERVAL_SECONDS"
done

echo "pilot_report_ready $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/watch.log"

subject_args=()
for subject in "${SUBJECTS[@]}"; do
  subject_args+=(--subject "$subject")
done

python3 scripts/backfill_subject_work_references.py \
  "${subject_args[@]}" \
  --workers "$BACKFILL_WORKERS" \
  --overwrite \
  > "$LOG_DIR/backfill.log" 2>&1

echo "backfill_complete $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_DIR/watch.log"
