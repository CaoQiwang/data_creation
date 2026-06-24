#!/usr/bin/env bash
# bash scripts/run_full_sft_test.sh


set -euo pipefail

cd "$(dirname "$0")/.."

INPUT="chunk_data/test_200.jsonl"
TAXONOMY="configs/military_sft_taxonomy_compact.json"

SCORES_OUT="labeled_data/full_test_200_scores.jsonl"
CLASSIFIED_OUT="labeled_data/full_test_200_classified.jsonl"
QUESTIONS_OUT="labeled_data/full_test_200_questions.jsonl"
ANSWERS_OUT="labeled_data/full_test_200_answers.jsonl"

mkdir -p labeled_data

echo "[1/4] Evaluate chunks"
python scripts/evaluate_sft_material.py \
  --input "$INPUT" \
  --output "$SCORES_OUT" \
  --config configs/eval.json \
  --limit 200 \
  --workers 8

echo "[2/4] Classify evaluated data"
python scripts/classify_sft_material.py \
  --input "$SCORES_OUT" \
  --output "$CLASSIFIED_OUT" \
  --config configs/classify.json \
  --taxonomy "$TAXONOMY" \
  --min-score 7 \
  --workers 2

echo "[3/4] Generate questions"
python scripts/generate_sft_questions.py \
  --input "$CLASSIFIED_OUT" \
  --output "$QUESTIONS_OUT" \
  --config configs/question.json \
  --min-score 7 \
  --workers 8

echo "[4/4] Generate answers"
python scripts/generate_sft_answers.py \
  --input "$QUESTIONS_OUT" \
  --output "$ANSWERS_OUT" \
  --config configs/answer.json \
  --workers 8

echo
echo "Done."
echo "Scores:     $SCORES_OUT"
echo "Classified: $CLASSIFIED_OUT"
echo "Questions:  $QUESTIONS_OUT"
echo "Answers:    $ANSWERS_OUT"
