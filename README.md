# SFT 数据构建流程

本仓库用于把原始军事领域公开文本构造成 SFT 训练样本。主流程是：

```text
raw_data
  -> chunk_data
  -> labeled_data/*_scores.jsonl
  -> labeled_data/*_classified.jsonl
  -> labeled_data/*_questions.jsonl
  -> labeled_data/*_answers.jsonl
  -> final_sft_data/*_sft_samples.jsonl
```

所有主数据文件均采用 JSONL 格式：一行一个 JSON 对象。后续阶段通常保留前一阶段字段，并追加本阶段产生的新字段。

## 目录说明

- `raw_data/`：原始数据，包括 PDF、Markdown、TXT 等来源文件。
- `chunk_data/`：从原始数据切分得到的文本块，以及对应统计文件。
- `labeled_data/`：模型辅助标注结果，包括材料评分、分类、问题和答案。
- `final_sft_data/`：最终可用于训练的 instruction/input/output 样本。
- `configs/`：各阶段 API 配置和能力分类目录。
- `scripts/`：数据切分、评分、分类、出题、答题脚本。

## 1. 原始数据到 chunk_data

### Markdown/PDF 来源切块

Markdown 数据通常来自 `raw_data/md_from_pdf/*.md`，由 `scripts/chunk_md.py` 切分。输出示例文件：

```text
chunk_data/md_paragraph_chunks.jsonl
```

单行 JSON 示例：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "text": "中国国防有着悠久的历史。夏、商、西周至春秋战国，是中国古代国防形成与发展时期...",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 3,
  "char_count": 910
}
```

字段含义：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 文本块唯一 ID，通常是 `source#序号` |
| `text` | string | 切分后的正文文本 |
| `source` | string | 原始文件相对路径 |
| `chunk_index` | number | 当前来源文件内的块序号 |
| `char_count` | number | 去除空白后的字符数 |

说明：`scripts/chunk_md.py` 会利用 Markdown 标题辅助判断切分上下文，但当前标准输出字段不包含 `headings`。如果历史数据中存在该字段，后续出题和答题脚本也会在写出时移除它。

配套统计文件示例：

```json
{
  "chunk_count": 206,
  "min_chars": 99,
  "max_chars": 1670,
  "avg_chars": 1014.66,
  "sources": ["md_from_pdf/MinerU_markdown_军事理论教程.md"]
}
```

### TXT 来源切块

TXT 数据来自 `raw_data/txt/`，由 `scripts/chunk_txt.py` 按段落、章节或发言轮次进行结构化切分。输出字段与 Markdown 切块保持一致。输出示例文件：

```text
chunk_data/txt_structured_chunks.jsonl
```

单行 JSON 示例：

```json
{
  "id": "00_white_papers/《中国军队参加联合国维和行动30年》白皮书.txt#00001",
  "text": "国务院新闻办公室18日发布《中国军队参加联合国维和行动30年》白皮书。全文如下：...",
  "source": "00_white_papers/《中国军队参加联合国维和行动30年》白皮书.txt",
  "chunk_index": 1,
  "char_count": 809
}
```

字段含义与 Markdown 切块一致，只包含 `id`、`text`、`source`、`chunk_index`、`char_count`。

## 2. 材料评分

评分阶段输入 `chunk_data/*.jsonl`，输出到：

```text
labeled_data/*_scores.jsonl
```

运行示例：

```powershell
python scripts\evaluate_sft_material.py `
  --input chunk_data\md_paragraph_chunks.jsonl `
  --output labeled_data\md_sft_material_scores.jsonl `
  --config configs\eval.json
