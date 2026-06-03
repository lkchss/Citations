#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
ANALYSIS_DIR="${ANALYSIS_DIR:-/root/sdb1/openalex/subjects/economics_econometrics_and_finance/analysis/hit_effects}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-300}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Add economics hit-effect analysis outputs}"

cd "$REPO_DIR"

required_files=(
  "$ANALYSIS_DIR/economics_hit_effects_report.md"
  "$ANALYSIS_DIR/summary.json"
  "$ANALYSIS_DIR/event_time_summary.csv"
)

while true; do
  complete=1
  for path in "${required_files[@]}"; do
    if [[ ! -s "$path" ]]; then
      complete=0
      break
    fi
  done

  if [[ "$complete" -eq 1 ]]; then
    break
  fi

  if ! pgrep -f "scripts/analyze_economics_hit_effects.py" >/dev/null; then
    echo "analysis process is not running and required outputs are missing" >&2
    exit 1
  fi

  sleep "$CHECK_INTERVAL_SECONDS"
done

python3 scripts/summarize_hit_panel_for_econometrics.py
python3 scripts/publish_economics_analysis_outputs.py

git add reports/economics
if git diff --cached --quiet; then
  echo "no report changes to commit"
  exit 0
fi

git commit -m "$COMMIT_MESSAGE"
git push
