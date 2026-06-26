from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from evaluate_sft_material import compact_text, expand_env_vars, extract_json_object, load_done_ids, read_jsonl


SYSTEM_PROMPT = """你是军事领域 SFT 数据构造专家。当前任务不是回答问题，而是参考一段已评估的公开文本材料，生成若干个适合构造军事大模型 SFT 数据的问题。

材料只是“选题灵感”和“知识种子”，不是最终问题的上下文。后续答案生成阶段只能看到 question 字段，看不到 text、质量评估、来源或任何材料内容。因此生成的问题必须能被一个没有读过材料的模型独立回答，必须像真实用户直接提出的问题，而不是阅读理解题。

生成原则：
1. 不要生成依赖材料细节、原文表述、具体段落、隐藏事实的问题。
2. 禁止出现“根据材料”“结合材料”“从材料中”“文中提到”“上述内容”“结合上文”“从材料看”等指代原文的表达。
3. 问题要贴合材料质量评估中的建议用途，体现该材料最有训练价值的能力方向。
4. 允许基于材料主题发散到相关概念解释、原则分析、风险辨析、对比、结构化整理、学习建议、政策影响、边界说明等问题。
5. 对军事、安全、国防材料保持安全边界：不得生成要求攻击实施、武器制造、规避侦察、突破系统、行动步骤等可操作伤害问题。
6. 如果材料风险较高，应生成安全改写、边界说明、风险识别或拒答类问题。
7. 可围绕同一段材料生成多个问题，但每个问题必须关注不同信息点或不同任务能力，避免同义改写凑数。
8. 问题可以是问答、摘要、抽取、对比、解释、结构化整理、非操作性复盘等类型。
9. 问题应使用中文，表述自然，尽量对齐真实用户会问的问题。
10. 不要把多个不相干问题硬拼成一个长问题；如需多点回答，应围绕同一个主题。

只返回一个 JSON 对象，不要输出 Markdown，不要输出多余解释。JSON 字段如下：
{
  "questions": [
    {
      "question": "一个用于构造军事大模型SFT数据的问题",
      "question_type": "qa/summary/extraction/classification/comparison/reasoning/rewrite/json_generation/critique/refusal",
      "target_label_id": "",
      "expected_answer_format": "plain_text/bullets/table/json",
      "difficulty": "easy/medium/hard",
      "risk_label": "public_safe/needs_caution/refuse_or_exclude",
      "reason": "一句话说明为什么这个问题适合该材料"
    }
  ]
}
"""


QUESTION_TYPES = {
    "qa",
    "summary",
    "extraction",
    "classification",
    "comparison",
    "reasoning",
    "rewrite",
    "json_generation",
    "critique",
    "refusal",
}
ANSWER_FORMATS = {"plain_text", "bullets", "table", "json"}
DIFFICULTIES = {"easy", "medium", "hard"}
RISK_LABELS = {"public_safe", "needs_caution", "refuse_or_exclude"}


@dataclass
class QuestionConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    retries: int = 2
    temperature: float = 0.2
    max_output_tokens: int = 1200
    max_input_chars: int = 4500
    sleep: float = 0.0
    extra_body: dict[str, Any] | None = None


