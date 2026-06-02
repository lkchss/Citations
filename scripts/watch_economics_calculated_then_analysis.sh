#!/usr/bin/env bash
set -euo pipefail

PROJECT="/root/sdb1/projects/Citations"
SUBJECT="economics_econometrics_and_finance"
SUBJECT_ROOT="/root/sdb1/openalex/subjects"
SUBJECT_DIR="${SUBJECT_ROOT}/${SUBJECT}"
CALCULATED="${SUBJECT_DIR}/calculated_citations/calculated_citations_by_year.csv.gz"
CALCULATED_SUMMARY="${CALCULATED}.summary.json"
PANEL="${SUBJECT_DIR}/panels/paper_author_year.csv.gz"
PANEL_SUMMARY="${PANEL}.summary.json"
ANALYSIS_DIR="${SUBJECT_DIR}/analysis/hit_effects"
LOG="${SUBJECT_DIR}/analysis/economics_calculated_pipeline.log"
INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-300}"

mkdir -p "$(dirname "${LOG}")" "${SUBJECT_DIR}/panels"
cd "${PROJECT}"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "${LOG}"
}

log "waiting for calculated citations summary ${CALCULATED_SUMMARY}"
while [ ! -s "${CALCULATED_SUMMARY}" ]; do
  sleep "${INTERVAL_SECONDS}"
done

if [ ! -s "${PANEL_SUMMARY}" ]; then
  log "building economics paper-author-year panel"
  python3 scripts/build_subject_panels_from_table_parts.py \
    --input-root "${SUBJECT_ROOT}" \
    --subject "${SUBJECT}" \
    --calculated-citations "${CALCULATED}" >> "${LOG}" 2>&1
else
  log "paper-author-year panel already exists"
fi

log "running economics hit-effect analysis"
python3 scripts/analyze_economics_hit_effects.py \
  --pre-years 10 \
  --post-years 10 \
  --output-dir "${ANALYSIS_DIR}" >> "${LOG}" 2>&1

log "publishing economics analysis outputs into repo"
python3 scripts/publish_economics_analysis_outputs.py >> "${LOG}" 2>&1

if ! git diff --quiet -- reports/economics; then
  git add reports/economics
  git commit -m "Add economics calculated citation analysis outputs" >> "${LOG}" 2>&1
  git push >> "${LOG}" 2>&1
  log "published economics analysis outputs to GitHub"
else
  log "no report changes to publish"
fi
