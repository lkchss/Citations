#!/usr/bin/env bash
set -euo pipefail

PROJECT="/root/sdb1/projects/Citations"
TABLE_DIR="/root/sdb1/openalex/derived/economics/tables"
OUTPUT="/root/sdb1/openalex/derived/economics/panels/paper_author_year.csv.gz"
LOG="/root/sdb1/openalex/watch_tables_then_subject_panel.log"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-600}"

cd "$PROJECT"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"
}

log "waiting for normalized economics tables in $TABLE_DIR"
while true; do
  if [[ -s "$TABLE_DIR/works.csv.gz" && -s "$TABLE_DIR/work_authors.csv.gz" && -s "$TABLE_DIR/work_citations_by_year.csv.gz" ]]; then
    log "tables found; building subject paper-author-year panel"
    python3 scripts/build_subject_paper_author_year_panel.py \
      --table-dir "$TABLE_DIR" \
      --output "$OUTPUT" >> "$LOG" 2>&1
    log "subject paper-author-year panel complete: $OUTPUT"
    exit 0
  fi
  sleep "$CHECK_INTERVAL_SECONDS"
done
