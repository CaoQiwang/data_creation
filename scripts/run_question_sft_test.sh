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

INPUT="chunk_data/test_200.jsonl"

SCORES_OUT="labeled_data/question_test_200_scores.jsonl"
QUESTIONS_OUT="labeled_data/question_test_200_questions.jsonl"

mkdir -p labeled_data

echo "[1/2] Evaluate chunks"
python scripts/evaluate_sft_material.py \
  --input "$INPUT" \
  --output "$SCORES_OUT" \
  --config configs/eval.json \
  --limit 100 \
  --workers 8

echo "[2/2] Generate questions"
python scripts/generate_sft_questions.py \
  --input "$SCORES_OUT" \
  --output "$QUESTIONS_OUT" \
  --config configs/question.json \
  --min-score 7 \
  --workers 8

echo
echo "Done."
echo "Scores:    $SCORES_OUT"
echo "Questions: $QUESTIONS_OUT"
