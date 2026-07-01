#!/usr/bin/env bash
# bash scripts/run_full_sft_test.sh


set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

INPUT="chunk_data/test100v2.jsonl"

MATERIAL_PLAN_OUT="labeled_data/full_test_100_material_plan.jsonl"
QUESTIONS_OUT="labeled_data/full_test_100_questions.jsonl"
QUESTIONS_SCORED_OUT="labeled_data/full_test_100_questions_scored.jsonl"
QUESTIONS_FILTERED_OUT="labeled_data/full_test_100_questions_filtered.jsonl"
ANSWERS_OUT="labeled_data/full_test_100_answers.jsonl"
ANSWERS_SCORED_OUT="labeled_data/full_test_100_answers_scored.jsonl"
ANSWERS_FILTERED_OUT="labeled_data/full_test_100_answers_filtered.jsonl"
FINAL_SFT_OUT="final_sft_data/full_test_100_ms_swift.jsonl"

mkdir -p labeled_data final_sft_data

echo "[1/6] Plan question generation"
python scripts/evaluate_sft_material.py \
  --input "$INPUT" \
  --output "$MATERIAL_PLAN_OUT" \
  --config configs/eval.json \
  --limit 200 \
  --workers 8

echo "[2/6] Generate questions"
python scripts/generate_sft_questions.py \
  --input "$MATERIAL_PLAN_OUT" \
  --output "$QUESTIONS_OUT" \
  --config configs/question.json \
  --workers 8

echo "[3/6] Filter questions"
python scripts/filter_sft_questions.py \
  --input "$QUESTIONS_OUT" \
  --output "$QUESTIONS_FILTERED_OUT" \
  --scored-output "$QUESTIONS_SCORED_OUT" \
  --config configs/question_filter.json \
  --pass-score 6 \
  --workers 8

echo "[4/6] Generate answers"
python scripts/generate_sft_answers.py \
  --input "$QUESTIONS_FILTERED_OUT" \
  --output "$ANSWERS_OUT" \
  --config configs/answer.json \
  --workers 8

echo "[5/6] Filter answers"
python scripts/filter_sft_answers.py \
  --input "$ANSWERS_OUT" \
  --output "$ANSWERS_FILTERED_OUT" \
  --scored-output "$ANSWERS_SCORED_OUT" \
  --config configs/answer_filter.json \
  --pass-score 7 \
  --workers 8

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