```

本阶段追加 `sft_material_eval` 字段：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "text": "中国国防有着悠久的历史...",
  "source": "md_from_pdf/MinerU_markdown_军事理论教程.md",
  "chunk_index": 3,
  "char_count": 910,
  "sft_material_eval": {
    "score": 7,
    "quality_level": "良好",
    "reason": "内容涉及中国古代和近代国防历史、政策、兵制和工程建设，具有一定的军事相关性。",
    "issues": ["部分文本存在排版问题", "信息密度一般"],
    "suggested_use": "可用于构造关于中国古代国防历史、政策、兵制和工程建设的问答样本。"
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

## 3. 能力分类

分类阶段读取评分结果，并结合：

```text
configs/military_sft_taxonomy_compact.json
```

输出到：

```text
labeled_data/*_classified.jsonl
```

运行示例：

```powershell
python scripts\classify_sft_material.py `
  --input labeled_data\md_sft_material_scores.jsonl `
  --output labeled_data\md_sft_material_classified.jsonl `
  --config configs\classify.json `
  --taxonomy configs\military_sft_taxonomy_compact.json `
  --min-score 7
```

本阶段追加 `sft_taxonomy_labels` 等字段：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "sft_material_eval": {
    "score": 7,
    "quality_level": "良好"
  },
  "sft_taxonomy_labels": {
    "primary": {
      "side": "friendly",
      "side_name": "我方",
      "l1": "我方军事知识与制度",
      "l2": "主要案例",
      "leaf": "案例启示生成",
      "path": ["我方", "我方军事知识与制度", "主要案例", "案例启示生成"],
      "source_file": "friendly/03-我方军事知识与制度.md",
      "id": "F0143"
    },
    "secondary": [
      {
        "side": "friendly",
        "side_name": "我方",
        "l1": "我方军事知识与制度",
        "l2": "主要案例",
        "leaf": "战例要素抽取",
        "id": "F0139"
      }
    ],
    "task_types": ["qa", "summary", "extraction", "comparison", "reasoning"],
    "source_type": "textbook",
    "risk_label": "public_safe",
    "confidence": 0.95,
    "reason": "文本内容聚焦于中国国防历史与启示，适合生成案例启示类样本。",
    "evidence_keywords": ["中国国防历史", "启示", "兵制建设"],
    "candidate_label_ids": ["F0143", "F0139", "F0144"],
    "status": "ok"
  }
}
```

核心字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `primary` | object | 主能力标签 |
| `secondary` | array[object] | 次级候选标签 |
| `task_types` | array[string] | 适合生成的任务类型 |
| `source_type` | string | 来源类型，如 `textbook`、`policy` |
| `risk_label` | string | 安全风险标签 |
| `confidence` | number | 分类置信度 |
| `candidate_label_ids` | array[string] | 召回或候选标签 ID |
| `status` | string | 分类状态 |

## 4. 生成 SFT 问题

问题生成阶段读取分类结果，输出到：

```text
labeled_data/*_questions.jsonl
```

运行示例：

```powershell
python scripts\generate_sft_questions.py `
  --input labeled_data\md_sft_material_classified.jsonl `
  --output labeled_data\md_sft_questions.jsonl `
  --config configs\question.json `
  --min-score 7
```

本阶段追加 `sft_question` 字段：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "sft_taxonomy_labels": {
    "primary": {
      "id": "F0143",
      "leaf": "案例启示生成"
    }
  },
  "sft_question": {
    "question": "中国古代国防历史的主要特点和启示有哪些？",
    "question_type": "reasoning",
    "target_label_id": "F0143",
    "expected_answer_format": "plain_text",
    "difficulty": "medium",
    "risk_label": "public_safe",
    "reason": "该问题聚焦于材料中关于中国古代国防历史与启示的内容。",
    "status": "ok"
  }
}
```

核心字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `question` | string | 生成的问题 |
| `question_type` | string | 问题类型，如 `qa`、`summary`、`reasoning` |
| `target_label_id` | string | 对齐的能力标签 ID |
| `expected_answer_format` | string | 期望答案格式 |
| `difficulty` | string | 难度 |
| `risk_label` | string | 安全风险标签 |
| `status` | string | 生成状态 |

## 5. 生成 SFT 答案

答案生成阶段读取问题结果，输出到：

```text
labeled_data/*_answers.jsonl
```

运行示例：

```powershell
python scripts\generate_sft_answers.py `
  --input labeled_data\md_sft_questions.jsonl `
  --output labeled_data\md_sft_answers.jsonl `
  --config configs\answer.json
```

本阶段追加 `sft_answer` 字段：

```json
{
  "id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "sft_question": {
    "question": "中国古代国防历史的主要特点和启示有哪些？",
    "question_type": "reasoning",
    "target_label_id": "F0143"
  },
  "sft_answer": {
    "answer": "中国古代国防历史的主要特点包括重视边防、强调以民为本、注重军事与政治的结合、发展多样化的防御体系以及传承和发扬军事文化。",
    "risk_label": "public_safe",
    "quality_notes": "答案基于通用知识，结构清晰，内容准确且符合安全规范。",
    "status": "ok",
    "answer_from_question_only": true,
    "question": "中国古代国防历史的主要特点和启示有哪些？"
  }
}
```

说明：当前答题脚本只基于问题本身生成答案，不读取原始 `text`，因此 `answer_from_question_only` 为 `true`。

## 6. 最终 SFT 样本

最终样本位于：

```text
final_sft_data/*_sft_samples.jsonl
```

单行 JSON 示例：

```json
{
  "sample_id": "mil-sft-00000001",
  "source_id": "md_from_pdf/MinerU_markdown_军事理论教程.md#00003",
  "side": "friendly",
  "category_path": {
    "l1": "我方军事知识与制度",
    "l2": "主要案例",
    "leaf": "案例启示生成",
    "label_id": "F0143"
  },
  "task_type": "reasoning",
  "source_type": "textbook",
  "instruction": "中国古代国防历史的主要特点和启示有哪些？",
  "input": "",
  "output": "中国古代国防历史的主要特点包括重视边防、强调以民为本、注重军事与政治的结合、发展多样化的防御体系以及传承和发扬军事文化。",
  "output_format": "plain_text",
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
    "quality_notes": "答案基于通用知识，结构清晰，内容准确且符合安全规范。"
  }
}
```

最终训练字段主要是：

| 字段 | 类型 | 说明 |
|---|---|---|
| `instruction` | string | 用户指令或问题 |
| `input` | string | 额外输入；当前样例通常为空 |
| `output` | string | 目标答案 |
| `category_path` | object | 能力分类路径 |
| `task_type` | string | 任务类型 |
| `risk_label` | string | 样本风险标签 |
| `judge_decision` | string | 样本保留决策，如 `keep` |
| `generation` | object | 答案生成元信息 |

## 快速运行

单阶段运行可以按上文命令逐步执行。若只想跑 200 条端到端测试：

```bash
bash scripts/run_full_sft_test.sh
```

该脚本会依次生成：

```text
labeled_data/full_test_200_scores.jsonl
labeled_data/full_test_200_classified.jsonl
labeled_data/full_test_200_questions.jsonl
labeled_data/full_test_200_answers.jsonl
```

## 质量与筛选建议

- 优先使用 `sft_material_eval.score >= 7` 的材料进入分类和出题阶段。
- 优先保留 `risk_label = public_safe` 且 `status = ok` 的问题和答案。
- 对 `needs_caution` 或 `refuse_or_exclude` 样本应人工复核，必要时剔除。
- 进入 `final_sft_data` 前，建议检查 `instruction` 是否清晰、`output` 是否回答了问题、分类标签是否与任务一致。
