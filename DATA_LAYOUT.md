# Data Layout

This workspace separates pre-chunk source preparation from the downstream SFT pipeline.

## Directories

- `raw_data/`: original and source-level data. Keep raw files here.
- `raw_data/wiki/`: local Wikipedia dump, extracted article JSONL shards, and page-level wiki filters.
- `pre_chunk_scripts/`: scripts used before or while constructing `chunk_data`.
- `chunk_data/v1_chunks.jsonl`: current first-version chunk dataset.
- `chunk_data/v1_chunks_stats.json`: source counts and merge stats for `v1_chunks.jsonl`.
- `chunk_data/intermediate/`: reproducible intermediate chunk-stage outputs.
- `scripts/`: downstream SFT pipeline scripts only: evaluate, classify, generate questions, generate answers.
- `labeled_data/`: model-assisted annotation outputs.
- `final_sft_data/`: final SFT samples.
- `configs/`: API configs and taxonomy files.

## Pre-Chunk Scripts

```text
pre_chunk_scripts/
  chunking/
    chunk_md.py
    chunk_txt.py
    rule_prefilter_chunks.py
  crawlers/
    crawl_81cn_txt.py
    run_81cn_sections.ps1
  pdf/
    parse_pdf_with_mineru.py
  wiki/
    extract_wiki_text.py
    filter_military_pages.py
    chunk_military_pages.py
    build_v1_dataset.py
```

## Current V1 Dataset

The current first-version chunk dataset is:

```text
chunk_data/v1_chunks.jsonl
```

It is built from:

```text
chunk_data/intermediate/rule_prefilter/rule_prefiltered_chunks.jsonl
chunk_data/intermediate/wiki/wiki_military_title_strict_prefiltered_chunks.jsonl
```

Each row has:

```text
dataset_version = "v1"
dataset_source  = "existing_rule_prefiltered" or "wiki_military_title_strict"
```

## Downstream Pipeline

Use `chunk_data/v1_chunks.jsonl` as the material input for the downstream scripts:

```powershell
python scripts\evaluate_sft_material.py `
  --input chunk_data\v1_chunks.jsonl `
  --output labeled_data\v1_material_scores.jsonl `
  --config configs\eval.json
```

```powershell
python scripts\classify_sft_material.py `
  --input labeled_data\v1_material_scores.jsonl `
  --output labeled_data\v1_material_classified.jsonl `
  --config configs\classify.json `
  --taxonomy configs\military_sft_taxonomy_compact.json `
  --min-score 7
```

```powershell
python scripts\generate_sft_questions.py `
  --input labeled_data\v1_material_classified.jsonl `
  --output labeled_data\v1_questions.jsonl `
  --config configs\question.json `
  --min-score 7
```

```powershell
python scripts\generate_sft_answers.py `
  --input labeled_data\v1_questions.jsonl `
  --output labeled_data\v1_answers.jsonl `
  --config configs\answer.json
```
