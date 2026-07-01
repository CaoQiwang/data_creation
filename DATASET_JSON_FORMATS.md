# 数据集各阶段 JSON 格式

本文档按当前 SFT 数据构造流水线整理各阶段 JSONL 的字段格式。

整体流程：

```text
raw_data
  -> chunk_data
  -> labeled_data/*_scores.jsonl
  -> labeled_data/*_questions.jsonl
  -> labeled_data/*_answers.jsonl
```

说明：

- 所有主数据文件都是 JSONL：一行一个 JSON 对象。
- 后一阶段通常保留前一阶段字段，并新增本阶段字段。
- 答案生成阶段仍是中间数据，会保留前序字段并新增 `sft_answer`。
- 最终 `final_sft_data` 的转换格式后续再定义。

## 1. 分块数据

目录：

```text
chunk_data/
```

### 1.1 Markdown/PDF 分块

典型文件：

```text
chunk_data/md_paragraph_chunks.jsonl
```

来源：`raw_data/md_from_pdf/*.md`

格式：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00001",
  "text": "分块正文文本",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 1,
  "char_count": 976
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 分块唯一 ID，通常为 `source#序号` |
| `text` | string | 分块文本正文 |
| `source` | string | 原始 markdown 相对路径 |
| `chunk_index` | number | 在来源文件中的分块序号 |
| `char_count` | number | 文本字符数 |

配套统计文件：

```text
chunk_data/md_paragraph_chunks_stats.json
```

格式：

```json
{
  "chunk_count": 206,
  "min_chars": 99,
  "max_chars": 1670,
  "avg_chars": 1014.66,
  "sources": [
    "md_from_pdf/MinerU_markdown_军事理论教程.md"
  ]
}
```

### 1.2 TXT 结构化分块

典型文件：

```text
chunk_data/txt_structured_chunks.jsonl
```

来源：`raw_data/txt/`

格式：

