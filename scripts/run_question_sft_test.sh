#!/usr/bin/env bash
# bash scripts/run_question_sft_test.sh

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

INPUT="chunk_data/test100.jsonl"

MATERIAL_PLAN_OUT="labeled_data/question_test_200_material_plan.jsonl"
QUESTIONS_OUT="labeled_data/question_test_200_questions.jsonl"
QUESTIONS_SCORED_OUT="labeled_data/question_test_200_questions_scored.jsonl"
QUESTIONS_FILTERED_OUT="labeled_data/question_test_200_questions_filtered.jsonl"

mkdir -p labeled_data

echo "[1/3] Plan question generation"
python scripts/evaluate_sft_material.py \
  --input "$INPUT" \
  --output "$MATERIAL_PLAN_OUT" \
  --config configs/eval.json \
  --limit 100 \
  --workers 8

echo "[2/3] Generate questions"
python scripts/generate_sft_questions.py \
  --input "$MATERIAL_PLAN_OUT" \
  --output "$QUESTIONS_OUT" \
  --config configs/question.json \
  --workers 8

echo "[3/3] Filter questions"
python scripts/filter_sft_questions.py \
  --input "$QUESTIONS_OUT" \
  --output "$QUESTIONS_FILTERED_OUT" \
  --scored-output "$QUESTIONS_SCORED_OUT" \
  --config configs/question_filter.json \
  --pass-score 7 \
  --workers 8

echo
echo "Done."
echo "Material plan:      $MATERIAL_PLAN_OUT"
echo "Questions raw:      $QUESTIONS_OUT"
echo "Questions scored:   $QUESTIONS_SCORED_OUT"
echo "Questions filtered: $QUESTIONS_FILTERED_OUT"
