#!/usr/bin/env bash
set -euo pipefail

SUBJECT_SLUG="${1:?usage: run_subject_panel_pipeline.sh <subject_slug> <field_name>}"
FIELD_NAME="${2:?usage: run_subject_panel_pipeline.sh <subject_slug> <field_name>}"

ROOT="/root/sdb1/openalex/derived/${SUBJECT_SLUG}"
WORKS_DIR="${ROOT}/works"
TABLE_DIR="${ROOT}/tables"
PANEL_DIR="${ROOT}/panels"
LOG="${ROOT}/pipeline.log"

mkdir -p "${WORKS_DIR}" "${TABLE_DIR}" "${PANEL_DIR}"

{
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) extracting ${FIELD_NAME} works"
  python3 scripts/extract_subject_from_snapshot.py \
    --field-name "${FIELD_NAME}" \
    --output-dir "${WORKS_DIR}"

  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) building ${FIELD_NAME} normalized tables"
  python3 scripts/build_research_tables.py \
    --input-dir "${WORKS_DIR}" \
    --output-dir "${TABLE_DIR}" \
    --skip-author-stats \
    --skip-hit-events

  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) building ${FIELD_NAME} paper-author-year panel"
  python3 scripts/build_subject_paper_author_year_panel.py \
    --table-dir "${TABLE_DIR}" \
    --output "${PANEL_DIR}/paper_author_year.csv.gz"

  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) done"
} >> "${LOG}" 2>&1