```json
{
  "id": "00_white_papers/《中国军队参加联合国维和行动30年》白皮书.txt#00001",
  "text": "分块正文文本",
  "source": "00_white_papers/《中国军队参加联合国维和行动30年》白皮书.txt",
  "title": "《中国军队参加联合国维和行动30年》白皮书",
  "category": "white_papers",
  "chunk_index": 1,
  "char_count": 809,
  "section": "结束语"
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 分块唯一 ID |
| `text` | string | 分块文本正文 |
| `source` | string | 原始 TXT 相对路径 |
| `title` | string | 从文件名或文本中得到的标题 |
| `category` | string | 原始数据类别，如 `white_papers`、`documents` |
| `chunk_index` | number | 在来源文件中的分块序号 |
| `char_count` | number | 文本字符数 |
| `section` | string | 章节或结构段名称 |

配套统计文件：

```text
chunk_data/txt_structured_chunks_stats.json
```

格式：

```json
{
  "txt_file_count": 443,
  "chunked_source_count": 443,
  "skipped_sources": [],
  "chunk_count": 1116,
  "min_chars": 60,
  "max_chars": 9973,
  "avg_chars": 988.07,
  "categories": {
    "documents": 130,
    "laws_regulations": 289,
    "regular_press_conferences": 470,
    "white_papers": 227
  }
}
```

## 2. 材料评分数据

典型文件：

```text
labeled_data/*_scores.jsonl
```

来源：分块数据。

新增字段：

```text
sft_material_eval
```

格式：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00002",
  "text": "分块正文文本",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 2,
  "char_count": 997,
  "sft_material_eval": {
    "reason": "内容紧扣国防政策、战略类型等军事领域核心主题，信息完整且结构清晰，适合生成多类型问题。",
    "issues": [],
    "suggested_use": "适合用于生成概念解释、结构化分类和提纲类问题。",
    "recommended_question_count": 3,
    "recommended_question_types": ["qa", "classification", "outline"],
    "question_type_plan": [
      {"question_type": "qa", "count": 1, "reason": "材料包含明确概念，可生成基础问答。"},
      {"question_type": "classification", "count": 1, "reason": "材料包含分类维度，可生成分类题。"},
      {"question_type": "outline", "count": 1, "reason": "材料结构清晰，可生成学习提纲题。"}
    ],
    "question_count_reason": "材料有多个不同能力方向的信息点，推荐生成 3 个不同题型的问题。"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `sft_material_eval.reason` | string | 出题规划理由 |
| `sft_material_eval.issues` | array[string] | 主要问题 |
| `sft_material_eval.suggested_use` | string | 建议用于何种问题生成 |
| `sft_material_eval.recommended_question_count` | number | 建议为该 chunk 生成的问题总数 |
| `sft_material_eval.recommended_question_types` | array[string] | 推荐题型列表，由 `question_type_plan` 汇总得到 |
| `sft_material_eval.question_type_plan` | array[object] | 写死给下一阶段执行的题型计划，每项包含 `question_type`、`count`、`reason` |
| `sft_material_eval.question_count_reason` | string | 推荐问题数量和题型的理由 |

异常情况：

```json
{
  "sft_material_eval": {
    "reason": "API评估失败：错误信息",
    "issues": [
      "api_error"
    ],
    "suggested_use": "不建议使用，需重新评估",
    "recommended_question_count": 0,
    "recommended_question_types": [],
    "question_type_plan": [],
    "question_count_reason": "API评估失败，无法推荐问题数量和类型。"
  }
}
```

## 3. 问题生成数据

典型文件：

```text
labeled_data/*_questions.jsonl
```

来源：材料评分数据。

新增字段：

```text
sft_question
```

格式：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00004",
  "text": "分块正文文本",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 4,
  "char_count": 930,
  "sft_material_eval": {
    "reason": "出题规划理由",
    "issues": [],
    "suggested_use": "建议用途",
    "recommended_question_count": 2,
    "recommended_question_types": ["summary", "outline"],
    "question_type_plan": [
      {"question_type": "summary", "count": 1, "reason": "适合生成总结题。"},
      {"question_type": "outline", "count": 1, "reason": "适合生成提纲题。"}
    ],
    "question_count_reason": "推荐生成两个不同题型的问题。"
  },
  "material_id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00004",
  "question_index": 1,
  "question_count": 2,
  "planned_question_type": "summary",
  "question_type_plan": [
    {"question_type": "summary", "count": 1, "reason": "适合生成总结题。"},
    {"question_type": "outline", "count": 1, "reason": "适合生成提纲题。"}
  ],
  "sft_question": {
    "question": "中国近代国防历史中，抗日战争胜利的主要原因有哪些？",
    "question_type": "summary",
    "target_label_id": "",
    "expected_answer_format": "bullets",
    "difficulty": "medium",
    "risk_label": "public_safe",
    "reason": "该问题聚焦中国近代国防历史，适合构造summary类SFT样本。",
    "status": "ok"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `material_id` | string | 原始 chunk ID |
| `question_index` | number | 该材料下的问题序号 |
| `question_count` | number | 该材料实际生成的问题总数 |
| `planned_question_type` | string | 规划阶段指定给该问题的题型 |
| `question_type_plan` | array[object] | 该材料完整题型计划的副本 |
| `sft_question.question` | string | 生成的问题，也是最终 SFT 的 `instruction` |
| `sft_question.question_type` | string | `qa` / `summary` / `extraction` / `classification` / `comparison` / `reasoning` / `rewrite` / `json_generation` / `critique` / `refusal` / `drafting` / `plan` / `outline` |
| `sft_question.target_label_id` | string | 兼容旧格式的分类标签 ID；新流程通常为空 |
| `sft_question.expected_answer_format` | string | `plain_text` / `bullets` / `table` / `json` |
| `sft_question.difficulty` | string | `easy` / `medium` / `hard` |
| `sft_question.risk_label` | string | 风险标签 |
| `sft_question.reason` | string | 问题生成理由 |
| `sft_question.status` | string | `ok` / `empty_question` / `api_error` / `worker_error` |

注意：

- 问题应尽量对齐真实用户提问。
- 问题不应包含“根据材料”“结合上文”“文中提到”等依赖原文的表达。
- 当前答案生成阶段只把 `sft_question.question` 发给模型。

异常情况：

```json
{
  "sft_question": {
    "question": "",
    "question_type": "refusal",
    "target_label_id": "",
    "expected_answer_format": "plain_text",
    "difficulty": "medium",
    "risk_label": "public_safe",
    "reason": "API问题生成失败：错误信息",
    "status": "api_error"
  }
}
```

## 4. 答案生成数据

典型文件：

```text
labeled_data/*_answers.jsonl
```

来源：问题生成数据。

特点：

- 保留问题生成阶段的所有字段。
- 新增 `sft_answer` 字段。
- 答案生成阶段只把 `sft_question.question` 发给模型，不传原始 `text` 或评分。
- 本阶段还不是最终 SFT 格式，后续可再转换为你需要的 `final_sft_data` 格式。

格式：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00013",
  "text": "分块正文文本",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 13,
  "char_count": 980,
  "sft_material_eval": {
    "score": 8,
    "quality_level": "良好",
    "reason": "评分理由",
    "issues": [],
    "suggested_use": "建议用途"
  },
  "sft_question": {
    "question": "根据《国防法》，公民在国防活动中享有哪些权利？这些权利与民事活动中的损害赔偿有何区别？",
    "question_type": "qa",
    "target_label_id": "",
    "expected_answer_format": "bullets",
    "difficulty": "medium",
    "risk_label": "public_safe",
    "reason": "问题生成理由",
    "status": "ok"
  },
  "sft_answer": {
    "answer": "答案文本",
    "risk_label": "public_safe",
    "quality_notes": "答案生成说明",
    "status": "ok",
    "answer_from_question_only": true,
    "question": "根据《国防法》，公民在国防活动中享有哪些权利？这些权利与民事活动中的损害赔偿有何区别？"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `sft_answer.answer` | string | 生成答案 |
| `sft_answer.risk_label` | string | 答案风险标签 |
| `sft_answer.quality_notes` | string | 答案生成说明 |
| `sft_answer.status` | string | `ok` / `empty_answer` / `api_error` / `worker_error` |
| `sft_answer.answer_from_question_only` | boolean | 固定为 `true`，表示答案只基于问题生成 |
| `sft_answer.question` | string | 实际发送给模型的问题，便于审计 |

异常情况：

```json
{
  "sft_answer": {
    "answer": "",
    "risk_label": "needs_caution",
    "quality_notes": "API答案生成失败：错误信息",
    "status": "api_error",
    "answer_from_question_only": true,
    "question": "实际发送给模型的问题"
  }
}
```

## 5. 阶段之间的字段继承关系

```text
chunk
  基础字段：id, text, source, chunk_index, char_count
  可选来源字段：title, category, section

score
  继承 chunk
  新增 sft_material_eval

questions
  继承 score
  新增 sft_question

answers
  继承 questions
  新增 sft_answer

final_sft
  后续按需要从 answers 转换
```

## 6. 常用枚举值

### 任务类型 `task_type/question_type`

```text
qa
summary
extraction
classification
comparison
reasoning
rewrite
json_generation
critique
refusal
drafting
plan
outline
```

### 风险标签 `risk_label`

```text
public_safe
needs_caution
refuse_or_exclude
```

### 问题状态 `sft_question.status`

```text
ok
empty_question
api_error
worker_error
```

### 答案状态 `sft_answer.status`

```text
ok
empty_answer
api_error
worker_error
```
