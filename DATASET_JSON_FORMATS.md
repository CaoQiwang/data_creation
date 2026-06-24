# 数据集各阶段 JSON 格式

本文档按当前 SFT 数据构造流水线整理各阶段 JSONL 的字段格式。

整体流程：

```text
raw_data
  -> chunk_data
  -> labeled_data/*_scores.jsonl
  -> labeled_data/*_classified.jsonl
  -> labeled_data/*_questions.jsonl
  -> labeled_data/*_answers.jsonl
```

说明：

- 所有主数据文件都是 JSONL：一行一个 JSON 对象。
- 后一阶段通常保留前一阶段字段，并新增本阶段字段。
- 答案生成阶段仍是中间数据，会保留前序字段并新增 `sft_answer`。
- 最终 `final_sft_data` 的转换格式后续再定义。

## 0. 分类目录

文件：

```text
configs/military_sft_taxonomy_compact.json
```

用途：把 `military_sft_taxonomy/` 下的 markdown 分类目录汇总成机器可读标签表，供分类阶段召回候选标签。

格式：

```json
{
  "version": "0.1",
  "description": "军事大模型SFT能力分类目录的紧凑机器可读版本，用于对评估后的文本块贴能力标签。",
  "source_root": "D:\\czc\\work\\sft_data\\military_sft_taxonomy",
  "source_files": [
    "friendly/01-我方军事实体认知.md"
  ],
  "missing_from_catalog": [
    "opponent/01-他方军事实体认知.md"
  ],
  "label_count": 944,
  "labels": [
    {
      "id": "F0001",
      "side": "friendly",
      "side_name": "我方",
      "l1": "我方军事实体认知",
      "l2": "物资器材",
      "leaf": "单兵携行物资识别",
      "path": [
        "我方",
        "我方军事实体认知",
        "物资器材",
        "单兵携行物资识别"
      ],
      "source_file": "friendly/01-我方军事实体认知.md"
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `version` | string | 分类目录版本 |
| `description` | string | 文件说明 |
| `source_root` | string | 原始分类 markdown 根目录 |
| `source_files` | array[string] | 已纳入汇总的分类文件 |
| `missing_from_catalog` | array[string] | 目录引用但本地缺失的文件 |
| `label_count` | number | 标签总数 |
| `labels` | array[object] | 标签列表 |
| `labels[].id` | string | 标签 ID，`F` 表示我方，`O` 表示他方 |
| `labels[].side` | string | `friendly` / `opponent` |
| `labels[].side_name` | string | 中文侧别 |
| `labels[].l1` | string | 一级能力域 |
| `labels[].l2` | string | 二级能力域 |
| `labels[].leaf` | string | 叶子能力项 |
| `labels[].path` | array[string] | 中文完整路径 |
| `labels[].source_file` | string | 来源分类文件 |

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
    "score": 9,
    "quality_level": "优秀",
    "reason": "内容紧扣国防政策、战略类型等军事领域核心主题，信息完整且结构清晰，具有较高的训练价值。",
    "issues": [],
    "suggested_use": "适合用于构造关于国防政策、国防类型、军事战略等的高质量SFT问答样本。"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `sft_material_eval.score` | number | 0-10 分质量评分 |
| `sft_material_eval.quality_level` | string | `不可用` / `较差` / `可用` / `良好` / `优秀` |
| `sft_material_eval.reason` | string | 评分理由 |
| `sft_material_eval.issues` | array[string] | 主要问题 |
| `sft_material_eval.suggested_use` | string | 建议用于何种 SFT 构造 |

异常情况：

```json
{
  "sft_material_eval": {
    "score": 0,
    "quality_level": "不可用",
    "reason": "API评估失败：错误信息",
    "issues": [
      "api_error"
    ],
    "suggested_use": "不建议使用，需重新评估"
  }
}
```

## 3. 分类标签数据

典型文件：

```text
labeled_data/*_classified.jsonl
```

来源：评分数据。

新增字段：

```text
sft_taxonomy_labels
```

格式：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00001",
  "text": "分块正文文本",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 1,
  "char_count": 976,
  "sft_material_eval": {
    "score": 9,
    "quality_level": "优秀",
    "reason": "评分理由",
    "issues": [],
    "suggested_use": "建议用途"
  },
  "sft_taxonomy_labels": {
    "primary": {
      "id": "F0120",
      "side": "friendly",
      "side_name": "我方",
      "l1": "我方军事知识与制度",
      "l2": "军事法规",
      "leaf": "法规问答生成",
      "path": [
        "我方",
        "我方军事知识与制度",
        "军事法规",
        "法规问答生成"
      ],
      "source_file": "friendly/03-我方军事知识与制度.md"
    },
    "task_types": [
      "qa",
      "summary",
      "extraction"
    ],
    "source_type": "policy_document",
    "risk_label": "public_safe",
    "confidence": 0.95,
    "reason": "分类依据说明",
    "evidence_keywords": [
      "国防法",
      "宪法"
    ],
    "candidate_label_ids": [
      "F0120",
      "F0118"
    ],
    "status": "ok"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `sft_taxonomy_labels.primary` | object/null | 主标签；找不到合适分类时为 `null` |
| `sft_taxonomy_labels.task_types` | array[string] | 推荐任务类型 |
| `sft_taxonomy_labels.source_type` | string | 来源类型 |
| `sft_taxonomy_labels.risk_label` | string | `public_safe` / `needs_caution` / `refuse_or_exclude` |
| `sft_taxonomy_labels.confidence` | number | 分类置信度，0-1 |
| `sft_taxonomy_labels.reason` | string | 分类理由 |
| `sft_taxonomy_labels.evidence_keywords` | array[string] | 证据关键词 |
| `sft_taxonomy_labels.candidate_label_ids` | array[string] | 本次给模型的候选标签 ID |
| `sft_taxonomy_labels.status` | string | `ok` / `no_primary_label` / `api_error` / `worker_error` |

找不到合适分类时：

```json
{
  "sft_taxonomy_labels": {
    "primary": null,
    "task_types": [],
    "source_type": "other",
    "risk_label": "needs_caution",
    "confidence": 0.3,
    "reason": "其他：现有分类无法准确覆盖该文本",
    "evidence_keywords": [],
    "candidate_label_ids": [
      "F0001"
    ],
    "status": "no_primary_label"
  }
}
```

API 失败时：

```json
{
  "sft_taxonomy_labels": {
    "primary": null,
    "task_types": [],
    "source_type": "other",
    "risk_label": "needs_caution",
    "confidence": 0.0,
    "reason": "API分类失败：错误信息",
    "evidence_keywords": [],
    "candidate_label_ids": [
      "F0001"
    ],
    "status": "api_error"
  }
}
```

## 4. 问题生成数据

典型文件：

```text
labeled_data/*_questions.jsonl
```

来源：分类标签数据。

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
    "score": 7,
    "quality_level": "良好",
    "reason": "评分理由",
    "issues": [],
    "suggested_use": "建议用途"
  },
  "sft_taxonomy_labels": {
    "primary": {
      "id": "F0143",
      "side": "friendly",
      "side_name": "我方",
      "l1": "我方军事知识与制度",
      "l2": "主要案例",
      "leaf": "案例启示生成",
      "path": [
        "我方",
        "我方军事知识与制度",
        "主要案例",
        "案例启示生成"
      ],
      "source_file": "friendly/03-我方军事知识与制度.md"
    },
    "task_types": [
      "qa",
      "summary"
    ],
    "source_type": "textbook",
    "risk_label": "public_safe",
    "confidence": 0.95,
    "reason": "分类理由",
    "evidence_keywords": [],
    "candidate_label_ids": [],
    "status": "ok"
  },
  "sft_question": {
    "question": "中国近代国防历史中，抗日战争胜利的主要原因有哪些？",
    "question_type": "summary",
    "target_label_id": "F0143",
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
| `sft_question.question` | string | 生成的问题，也是最终 SFT 的 `instruction` |
| `sft_question.question_type` | string | `qa` / `summary` / `extraction` / `classification` / `comparison` / `reasoning` / `rewrite` / `json_generation` / `critique` / `refusal` |
| `sft_question.target_label_id` | string | 目标分类标签 ID |
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
    "target_label_id": "F0143",
    "expected_answer_format": "plain_text",
    "difficulty": "medium",
    "risk_label": "public_safe",
    "reason": "API问题生成失败：错误信息",
    "status": "api_error"
  }
}
```

## 5. 答案生成数据

典型文件：

```text
labeled_data/*_answers.jsonl
```

来源：问题生成数据。

特点：

- 保留问题生成阶段的所有字段。
- 新增 `sft_answer` 字段。
- 答案生成阶段只把 `sft_question.question` 发给模型，不传原始 `text`、分类或评分。
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
  "sft_taxonomy_labels": {
    "primary": {
      "id": "F0119",
      "side": "friendly",
      "side_name": "我方",
      "l1": "我方军事知识与制度",
      "l2": "军事法规",
      "leaf": "法规适用条件判断",
      "path": [
        "我方",
        "我方军事知识与制度",
        "军事法规",
        "法规适用条件判断"
      ],
      "source_file": "friendly/03-我方军事知识与制度.md"
    },
    "task_types": [
      "qa"
    ],
    "source_type": "policy_document",
    "risk_label": "public_safe",
    "confidence": 0.95,
    "reason": "分类理由",
    "evidence_keywords": [],
    "candidate_label_ids": [],
    "status": "ok"
  },
  "sft_question": {
    "question": "根据《国防法》，公民在国防活动中享有哪些权利？这些权利与民事活动中的损害赔偿有何区别？",
    "question_type": "qa",
    "target_label_id": "F0119",
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

## 6. 阶段之间的字段继承关系

```text
chunk
  基础字段：id, text, source, chunk_index, char_count
  可选来源字段：title, category, section

score
  继承 chunk
  新增 sft_material_eval

classified
  继承 score
  新增 sft_taxonomy_labels

questions
  继承 classified
  新增 sft_question

answers
  继承 questions
  新增 sft_answer

final_sft
  后续按需要从 answers 转换
```

## 7. 常用枚举值

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
```

### 风险标签 `risk_label`

```text
public_safe
needs_caution
refuse_or_exclude
```

### 来源类型 `source_type`

```text
textbook
law_regulation
policy_document
press_conference
news_report
white_paper
open_report
other
```

### 分类状态 `sft_taxonomy_labels.status`

```text
ok
no_primary_label
api_error
worker_error
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
