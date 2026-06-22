#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/projects/Citations}"
SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
DATABASE="${DATABASE:-${SUBJECT_ROOT}/subject_level.duckdb}"
LOG="${LOG:-${SUBJECT_ROOT}/subject_level_duckdb_build.log}"
PYTHON="${PYTHON:-${REPO_DIR}/.venv-duckdb/bin/python}"
THREADS="${THREADS:-4}"
MEMORY_LIMIT="${MEMORY_LIMIT:-12GB}"

cd "$REPO_DIR"
mkdir -p "$(dirname "$LOG")" "$(dirname "$DATABASE")"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing Python executable: $PYTHON" >&2
  echo "Create it with: python3 -m venv .venv-duckdb && .venv-duckdb/bin/python -m pip install duckdb" >&2
  exit 1
fi

{
  echo "subject_duckdb_build_start $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  "$PYTHON" scripts/build_subject_duckdb.py \
    --subject-root "$SUBJECT_ROOT" \
    --database "$DATABASE" \
    --threads "$THREADS" \
    --memory-limit "$MEMORY_LIMIT" \
    "$@"
  echo "subject_duckdb_build_complete $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
} >> "$LOG" 2>&1
