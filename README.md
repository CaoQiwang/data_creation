# 军事领域 SFT 数据构造流程

本仓库用于把公开军事、国防、安全相关文本构造成可用于 SFT 训练的问答样本。当前主流程已经从旧版“材料打分 -> 出题 -> 答题”调整为：

```text
raw_data/
  -> chunk_data/v2_chunks.jsonl
  -> labeled_data/*_material_plan.jsonl
  -> labeled_data/*_questions.jsonl
  -> labeled_data/*_questions_scored.jsonl
  -> labeled_data/*_questions_filtered.jsonl
  -> labeled_data/*_questions_classified.jsonl  # 可选：问题级 taxonomy 分类
  -> labeled_data/*_answers.jsonl
  -> labeled_data/*_answers_scored.jsonl
  -> labeled_data/*_answers_filtered.jsonl
  -> final_sft_data/*_ms_swift.jsonl
```

核心变化：

- `evaluate_sft_material.py` 现在做的是“出题规划”，不是传统质量打分。它为每个 chunk 判断推荐生成几个问题、适合哪些问题类型。
- 问题生成后新增 `filter_sft_questions.py`，先过滤掉不独立、不自然、不安全或训练价值低的问题。
- taxonomy 分类不再对材料打标签，而是在问题生成并过滤后，对 `sft_question.question` 打问题级能力标签。该步骤仍为可选。
- 答案生成后新增 `filter_sft_answers.py`，再按完整问答对质量过滤。
- 最终由 `convert_to_ms_swift_sft.py` 转成 ms-swift `messages` 格式。

所有主数据文件均为 JSONL：一行一个 JSON 对象。后续阶段通常保留上一阶段字段，并追加本阶段结果字段，便于审计和回溯。

## 目录说明

- `raw_data/`：原始数据，包括 TXT、Markdown、PDF 解析结果、wiki 等。
- `pre_chunk_scripts/`：chunk 构造前后的脚本，包括爬取、PDF 解析、wiki 处理、分块、规则初筛、v2 汇总。
- `chunk_data/`：分块数据和中间产物。当前推荐主输入是 `chunk_data/v2_chunks.jsonl`。
- `labeled_data/`：模型辅助生成和评估结果，包括出题规划、问题、问题评分、答案、答案评分。
- `final_sft_data/`：最终训练格式数据，目前输出为 ms-swift messages JSONL。
- `configs/`：各阶段 API 配置、过滤配置和分类 taxonomy。
- `scripts/`：SFT 主流水线脚本。

## 1. 构造 chunk 数据

当前推荐使用 v2 chunk 数据：

```text
chunk_data/v2_chunks.jsonl
chunk_data/v2_chunks_stats.json
```

v2 由 `pre_chunk_scripts/chunking/build_v2_chunks.py` 汇总生成，来源包括：

- `raw_data/txt/`
- `raw_data/md_from_pdf/`
- `chunk_data/intermediate/pdf_guofang_keji/pdf_paragraph_chunks.jsonl`
- `chunk_data/intermediate/pdf_junshi_lishi/pdf_paragraph_chunks.jsonl`
- `chunk_data/intermediate/wiki/wiki_military_title_strict_prefiltered_chunks.jsonl`

重新构建：

```powershell
python pre_chunk_scripts\chunking\build_v2_chunks.py
```

常用参数：

```powershell
python pre_chunk_scripts\chunking\build_v2_chunks.py `
  --output chunk_data\v2_chunks.jsonl `
  --stats-output chunk_data\v2_chunks_stats.json `
  --min-chars 80 `
  --target-chars 900 `
  --max-chars 1800 `
  --include-wiki
```

单条 chunk 典型字段：

```json
{
  "id": "raw_txt_v2/raw_data/txt/0/00_white_papers/example.txt#00001",
  "text": "分块正文文本",
  "source": "raw_data/txt/0/00_white_papers/example.txt",
  "title": "example",
  "chunk_index": 1,
  "char_count": 923,
  "dataset_version": "v2",
  "dataset_source": "raw_txt_v2"
}
```

`dataset_source` 用来区分来源，如 `raw_txt_v2`、`raw_md_v2`、`pdf_guofang_keji_v2`、`pdf_junshi_lishi_v2`、`wiki_military_title_strict_v2`。

## 2. 出题规划

脚本：

```text
scripts/evaluate_sft_material.py
```

虽然脚本名仍是 evaluate，但当前输出字段 `sft_material_eval` 表示“出题规划”，包含：

- `recommended_question_count`：建议为该 chunk 生成多少个问题。
- `recommended_question_types`：推荐问题类型，如 `qa`、`summary`、`reasoning`、`comparison`，由 `question_type_plan` 汇总得到。
- `question_type_plan`：写死给下一阶段执行的题型计划，包含每种 `question_type` 的 `count` 和推荐理由；所有 `count` 之和应等于 `recommended_question_count`。
- `reason` / `issues` / `suggested_use` / `question_count_reason`：规划依据和注意事项。