class SFTQuestionGenerator:
    def __init__(self, config: QuestionConfig) -> None:
        self.config = config

    @classmethod
    def from_config_file(cls, path: str | Path) -> "SFTQuestionGenerator":
        return cls(load_question_config(Path(path)))

    def generate_questions(self, row: dict[str, Any], question_count: int) -> list[dict[str, Any]]:
        prompt = self._build_user_prompt(row, question_count)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                content = self._chat_completion(messages)
                return normalize_questions(extract_json_object(content), row, question_count)
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                json.JSONDecodeError,
                KeyError,
            ) as exc:
                last_error = exc
                if attempt >= self.config.retries:
                    break
                time.sleep(2**attempt)

        return [
            {
                "question": "",
                "question_type": "refusal",
                "target_label_id": primary_label_id(row),
                "expected_answer_format": "plain_text",
                "difficulty": "medium",
                "risk_label": row_risk_label(row),
                "reason": f"API问题生成失败：{last_error}",
                "status": "api_error",
            }
        ]

    def _build_user_prompt(self, row: dict[str, Any], question_count: int) -> str:
        text = compact_text(str(row.get("text", "")), self.config.max_input_chars)
        eval_result = row.get("sft_material_eval", {})
        return "\n".join(
            [
                f"请基于下面材料生成 {question_count} 个 SFT 训练问题。",
                "如果材料信息不足以支撑这么多高质量问题，可以少生成，但不要重复凑数。",
                "",
                f"样本ID：{row.get('id', '')}",
                f"来源：{row.get('source', '')}",
                f"质量评估：{json.dumps(eval_result, ensure_ascii=False)}",
                "",
                "text：",
                text,
            ]
        )

    def _chat_completion(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        if self.config.extra_body:
            payload.update(self.config.extra_body)

        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
            body = response.read().decode("utf-8")

        result = json.loads(body)
        return result["choices"][0]["message"]["content"]


def load_question_config(path: Path) -> QuestionConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a JSON object.")

    data = {key: expand_env_vars(value) for key, value in raw.items()}
    api_key = data.get("api_key") or os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing API key. Set api_key in config or use SILICONFLOW_API_KEY.")

    extra_body = data.get("extra_body", {})
    if isinstance(extra_body, str):
        extra_body = json.loads(extra_body)
    if not isinstance(extra_body, dict):
        raise ValueError("extra_body must be a JSON object.")

    return QuestionConfig(
        base_url=str(data.get("base_url", "https://api.siliconflow.cn/v1")),
        api_key=str(api_key),
        model=str(data.get("model", "Qwen/Qwen3-8B")),
        timeout=int(data.get("timeout", 60)),
        retries=int(data.get("retries", 2)),
        temperature=float(data.get("temperature", 0.2)),
        max_output_tokens=int(data.get("max_output_tokens", 1200)),
        max_input_chars=int(data.get("max_input_chars", 4500)),
        sleep=float(data.get("sleep", 0.0)),
        extra_body=extra_body,
    )


def primary_label_id(row: dict[str, Any]) -> str:
    labels = row.get("sft_taxonomy_labels")
    if not isinstance(labels, dict):
        return ""
    primary = labels.get("primary")
    if isinstance(primary, dict):
        return str(primary.get("id") or "")
    return ""


def row_risk_label(row: dict[str, Any]) -> str:
    labels = row.get("sft_taxonomy_labels")
    if isinstance(labels, dict):
        risk_label = labels.get("risk_label")
        if risk_label in RISK_LABELS:
            return str(risk_label)
    return "public_safe"


def normalize_questions(raw: dict[str, Any], row: dict[str, Any], question_count: int) -> list[dict[str, Any]]:
    raw_questions = raw.get("questions")
    if not isinstance(raw_questions, list):
        raw_questions = [raw] if raw.get("question") else []

    normalized: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question = normalize_question(item, row)
        dedupe_key = question["question"]
        if not dedupe_key or dedupe_key in seen_questions:
            continue
        seen_questions.add(dedupe_key)
        normalized.append(question)
        if len(normalized) >= question_count:
            break

    if normalized:
        return normalized

    return [
        {
            "question": "",
            "question_type": "refusal",
            "target_label_id": primary_label_id(row),
            "expected_answer_format": "plain_text",
            "difficulty": "medium",
            "risk_label": row_risk_label(row),
            "reason": "模型未返回可用问题",
            "status": "empty_question",
        }
    ]


def normalize_question(raw: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    question = clean_question(str(raw.get("question") or ""))

    question_type = str(raw.get("question_type") or "qa").strip()
    if question_type not in QUESTION_TYPES:
        question_type = "qa"

    answer_format = str(raw.get("expected_answer_format") or "plain_text").strip()
    if answer_format not in ANSWER_FORMATS:
        answer_format = "plain_text"

    difficulty = str(raw.get("difficulty") or "medium").strip()
    if difficulty not in DIFFICULTIES:
        difficulty = "medium"

    risk_label = str(raw.get("risk_label") or row_risk_label(row)).strip()
    if risk_label not in RISK_LABELS:
        risk_label = row_risk_label(row)

    return {
        "question": question,
        "question_type": question_type,
        "target_label_id": str(raw.get("target_label_id") or primary_label_id(row)),
        "expected_answer_format": answer_format,
        "difficulty": difficulty,
        "risk_label": risk_label,
        "reason": str(raw.get("reason") or "").strip(),
        "status": "ok" if question else "empty_question",
    }


def clean_question(question: str) -> str:
    question = question.strip()
    prefixes = [
        "根据材料：",
        "根据材料,",
        "根据材料，",
        "结合材料：",
        "结合材料,",
        "结合材料，",
        "根据上述材料：",
        "根据上述材料,",
        "根据上述材料，",
        "结合上文：",
        "结合上文,",
        "结合上文，",
        "从材料看：",
        "从材料看,",
        "从材料看，",
        "文中提到：",
        "文中提到,",
        "文中提到，",
        "请根据材料",
        "请结合材料",
    ]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if question.startswith(prefix):
                question = question[len(prefix) :].lstrip(" ：:,，")
                changed = True
    return question


def eval_score(row: dict[str, Any]) -> int:
    result = row.get("sft_material_eval")
    if not isinstance(result, dict):
        return 0
    try:
        return int(result.get("score", 0))
    except (TypeError, ValueError):
        return 0


def char_count(row: dict[str, Any]) -> int:
    try:
        return int(row.get("char_count") or len(str(row.get("text") or "")))
    except (TypeError, ValueError):
        return len(str(row.get("text") or ""))


def suggested_question_count(row: dict[str, Any], max_questions: int) -> int:
    if max_questions <= 1 or row_risk_label(row) == "refuse_or_exclude":
        return 1

    score = eval_score(row)
    size = char_count(row)
    count = 1
    if score >= 8 and size >= 600:
        count += 1
    if score >= 9 or size >= 1000:
        count += 1

    return max(1, min(max_questions, count))


def expanded_row_id(row: dict[str, Any], question_index: int) -> str:
    base_id = str(row.get("id") or "").strip()
    if not base_id:
        base_id = "unknown"
    return f"{base_id}#q{question_index:04d}"


def all_questions_done(row: dict[str, Any], done_ids: set[str], max_questions: int) -> bool:
    question_count = suggested_question_count(row, max_questions)
    return all(expanded_row_id(row, index) in done_ids for index in range(1, question_count + 1))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one or more SFT construction questions for each scored material JSONL row."
    )
    parser.add_argument("--input", required=True, help="Input scored JSONL file, usually under labeled_data.")
    parser.add_argument("--output", required=True, help="Output question JSONL file, recommended under labeled_data.")
    parser.add_argument("--config", default="configs/question.json", help="API config JSON file.")
    parser.add_argument("--limit", type=int, default=0, help="Generate at most N material rows. 0 means all.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent API request workers.")
    parser.add_argument("--skip-done", action="store_true", help="Skip question rows already present in output.")
    parser.add_argument("--min-score", type=int, default=7, help="Only generate questions for rows at least this score.")
    parser.add_argument(
        "--max-questions",
        type=int,
        default=3,
        help="Generate at most N questions for each material row.",
    )
    parser.add_argument(
        "--include-refuse-risk",
        action="store_true",
        help="Also process rows marked refuse_or_exclude in legacy taxonomy labels. By default they are skipped.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if args.workers <= 0:
        raise ValueError("--workers must be greater than 0")
    if args.max_questions <= 0:
        raise ValueError("--max-questions must be greater than 0")

    rows = read_jsonl(input_path)
    rows = [row for row in rows if eval_score(row) >= args.min_score]
    if not args.include_refuse_risk:
        rows = [row for row in rows if row_risk_label(row) != "refuse_or_exclude"]

    done_ids: set[str] = set()
    if args.skip_done:
        done_ids = load_done_ids(output_path)
        rows = [row for row in rows if not all_questions_done(row, done_ids, args.max_questions)]

    if args.limit > 0:
        rows = rows[: args.limit]

    generator = SFTQuestionGenerator.from_config_file(args.config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.skip_done else "w"

    def generate_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
        material_id = str(row.get("id") or "")
        question_count = suggested_question_count(row, args.max_questions)
        results = generator.generate_questions(row, question_count)
        output_rows: list[dict[str, Any]] = []

        for question_index, result in enumerate(results, start=1):
            output_id = expanded_row_id(row, question_index)
            if args.skip_done and output_id in done_ids:
                continue

            output_row = dict(row)
            output_row.pop("headings", None)
            output_row["id"] = output_id
            output_row["material_id"] = material_id
            output_row["question_index"] = question_index
            output_row["question_count"] = len(results)
            output_row["sft_question"] = result
            output_rows.append(output_row)

        if generator.config.sleep > 0:
            time.sleep(generator.config.sleep)
        return output_rows

    written_count = 0
    with output_path.open(mode, encoding="utf-8", newline="\n") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_row = {executor.submit(generate_rows, row): row for row in rows}
            iterator = as_completed(future_to_row)
            if tqdm is not None:
                iterator = tqdm(iterator, total=len(rows), desc="Questions", unit="item")

            for index, future in enumerate(iterator, start=1):
                row = future_to_row[future]
                try:
                    output_rows = future.result()
                except Exception as exc:
                    material_id = str(row.get("id") or "")
                    output_row = dict(row)
                    output_row.pop("headings", None)
                    output_row["id"] = expanded_row_id(row, 1)
                    output_row["material_id"] = material_id
                    output_row["question_index"] = 1
                    output_row["question_count"] = 1
                    output_row["sft_question"] = {
                        "question": "",
                        "question_type": "refusal",
                        "target_label_id": primary_label_id(row),
                        "expected_answer_format": "plain_text",
                        "difficulty": "medium",
                        "risk_label": row_risk_label(row),
                        "reason": f"并发任务失败：{exc}",
                        "status": "worker_error",
                    }
                    output_rows = [output_row]

                for output_row in output_rows:
                    f.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                    written_count += 1
                f.flush()

                if output_rows:
                    result = output_rows[-1]["sft_question"]
                    if tqdm is not None and hasattr(iterator, "set_postfix"):
                        iterator.set_postfix(rows=written_count, qtype=result["question_type"], status=result["status"])
                    else:
                        print(
                            f"[{index}/{len(rows)}] wrote={len(output_rows)} "
                            f"type={result['question_type']} status={result['status']}"
                        )

    print(f"Processed materials: {len(rows)}")
    print(f"Generated question rows: {written_count}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
