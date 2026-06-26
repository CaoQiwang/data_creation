# SFT 数据构建流程

本仓库用于把军事领域公开文本构造成 SFT 训练样本。主流程如下：

```text
raw_data
  -> chunk_data
  -> labeled_data/*_scores.jsonl
  -> labeled_data/*_questions.jsonl
  -> labeled_data/*_answers.jsonl
  -> final_sft_data/*_sft_samples.jsonl
```

所有主数据文件均采用 JSONL 格式：一行一个 JSON 对象。后续阶段通常保留前一阶段字段，并追加本阶段生成的新字段。

## 目录说明

- `raw_data/`：原始数据，包括 PDF、Markdown、TXT 等来源文件。
- `raw_data/md_from_pdf/`：由 MinerU 等工具从 PDF 解析得到的 Markdown。
- `chunk_data/`：从原始数据切分得到的文本块。
- `labeled_data/`：模型辅助标注结果，包括材料评分、问题和答案。
- `final_sft_data/`：最终可用于训练的 `instruction/input/output` 样本。
- `configs/`：各阶段 API 配置。
- `scripts/`：数据切分、评分、出题、答题脚本。

## 1. 原始数据到 chunk_data

Markdown 数据通常来自 `raw_data/md_from_pdf/*.md`，由 `pre_chunk_scripts/chunking/chunk_md.py` 切分。TXT 数据来自 `raw_data/txt/`，由 `pre_chunk_scripts/chunking/chunk_txt.py` 切分。`scripts/` 目录只保留 chunk 完成后的评估、分类、出题和答题流水线脚本。

标准 chunk 行示例：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "text": "中国国防有着悠久的历史……",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 3,
  "char_count": 910
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 文本块唯一 ID，通常是 `source#序号` |
| `text` | string | 切分后的正文文本 |
| `source` | string | 原始文件相对路径 |
| `chunk_index` | number | 当前来源文件内的块序号 |
| `char_count` | number | 去除空白后的字符数 |

## 2. 材料评分

评分阶段建议读取当前第一版主数据 `chunk_data/v1_chunks.jsonl`，输出到：

```text
labeled_data/*_scores.jsonl
```

运行示例：

```powershell
python scripts\evaluate_sft_material.py `
  --input chunk_data\v1_chunks.jsonl `
  --output labeled_data\full_test_200_scores.jsonl `
  --config configs\eval.json `
  --limit 200
```

