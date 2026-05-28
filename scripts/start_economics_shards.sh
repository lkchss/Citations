#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/sdb1/openalex"
PROJECT="/root/sdb1/projects/Citations"
BASE_DIR="$ROOT/economics_field20"
SHARD_ROOT="$ROOT/economics_field20_shards_balanced"
OLD_SHARDS="$ROOT/economics_field20_shards"
ID_CACHE="$ROOT/economics_existing_ids.txt"

mkdir -p "$SHARD_ROOT"
cd "$PROJECT"

start_shard() {
  local name="$1"
  shift
  local out="$SHARD_ROOT/$name"
  mkdir -p "$out"
  setsid -f python3 scripts/pull_openalex_economics.py \
    --output-dir "$out" \
    "$@" \
    --exclude-ids-file "$ID_CACHE" \
    --per-page 200 \
    --sleep 0.05 \
    >> "$out/pull.log" 2>&1
}

start_shard "to_1989" --to-publication-year 1989
start_shard "1990_1999" --from-publication-year 1990 --to-publication-year 1999
start_shard "2000_2009" --from-publication-year 2000 --to-publication-year 2009
start_shard "2010_2014" --from-publication-year 2010 --to-publication-year 2014
start_shard "2015_2019" --from-publication-year 2015 --to-publication-year 2019
start_shard "2020_2026" --from-publication-year 2020 --to-publication-year 2026

echo "Started balanced economics shards under $SHARD_ROOT"
