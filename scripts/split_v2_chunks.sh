#!/usr/bin/env bash
# bash scripts/split_v2_chunks.sh

set -euo pipefail

cd "$(dirname "$0")/.."

INPUT="chunk_data/v2_chunks.jsonl"
OUTPUT_PREFIX="chunk_data/v2_chunks_part"
TEMP_PREFIX="chunk_data/.v2_chunks_part_tmp_"
PARTS=4

TOTAL_LINES="$(wc -l < "$INPUT")"
LINES_PER_PART="$(((TOTAL_LINES + PARTS - 1) / PARTS))"

rm -f "${OUTPUT_PREFIX}"*.jsonl
rm -f "${TEMP_PREFIX}"*.jsonl

split \
  -d \
  -a 2 \
  -l "$LINES_PER_PART" \
  --additional-suffix=.jsonl \
  "$INPUT" \
  "$TEMP_PREFIX"

part_no=1
for file in "${TEMP_PREFIX}"*.jsonl; do
  mv "$file" "$(printf "%s%02d.jsonl" "$OUTPUT_PREFIX" "$part_no")"
  part_no="$((part_no + 1))"
done

echo "Done."
echo "Input:          $INPUT"
echo "Total lines:    $TOTAL_LINES"
echo "Parts:          $PARTS"
echo "Lines per part: $LINES_PER_PART"
wc -l "${OUTPUT_PREFIX}"*.jsonl
