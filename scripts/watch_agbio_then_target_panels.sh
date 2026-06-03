#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
CURRENT_PID="${CURRENT_PID:-7933}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-300}"
LOG="${LOG:-/root/sdb1/openalex/subjects/target_biology_physics_panels.log}"

AGBIO_PANEL="$SUBJECT_ROOT/agricultural_and_biological_sciences/panels/paper_author_year.csv.gz"
AGBIO_SUMMARY="$SUBJECT_ROOT/agricultural_and_biological_sciences/panels/paper_author_year.csv.gz.summary.json"
AGBIO_TMP="$SUBJECT_ROOT/agricultural_and_biological_sciences/panels/paper_author_year.csv.gz.tmp"

cd "$REPO_DIR"

echo "watcher started at $(date -Is)" >> "$LOG"
while true; do
  if [[ -s "$AGBIO_PANEL" && -s "$AGBIO_SUMMARY" && ! -e "$AGBIO_TMP" ]]; then
    echo "agricultural biology panel complete at $(date -Is)" >> "$LOG"
    break
  fi
  if ! ps -p "$CURRENT_PID" >/dev/null 2>&1; then
    echo "current panel builder pid=$CURRENT_PID is not running before agricultural biology completed" >> "$LOG"
    exit 1
  fi
  sleep "$CHECK_INTERVAL_SECONDS"
done

if ps -p "$CURRENT_PID" >/dev/null 2>&1; then
  echo "stopping broad panel builder pid=$CURRENT_PID at $(date -Is)" >> "$LOG"
  kill -TERM "$CURRENT_PID" || true
  for _ in {1..24}; do
    if ! ps -p "$CURRENT_PID" >/dev/null 2>&1; then
      break
    fi
    sleep 5
  done
fi

echo "starting targeted biology/physics panels at $(date -Is)" >> "$LOG"
python3 scripts/build_subject_panels_from_table_parts.py \
  --input-root "$SUBJECT_ROOT" \
  --subject biochemistry_genetics_and_molecular_biology \
  --subject physics_and_astronomy \
  --skip-existing >> "$LOG" 2>&1
echo "targeted biology/physics panels complete at $(date -Is)" >> "$LOG"
