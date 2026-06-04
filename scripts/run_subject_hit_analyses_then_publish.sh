#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
LOG_ROOT="${LOG_ROOT:-/root/sdb1/openalex/subjects/hit_effects_counts_by_year_logs}"
REFERENCE_WORKERS="${REFERENCE_WORKERS:-12}"
PRE_YEARS="${PRE_YEARS:-10}"
POST_YEARS="${POST_YEARS:-10}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Compare subject hit-effect baselines}"

subjects=(
  "agricultural_and_biological_sciences"
  "biochemistry_genetics_and_molecular_biology"
  "physics_and_astronomy"
)

mkdir -p "$LOG_ROOT"
cd "$REPO_DIR"

commit_if_changed() {
  local message="$1"
  git add reports/subjects scripts/publish_subject_hit_comparison.py scripts/run_subject_hit_analyses_then_publish.sh
  if git diff --cached --quiet; then
    echo "no report changes to commit for message=$message" | tee -a "$LOG_ROOT/pipeline.log"
    return
  fi
  git commit -m "$message"
  git push
}

for subject in "${subjects[@]}"; do
  output_dir="$SUBJECT_ROOT/$subject/analysis/hit_effects_counts_by_year"
  mkdir -p "$output_dir"
  if [[ -s "$output_dir/summary.json" && -s "$output_dir/event_time_summary.csv" ]]; then
    echo "skipping existing subject=$subject" | tee -a "$LOG_ROOT/pipeline.log"
    python3 scripts/publish_subject_hit_comparison.py --only-subject "$subject"
    commit_if_changed "Publish ${subject} hit-effect baseline"
    continue
  fi
  echo "starting subject=$subject at $(date -Is)" | tee -a "$LOG_ROOT/pipeline.log"
  python3 scripts/analyze_subject_hit_effects_streaming.py \
    --subject-dir "$SUBJECT_ROOT/$subject" \
    --output-dir "$output_dir" \
    --pre-years "$PRE_YEARS" \
    --post-years "$POST_YEARS" \
    --reference-workers "$REFERENCE_WORKERS" \
    >> "$LOG_ROOT/$subject.log" 2>&1
  echo "finished subject=$subject at $(date -Is)" | tee -a "$LOG_ROOT/pipeline.log"
  python3 scripts/publish_subject_hit_comparison.py --only-subject "$subject"
  commit_if_changed "Publish ${subject} hit-effect baseline"
done

python3 scripts/publish_subject_hit_comparison.py
commit_if_changed "$COMMIT_MESSAGE"