运行示例：

```powershell
python scripts\evaluate_sft_material.py `
  --input chunk_data\v2_chunks.jsonl `
  --output labeled_data\v2_material_plan.jsonl `
  --config configs\eval.json `
  --workers 8
```

小样本联调可加 `--limit`：

```powershell
python scripts\evaluate_sft_material.py `
  --input chunk_data\test100.jsonl `
  --output labeled_data\test100_material_plan.jsonl `
  --config configs\eval.json `
  --limit 100 `
  --workers 8
```

## 3. 生成问题

脚本：

```text
scripts/generate_sft_questions.py
```

输入为出题规划结果，脚本会优先根据 `question_type_plan` 为每个材料生成一个或多个问题；若旧数据没有该字段，则回退到 `recommended_question_count` 和 `recommended_question_types`。输出会把一条材料展开成多条问题行，问题行 ID 形如：

```text
<material_id>#q0001
```

运行示例：

```powershell
python scripts\generate_sft_questions.py `
  --input labeled_data\v2_material_plan.jsonl `
  --output labeled_data\v2_questions.jsonl `
  --config configs\question.json `
  --workers 8
```

可用 `--max-questions` 给单个材料的问题数加硬上限：

```powershell
python scripts\generate_sft_questions.py `
  --input labeled_data\v2_material_plan.jsonl `
  --output labeled_data\v2_questions.jsonl `
  --config configs\question.json `
  --max-questions 3 `
  --workers 8
```

新增字段：

- `material_id`：原始 chunk ID。
- `question_index` / `question_count`：该材料下的问题序号和问题总数。
- `planned_question_type`：规划阶段为该问题指定的题型。
- `question_type_plan`：该材料完整题型计划的副本。
- `sft_question`：生成的问题及元信息。

`sft_question.question` 必须是独立可回答的问题，不能依赖“根据材料”“结合上文”等隐藏上下文，因为后续答案生成只会看到问题本身。

## 4. 过滤问题

脚本：

```text
scripts/filter_sft_questions.py
```

该阶段评估问题是否适合进入答案生成。它会输出两份文件：

- `*_questions_scored.jsonl`：所有已评分问题，包含通过和拒绝。
- `*_questions_filtered.jsonl`：仅保留通过过滤的问题。

运行示例：

```powershell
python scripts\filter_sft_questions.py `
  --input labeled_data\v2_questions.jsonl `
  --output labeled_data\v2_questions_filtered.jsonl `
  --scored-output labeled_data\v2_questions_scored.jsonl `
  --config configs\question_filter.json `
  --pass-score 7 `
  --workers 8
```

新增字段：

```text
sft_question_eval
```

主要字段包括 `score`、`pass_filter`、`quality_level`、`reason`、`issues`、`suggested_action`、`rewrite_suggestion`、`risk_label`。

## 5. 可选：问题分类标注

脚本：

```text
scripts/classify_sft_questions.py
```

当前语义是“问题级分类”：输入应使用问题过滤后的文件，分类对象是 `sft_question.question`，不是原始材料 `text`。旧入口 `scripts/classify_sft_material.py` 仍保留用于兼容，但新流程建议使用 `classify_sft_questions.py`。

运行示例：

```powershell
python scripts\classify_sft_questions.py `
  --input labeled_data\v2_questions_filtered.jsonl `
  --output labeled_data\v2_questions_classified.jsonl `
  --config configs\classify.json `
  --taxonomy configs\military_sft_taxonomy_compact.json `
  --workers 8
```

如果只想分类高分问题，可加：

```powershell
python scripts\classify_sft_questions.py `
  --input labeled_data\v2_questions_filtered.jsonl `
  --output labeled_data\v2_questions_classified.jsonl `
  --config configs\classify.json `
  --taxonomy configs\military_sft_taxonomy_compact.json `
  --min-question-score 8 `
  --workers 8
```

新增字段：

```text
sft_question_taxonomy_labels
```

主要字段包括 `primary`、`task_types`、`source_type`、`risk_label`、`confidence`、`reason`、`evidence_keywords`、`candidate_label_ids`。

如果运行了该步骤，后续答案生成建议读取：

```text
labeled_data/v2_questions_classified.jsonl
```

如果不需要分类，直接用 `v2_questions_filtered.jsonl` 进入答案生成即可。

## 6. 生成答案

脚本：

```text
scripts/generate_sft_answers.py
```

输入应使用问题过滤后的文件。答案生成阶段只把 `sft_question.question` 发给模型，不传原始 `text`，因此生成结果更接近最终训练样本的真实使用形态。

运行示例：

```powershell
python scripts\generate_sft_answers.py `
  --input labeled_data\v2_questions_filtered.jsonl `
  --output labeled_data\v2_answers.jsonl `
  --config configs\answer.json `
  --workers 8
