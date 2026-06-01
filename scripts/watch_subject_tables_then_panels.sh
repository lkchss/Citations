#!/usr/bin/env bash
set -euo pipefail

SUBJECT_ROOT="${SUBJECT_ROOT:-/root/sdb1/openalex/subjects}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-1800}"
LOG="${SUBJECT_ROOT}/watch_subject_tables_then_panels.log"
SUMMARY="${SUBJECT_ROOT}/build_subject_tables_summary.json"

mkdir -p "${SUBJECT_ROOT}"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) waiting for ${SUMMARY}" >> "${LOG}"
while [[ ! -s "${SUMMARY}" ]]; do
  sleep "${CHECK_INTERVAL_SECONDS}"
done

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) subject tables complete; building paper-author-year panels" >> "${LOG}"
python3 scripts/build_subject_panels_from_table_parts.py \
  --input-root "${SUBJECT_ROOT}" >> "${LOG}" 2>&1

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) all subject panels complete" >> "${LOG}"
