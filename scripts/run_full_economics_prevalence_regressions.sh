#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/sdb1/projects/Citations}"
DATA_ROOT="${DATA_ROOT:-/root/sdb1/openalex/subjects/prevalence_regressions_full}"
WORK_DIR="${WORK_DIR:-/root/sdb1/openalex/subjects/prevalence_regressions_full_work}"
LOG_DIR="${LOG_DIR:-/root/sdb1/openalex/subjects/prevalence_regressions_full_logs}"
REPORT="${REPORT:-${REPO_DIR}/reports/subjects/full_economics_prevalence_regressions.html}"
REFERENCE_WORKERS="${REFERENCE_WORKERS:-12}"

mkdir -p "$DATA_ROOT" "$WORK_DIR" "$LOG_DIR"
cd "$REPO_DIR"

python3 scripts/build_subject_prevalence_regression_data.py \
  --subject economics_econometrics_and_finance \
  --output-root "$DATA_ROOT" \
  --sample-mod 1 \
  --sample-keep 1 \
  --max-authors 0 \
  --min-author-papers 2 \
  --reference-workers "$REFERENCE_WORKERS" \
  > "$LOG_DIR/build.log" 2>&1

INPUT="${DATA_ROOT}/economics_econometrics_and_finance/paper_author_year_prevalence_regression.csv.gz"
ROWS="$(python3 - <<'PY' "$INPUT"
import gzip
import sys
path = sys.argv[1]
rows = 0
with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
    next(handle)
    for _ in handle:
        rows += 1
print(rows)
PY
)"

python3 scripts/render_full_prevalence_regressions_numpy.py \
  --input "$INPUT" \
  --output "$REPORT" \
  --work-dir "$WORK_DIR" \
  --row-count "$ROWS" \
  > "$LOG_DIR/render.log" 2>&1

git add \
  scripts/render_full_prevalence_regressions_numpy.py \
  scripts/run_full_economics_prevalence_regressions.sh \
  reports/subjects/full_economics_prevalence_regressions.html \
  reports/subjects/full_economics_prevalence_regressions.summary.json

if ! git diff --cached --quiet; then
  git commit -m "Add full economics prevalence regressions"
  git push
fi
