# Data Layout

This workspace keeps each data stage in a separate directory:

- `raw_data/`: original source files. Do not move or rewrite these files during processing.
- `chunk_data/`: chunks generated directly from `raw_data/`, including `*_chunks.jsonl`, `*_chunks.txt`, and `*_chunks_stats.json`.
- `labeled_data/`: downstream annotation outputs, including SFT material evaluation scores, taxonomy classification results, generated SFT construction questions, and generated answers.
- `configs/`: API configs and compact taxonomy files used by scripts.
- `military_sft_taxonomy/`: source taxonomy markdown files.

Recommended commands:

```powershell
python scripts\evaluate_sft_material.py `
  --input chunk_data\md_paragraph_chunks.jsonl `
  --output labeled_data\md_sft_material_scores.jsonl `
  --config configs\eval.json
```

```powershell
python scripts\classify_sft_material.py `
  --input labeled_data\md_sft_material_scores.jsonl `
  --output labeled_data\md_sft_material_classified.jsonl `
  --config configs\classify.json `
  --taxonomy configs\military_sft_taxonomy_compact.json `
  --min-score 7
```

```powershell
python scripts\generate_sft_questions.py `
  --input labeled_data\md_sft_material_classified.jsonl `
  --output labeled_data\md_sft_questions.jsonl `
  --config configs\question.json `
  --min-score 7
```

```powershell
python scripts\generate_sft_answers.py `
  --input labeled_data\md_sft_questions.jsonl `
  --output labeled_data\md_sft_answers.jsonl `
  --config configs\answer.json
```

Full 200-row pipeline test:

```bash
bash scripts/run_full_sft_test.sh
```