```

如果已经执行可选分类，则把输入替换为 `labeled_data\v2_questions_classified.jsonl`。

新增字段：

```text
sft_answer
```

主要字段包括 `answer`、`risk_label`、`quality_notes`、`status`、`answer_from_question_only`、`question`。

## 7. 过滤问答对

脚本：

```text
scripts/filter_sft_answers.py
```

该阶段评估完整 question-answer 是否能直接作为 SFT 样本。它同样输出两份文件：

- `*_answers_scored.jsonl`：所有已评分问答对。
- `*_answers_filtered.jsonl`：仅保留通过过滤的问答对。

运行示例：

```powershell
python scripts\filter_sft_answers.py `
  --input labeled_data\v2_answers.jsonl `
  --output labeled_data\v2_answers_filtered.jsonl `
  --scored-output labeled_data\v2_answers_scored.jsonl `
  --config configs\answer_filter.json `
  --pass-score 7 `
  --workers 8
```

新增字段：

```text
sft_answer_eval
```

主要字段包括 `score`、`pass_filter`、`quality_level`、`reason`、`issues`、`suggested_action`、`answer_issue_type`、`risk_label`。

## 8. 转换为 ms-swift 格式

脚本：

```text
scripts/convert_to_ms_swift_sft.py
```

输入应使用答案过滤后的文件。默认输出只包含 `messages`：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "问题文本"
    },
    {
      "role": "assistant",
      "content": "答案文本"
    }
  ]
}
```

运行示例：

```powershell
python scripts\convert_to_ms_swift_sft.py `
  --input labeled_data\v2_answers_filtered.jsonl `
  --output final_sft_data\v2_ms_swift.jsonl
```

可选保留轻量元数据：

```powershell
python scripts\convert_to_ms_swift_sft.py `
  --input labeled_data\v2_answers_filtered.jsonl `
  --output final_sft_data\v2_ms_swift_with_meta.jsonl `
  --include-metadata
```

如果上游执行过问题分类，`--include-metadata` 会额外写入 `taxonomy_label_id`、`taxonomy_label_path` 和 `taxonomy_confidence`。

脚本还会生成统计文件，默认路径为：

```text
final_sft_data/v2_ms_swift.stats.json
```

## 快速联调

仓库提供了基于 `chunk_data/test100.jsonl` 的联调脚本。

只跑到问题过滤：

```bash
bash scripts/run_question_sft_test.sh
```

完整跑通出题规划、问题生成、问题过滤、答案生成、答案过滤和 ms-swift 转换：

```bash
bash scripts/run_full_sft_test.sh
```

完整联调会生成：

```text
labeled_data/full_test_100_material_plan.jsonl
labeled_data/full_test_100_questions.jsonl
labeled_data/full_test_100_questions_scored.jsonl
labeled_data/full_test_100_questions_filtered.jsonl
labeled_data/full_test_100_answers.jsonl
labeled_data/full_test_100_answers_scored.jsonl
labeled_data/full_test_100_answers_filtered.jsonl
final_sft_data/full_test_100_ms_swift.jsonl
```

## API 配置

各阶段配置位于：

```text
configs/eval.json
configs/question.json
configs/question_filter.json
configs/answer.json
configs/answer_filter.json
```

脚本会读取配置中的 `api_key`，也支持环境变量。项目根目录可放 `.env`，联调脚本会自动加载：

```env
SILICONFLOW_API_KEY=你的 key
```

也可使用：

```env
OPENAI_API_KEY=你的 key
```

## 断点续跑

多数主流水线脚本支持 `--skip-done`。开启后会跳过输出文件中已有 ID，适合 API 中断后续跑：

```powershell
python scripts\generate_sft_answers.py `
  --input labeled_data\v2_questions_filtered.jsonl `
  --output labeled_data\v2_answers.jsonl `
  --config configs\answer.json `
  --skip-done `
  --workers 8
```

注意：使用 `--skip-done` 时脚本会追加写入输出文件；如果希望重跑一版干净结果，请换一个输出文件名或先自行备份旧文件。

## 更新 taxonomy

```powershell
python scripts\build_taxonomy_summary.py `
  --taxonomy-root ..\military_sft_taxonomy `
  --output configs\military_sft_taxonomy_compact.json
```

## 质量控制建议

- 主流程输入优先使用 `chunk_data/v2_chunks.jsonl`；`chunk_data/test100.jsonl` 仅用于快速联调。
- 出题规划阶段不要再按旧字段 `score >= 7` 理解，当前关键字段是 `recommended_question_count`、`recommended_question_types` 和 `question_type_plan`。
- 问题过滤建议使用 `--pass-score 7`，需要更高精度时可提高到 8。
- taxonomy 分类应放在问题过滤后，对通过过滤的问题打 `sft_question_taxonomy_labels`，不要再对材料打分类标签。
- 答案过滤建议使用 `--pass-score 7`，正式训练集优先保留 `sft_answer_eval.pass_filter = true` 的样本。
- 最终转换前重点检查：问题是否独立、答案是否直接回答问题、答案中是否出现“根据材料/上文/文中”等不应出现在最终样本中的表达。
