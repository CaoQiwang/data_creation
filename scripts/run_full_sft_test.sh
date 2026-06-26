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

INPUT="chunk_data/test_200.jsonl"

SCORES_OUT="labeled_data/full_test_200_scores.jsonl"
QUESTIONS_OUT="labeled_data/full_test_200_questions.jsonl"
ANSWERS_OUT="labeled_data/full_test_200_answers.jsonl"

mkdir -p labeled_data

echo "[1/3] Evaluate chunks"
python scripts/evaluate_sft_material.py \
  --input "$INPUT" \
  --output "$SCORES_OUT" \
  --config configs/eval.json \
  --limit 200 \
  --workers 8

echo "[2/3] Generate questions"
python scripts/generate_sft_questions.py \
  --input "$SCORES_OUT" \
  --output "$QUESTIONS_OUT" \
  --config configs/question.json \
  --min-score 7 \
  --workers 8

echo "[3/3] Generate answers"
python scripts/generate_sft_answers.py \
  --input "$QUESTIONS_OUT" \
  --output "$ANSWERS_OUT" \
  --config configs/answer.json \
  --workers 8

echo
echo "Done."
echo "Scores:     $SCORES_OUT"
echo "Questions:  $QUESTIONS_OUT"
echo "Answers:    $ANSWERS_OUT"
