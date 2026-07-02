#!/usr/bin/env bash
# bash scripts/run.sh

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

INPUT="chunk_data/v2_chunks.jsonl"

MATERIAL_PLAN_OUT="labeled_data/v2_material_plan.jsonl"
QUESTIONS_OUT="labeled_data/v2_questions.jsonl"
QUESTIONS_SCORED_OUT="labeled_data/v2_questions_scored.jsonl"
QUESTIONS_FILTERED_OUT="labeled_data/v2_questions_filtered.jsonl"
ANSWERS_OUT="labeled_data/v2_answers.jsonl"
ANSWERS_SCORED_OUT="labeled_data/v2_answers_scored.jsonl"
ANSWERS_FILTERED_OUT="labeled_data/v2_answers_filtered.jsonl"
FINAL_SFT_OUT="final_sft_data/v2_ms_swift.jsonl"

mkdir -p labeled_data final_sft_data

echo "[1/6] Plan question generation"
python scripts/evaluate_sft_material.py \
  --input "$INPUT" \
  --output "$MATERIAL_PLAN_OUT" \
  --config configs/eval.json \
  --workers 16

echo "[2/6] Generate questions"
python scripts/generate_sft_questions.py \
  --input "$MATERIAL_PLAN_OUT" \
  --output "$QUESTIONS_OUT" \
  --config configs/question.json \
  --workers 16

echo "[3/6] Filter questions"
python scripts/filter_sft_questions.py \
  --input "$QUESTIONS_OUT" \
  --output "$QUESTIONS_FILTERED_OUT" \
  --scored-output "$QUESTIONS_SCORED_OUT" \
  --config configs/question_filter.json \
  --pass-score 6 \
  --workers 16

echo "[4/6] Generate answers"
python scripts/generate_sft_answers.py \
  --input "$QUESTIONS_FILTERED_OUT" \
  --output "$ANSWERS_OUT" \
  --config configs/answer.json \
  --workers 16

echo "[5/6] Filter answers"
python scripts/filter_sft_answers.py \
  --input "$ANSWERS_OUT" \
  --output "$ANSWERS_FILTERED_OUT" \
  --scored-output "$ANSWERS_SCORED_OUT" \
  --config configs/answer_filter.json \
  --pass-score 8 \
  --workers 16

echo "[6/6] Convert to ms-swift SFT format"
python scripts/convert_to_ms_swift_sft.py \
  --input "$ANSWERS_FILTERED_OUT" \
  --output "$FINAL_SFT_OUT"

echo
echo "Done."
echo "Material plan:       $MATERIAL_PLAN_OUT"
echo "Questions raw:       $QUESTIONS_OUT"
echo "Questions scored:    $QUESTIONS_SCORED_OUT"
echo "Questions filtered:  $QUESTIONS_FILTERED_OUT"
echo "Answers raw:         $ANSWERS_OUT"
echo "Answers scored:      $ANSWERS_SCORED_OUT"
echo "Answers filtered:    $ANSWERS_FILTERED_OUT"
echo "Final ms-swift SFT:  $FINAL_SFT_OUT"
