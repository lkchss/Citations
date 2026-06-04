#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
LOG_ROOT="${LOG_ROOT:-/root/sdb1/openalex/subjects/hit_effects_counts_by_year_logs}"
SUBJECT="${SUBJECT:-agricultural_and_biological_sciences}"
CURRENT_RUNNER_PID="${CURRENT_RUNNER_PID:-}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-60}"

analysis_dir="$SUBJECT_ROOT/$SUBJECT/analysis/hit_effects_counts_by_year"
mkdir -p "$LOG_ROOT"

echo "watching first subject=$SUBJECT at $(date -Is)" >> "$LOG_ROOT/first_subject_publish_then_resume.log"
while [[ ! -s "$analysis_dir/summary.json" || ! -s "$analysis_dir/event_time_summary.csv" ]]; do
  sleep "$CHECK_INTERVAL_SECONDS"
done

echo "first subject outputs detected subject=$SUBJECT at $(date -Is)" >> "$LOG_ROOT/first_subject_publish_then_resume.log"

if [[ -n "$CURRENT_RUNNER_PID" ]]; then
  kill -TERM "$CURRENT_RUNNER_PID" 2>/dev/null || true
fi

pkill -TERM -f "analyze_subject_hit_effects_streaming.py --subject-dir $SUBJECT_ROOT/biochemistry_genetics_and_molecular_biology" 2>/dev/null || true
pkill -TERM -f "analyze_subject_hit_effects_streaming.py --subject-dir $SUBJECT_ROOT/physics_and_astronomy" 2>/dev/null || true

cd "$REPO_DIR"
python3 scripts/publish_subject_hit_comparison.py --only-subject "$SUBJECT"
git add reports/subjects scripts/watch_first_subject_publish_then_resume.sh
if git diff --cached --quiet; then
  echo "no first-subject report changes to commit at $(date -Is)" >> "$LOG_ROOT/first_subject_publish_then_resume.log"
else
  git commit -m "Publish ${SUBJECT} hit-effect baseline"
  git push
fi

setsid -f env REFERENCE_WORKERS="${REFERENCE_WORKERS:-12}" PRE_YEARS="${PRE_YEARS:-10}" POST_YEARS="${POST_YEARS:-10}" \
  ./scripts/run_subject_hit_analyses_then_publish.sh \
  >> "$LOG_ROOT/hit_effects_counts_by_year_pipeline.resumed.log" 2>&1

echo "resumed updated subject pipeline at $(date -Is)" >> "$LOG_ROOT/first_subject_publish_then_resume.log"
