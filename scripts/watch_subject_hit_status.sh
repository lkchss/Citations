#!/usr/bin/env bash
set -euo pipefail

LOG_ROOT="${LOG_ROOT:-/root/sdb1/openalex/subjects/hit_effects_counts_by_year_logs}"
SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-1800}"
STATUS_LOG="${STATUS_LOG:-$LOG_ROOT/status_watch.log}"

subjects=(
  "agricultural_and_biological_sciences"
  "biochemistry_genetics_and_molecular_biology"
  "physics_and_astronomy"
)

mkdir -p "$LOG_ROOT"

while true; do
  {
    echo "===== $(date -u '+%Y-%m-%dT%H:%M:%SZ') ====="
    pgrep -af 'run_subject_hit_analyses_then_publish|analyze_subject_hit_effects_streaming|publish_subject_hit_comparison|git push' || true
    free -h
    for subject in "${subjects[@]}"; do
      echo "--- subject=$subject ---"
      output_dir="$SUBJECT_ROOT/$subject/analysis/hit_effects_counts_by_year"
      if [[ -s "$output_dir/summary.json" && -s "$output_dir/event_time_summary.csv" ]]; then
        echo "status=outputs_ready"
        stat -c 'summary=%s bytes mtime=%y' "$output_dir/summary.json"
        stat -c 'event_time_summary=%s bytes mtime=%y' "$output_dir/event_time_summary.csv"
      else
        echo "status=incomplete"
      fi
      if [[ -s "$LOG_ROOT/$subject.log" ]]; then
        tail -n 5 "$LOG_ROOT/$subject.log"
      else
        echo "log=missing"
      fi
    done
    echo
  } >> "$STATUS_LOG" 2>&1
  sleep "$INTERVAL_SECONDS"
done
