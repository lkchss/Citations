#!/usr/bin/env bash
set -euo pipefail

PROJECT="/root/sdb1/projects/Citations"
SNAPSHOT_DIR="/root/sdb1/openalex/snapshot"
LOG="/root/sdb1/openalex/watch_snapshot_then_process.log"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-1800}"
INITIAL_SLEEP_SECONDS="${INITIAL_SLEEP_SECONDS:-36000}"

cd "$PROJECT"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"
}

snapshot_complete() {
  python3 - "$SNAPSHOT_DIR" <<'PY'
import json
import sys
from pathlib import Path

snapshot_dir = Path(sys.argv[1])
manifest_path = snapshot_dir / "download_manifest.json"
if not manifest_path.exists():
    print("missing_manifest")
    raise SystemExit(1)

entries = json.loads(manifest_path.read_text(encoding="utf-8"))
missing = 0
incomplete = 0
for entry in entries:
    rel = entry["relative_path"]
    expected = int(entry.get("size") or 0)
    path = snapshot_dir / rel
    if not path.exists():
        missing += 1
        continue
    if expected and path.stat().st_size != expected:
        incomplete += 1

print(f"files={len(entries)} missing={missing} incomplete={incomplete}")
raise SystemExit(0 if missing == 0 and incomplete == 0 else 1)
PY
}

run_processing() {
  log "snapshot complete; starting inventory"
  python3 scripts/snapshot_inventory.py >> "$LOG" 2>&1

  log "extracting economics works from snapshot"
  python3 scripts/extract_economics_from_snapshot.py >> "$LOG" 2>&1

  log "building normalized economics research tables"
  python3 scripts/build_research_tables.py \
    --input-dir /root/sdb1/openalex/derived/economics/works \
    --output-dir /root/sdb1/openalex/derived/economics/tables \
    --include-references >> "$LOG" 2>&1

  log "building paper-author-hit-year panel"
  python3 scripts/build_panel_from_tables.py \
    --table-dir /root/sdb1/openalex/derived/economics/tables \
    --output /root/sdb1/openalex/derived/panels/paper_author_hit_year_panel.csv.gz >> "$LOG" 2>&1

  log "processing complete"
}

log "watchdog started; initial_sleep_seconds=$INITIAL_SLEEP_SECONDS check_interval_seconds=$CHECK_INTERVAL_SECONDS"
sleep "$INITIAL_SLEEP_SECONDS"

while true; do
  status="$(snapshot_complete 2>&1)" && {
    log "snapshot status: $status"
    run_processing
    exit 0
  }
  log "snapshot incomplete: $status"
  sleep "$CHECK_INTERVAL_SECONDS"
done