本阶段追加 `sft_material_eval` 字段：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "text": "中国国防有着悠久的历史……",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 3,
  "char_count": 910,
  "sft_material_eval": {
    "score": 7,
    "quality_level": "良好",
    "reason": "内容涉及中国古代和近代国防历史，适合构造问答样本。",
    "issues": ["部分文本存在排版问题"],
    "suggested_use": "可用于构造国防历史、政策、兵制和工程建设相关问答。"
  }
}
```

核心字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `sft_material_eval.score` | number | 0-10 分材料质量评分 |
| `sft_material_eval.quality_level` | string | 质量等级 |
| `sft_material_eval.reason` | string | 评分理由 |
| `sft_material_eval.issues` | array[string] | 主要问题 |
| `sft_material_eval.suggested_use` | string | 推荐构造方向 |

## 3. 生成 SFT 问题

问题生成阶段读取评分结果，输出到：

```text
labeled_data/*_questions.jsonl
```

当前脚本支持“一段材料生成多个问题”。模型内部返回 `questions: []`，落盘时会展开成多行：每一行仍然只包含一个 `sft_question`，因此下游答案脚本可以继续按“一行一个问题”处理。

运行示例：

```powershell
python scripts\generate_sft_questions.py `
  --input labeled_data\full_test_200_scores.jsonl `
  --output labeled_data\full_test_200_questions.jsonl `
  --config configs\question.json `
  --min-score 7 `
  --max-questions 3
```

本阶段新增或更新字段：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003#q0001",
  "material_id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "question_index": 1,
  "question_count": 2,
  "sft_question": {
    "question": "中国古代国防建设在兵制方面有哪些主要形式？请列举并简要说明其特点。",
    "question_type": "extraction",
    "target_label_id": "",
    "expected_answer_format": "bullets",
    "difficulty": "medium",
    "risk_label": "public_safe",
    "reason": "该问题聚焦材料中的兵制建设信息，适合训练结构化抽取能力。",
    "status": "ok"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 问题级 ID，格式通常为 `material_id#q0001` |
| `material_id` | string | 原始材料 chunk ID |
| `question_index` | number | 当前材料下的问题序号 |
| `question_count` | number | 当前材料实际生成的问题数量 |
| `sft_question.question` | string | 生成的问题 |
| `sft_question.question_type` | string | `qa` / `summary` / `extraction` / `classification` / `comparison` / `reasoning` 等 |
| `sft_question.target_label_id` | string | 兼容旧格式的能力标签 ID；新流程通常为空 |
| `sft_question.expected_answer_format` | string | `plain_text` / `bullets` / `table` / `json` |
| `sft_question.difficulty` | string | `easy` / `medium` / `hard` |
| `sft_question.risk_label` | string | 问题风险标签 |
| `sft_question.status` | string | `ok` / `empty_question` / `api_error` / `worker_error` |

## 4. 生成 SFT 答案

答案生成阶段读取问题结果，输出到：

```text
labeled_data/*_answers.jsonl
```

运行示例：

```powershell
python scripts\generate_sft_answers.py `
  --input labeled_data\full_test_200_questions.jsonl `
  --output labeled_data\full_test_200_answers.jsonl `
  --config configs\answer.json
```

本阶段追加 `sft_answer` 字段：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003#q0001",
  "material_id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "sft_question": {
    "question": "中国古代国防建设在兵制方面有哪些主要形式？请列举并简要说明其特点。",
    "question_type": "extraction",
    "target_label_id": ""
  },
  "sft_answer": {
    "answer": "中国古代国防建设中的兵制形式主要包括民军制、征兵制、府兵制和募兵制等……",
    "risk_label": "public_safe",
    "quality_notes": "答案结构清晰，适合作为 SFT 样本输出。",
    "status": "ok",
    "answer_from_question_only": true,
    "question": "中国古代国防建设在兵制方面有哪些主要形式？请列举并简要说明其特点。"
  }
}
```

说明：当前答案生成脚本只把 `sft_question.question` 发给模型，不传原始 `text`，因此 `answer_from_question_only` 固定为 `true`。

核心字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `sft_answer.answer` | string | 生成答案 |
| `sft_answer.risk_label` | string | 答案风险标签 |
| `sft_answer.quality_notes` | string | 答案生成说明 |
| `sft_answer.status` | string | `ok` / `empty_answer` / `api_error` / `worker_error` |
| `sft_answer.answer_from_question_only` | boolean | 是否只基于问题生成答案 |
| `sft_answer.question` | string | 实际发送给模型的问题，便于审计 |

## 5. 最终 SFT 样本

最终样本位于：

```text
final_sft_data/*_sft_samples.jsonl
```

单行 JSON 示例：

```json
{
  "sample_id": "mil-sft-00000001",
  "source_id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003#q0001",
  "task_type": "extraction",
  "instruction": "中国古代国防建设在兵制方面有哪些主要形式？请列举并简要说明其特点。",
  "input": "",
  "output": "中国古代国防建设中的兵制形式主要包括民军制、征兵制、府兵制和募兵制等……",
  "output_format": "bullets",
  "difficulty": "medium",
  "risk_label": "public_safe",
  "quality": {
    "faithfulness": null,
    "specificity": null,
    "usefulness": null,
    "clarity": null,
    "safety": null
  },
  "judge_decision": "keep",
  "error_type": "none",
  "generation": {
    "answer_from_question_only": true,
    "answer_status": "ok",
    "quality_notes": "答案结构清晰，适合作为 SFT 样本输出。"
  }
}
```

最终训练字段主要是：

| 字段 | 类型 | 说明 |
|---|---|---|
| `instruction` | string | 用户指令或问题 |
| `input` | string | 额外输入；当前通常为空 |
| `output` | string | 目标答案 |
| `task_type` | string | 任务类型 |
| `risk_label` | string | 样本风险标签 |
| `judge_decision` | string | 样本保留决策，如 `keep` |
| `generation` | object | 答案生成元信息 |

## 快速运行

单阶段运行可按上文命令逐步执行。若只想跑 200 条端到端测试：

```bash
bash scripts/run_full_sft_test.sh
```

该脚本会依次生成：

```text
labeled_data/full_test_200_scores.jsonl
labeled_data/full_test_200_questions.jsonl
labeled_data/full_test_200_answers.jsonl
```

若只想测试到生成问题环节：

```bash
bash scripts/run_question_sft_test.sh
```

该脚本会依次生成：

```text
labeled_data/question_test_200_scores.jsonl
labeled_data/question_test_200_questions.jsonl
```

脚本会自动读取项目根目录下的 `.env`。例如：

```env
SILICONFLOW_API_KEY=你的真实 key
```

## 质量与筛选建议

- 优先使用 `sft_material_eval.score >= 7` 的材料进入出题阶段。
- 问题生成阶段已经支持一段材料生成多个问题，但仍应检查同一 `material_id` 下是否存在近义重复问题。
- 优先保留 `risk_label = public_safe` 且 `status = ok` 的问题和答案。
- 对 `needs_caution` 或 `refuse_or_exclude` 样本应人工复核，必要时剔除。
- 进入 `final_sft_data` 前，建议检查 `instruction` 是否清晰、`output` 是否回答了问题。
