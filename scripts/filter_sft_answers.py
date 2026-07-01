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

from evaluate_sft_material import expand_env_vars, extract_json_object, load_done_ids, read_jsonl


SYSTEM_PROMPT = """你是军事领域 SFT 数据构造流程中的“问答对质量过滤”评估专家。
你的任务是评估一个完整的 question-answer 样本是否适合作为 SFT 训练数据。

评分核心：
这个问答对是否可以直接作为 instruction/output 训练样本，帮助模型学习准确、稳健、结构清晰且安全的回答方式？

评分范围为 0-10 分，必须是整数：
0-2 分：不可用。问题或答案为空、答案明显不回答问题、乱码、严重事实错误、危险指导、错误拒答，或无法作为训练样本。
3-4 分：较差。答案泛泛而谈、偏题、结构混乱、缺少关键约束、安全处理不当，训练价值较低。
5-6 分：可用但一般。基本回答了问题，但深度、准确性、结构或边界说明一般，适合保留到低优先级数据。
7-8 分：良好。问答匹配，答案清楚、稳健、有结构，能作为较好的 SFT 训练样本。
9-10 分：优秀。答案准确、完整、层次清楚、边界稳健，安全处理恰当，具有较高训练价值。

重点检查：
1. 对题性：答案必须直接回应问题，不能只复述问题、转移主题或空泛表态。
2. 独立性：答案不能声称“根据材料/文中/上文”，因为最终样本只有 question 和 answer。
3. 准确性与稳健性：公开知识、政策法规、历史事实、概念解释应避免明显错误和过度确定。
4. 结构与可读性：答案应自然、清楚，必要时分点；不能堆砌、重复、病句严重。
5. 安全边界：对攻击实施、武器制造、规避侦察、突破系统、行动步骤等可操作伤害问题，应安全拒答或转向原则性、合规性、风险识别说明。安全拒答类样本如果处理得当，可以通过。
6. 训练价值：优先保留能训练解释、归纳、对比、分类、政策解读、风险辨析、结构化整理能力的问答对。

只返回一个 JSON 对象，不要输出 Markdown，不要输出多余解释。JSON 字段为：
{
  "score": 0-10 的整数,
  "pass_filter": true 或 false,
  "quality_level": "不可用/较差/可用/良好/优秀",
  "reason": "一句话说明评分和是否通过的主要原因",
  "issues": ["主要问题1", "主要问题2"],
  "suggested_action": "keep/rewrite/drop",
  "answer_issue_type": "none/off_topic/too_generic/factual_risk/unsafe/over_refusal/format_noise/empty",
  "risk_label": "public_safe/needs_caution/refuse_or_exclude"
}
"""


DEPENDENT_CONTEXT_PATTERNS = [
    "根据材料",
    "结合材料",
    "从材料中",
    "材料中",
    "文中提到",
    "上述内容",
    "结合上文",
    "从上文",
    "根据上文",
    "这段文字",
    "该材料",
]

RISK_LABELS = {"public_safe", "needs_caution", "refuse_or_exclude"}
ANSWER_ISSUE_TYPES = {
    "none",
    "off_topic",
    "too_generic",
    "factual_risk",
    "unsafe",
    "over_refusal",
    "format_noise",
    "empty",
}


@dataclass
class AnswerFilterConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    retries: int = 2
    temperature: float = 0.0
    max_output_tokens: int = 700
    sleep: float = 0.0
    extra_body: dict[str, Any] | None = None


class SFTAnswerFilter:
    def __init__(self, config: AnswerFilterConfig, pass_score: int) -> None:
        self.config = config
        self.pass_score = pass_score

    @classmethod
    def from_config_file(cls, path: str | Path, pass_score: int) -> "SFTAnswerFilter":
        return cls(load_answer_filter_config(Path(path)), pass_score)

    def evaluate_pair(self, row: dict[str, Any]) -> dict[str, Any]:
        heuristic_result = heuristic_reject(question_text(row), answer_text(row))
        if heuristic_result is not None:
            return normalize_answer_eval(heuristic_result, self.pass_score)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_user_prompt(row)},
        ]

        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                content = self._chat_completion(messages)
                return normalize_answer_eval(extract_json_object(content), self.pass_score)
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

        return {
            "score": 0,
            "pass_filter": False,
            "quality_level": "不可用",
            "reason": f"API问答对评分失败：{last_error}",
            "issues": ["api_error"],
            "suggested_action": "drop",
            "answer_issue_type": "empty",
            "risk_label": pair_risk_label(row),
            "status": "api_error",
        }

    def _build_user_prompt(self, row: dict[str, Any]) -> str:
        eval_context = {
            "question": question_text(row),
            "answer": answer_text(row),
            "question_meta": {
                "question_type": sft_question(row).get("question_type", ""),
                "expected_answer_format": sft_question(row).get("expected_answer_format", ""),
                "difficulty": sft_question(row).get("difficulty", ""),
                "risk_label": sft_question(row).get("risk_label", ""),
            },
            "answer_meta": {
                "risk_label": sft_answer(row).get("risk_label", ""),
                "quality_notes": sft_answer(row).get("quality_notes", ""),
                "status": sft_answer(row).get("status", ""),
            },
            "question_eval": row.get("sft_question_eval", {}),
        }
        return "请评估下面这个问答对是否适合作为 SFT 训练数据：\n\n" + json.dumps(
            eval_context, ensure_ascii=False
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


def load_answer_filter_config(path: Path) -> AnswerFilterConfig:
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

    return AnswerFilterConfig(
        base_url=str(data.get("base_url", "https://api.siliconflow.cn/v1")),
        api_key=str(api_key),
        model=str(data.get("model", "Qwen/Qwen3-8B")),
        timeout=int(data.get("timeout", 60)),
        retries=int(data.get("retries", 2)),
        temperature=float(data.get("temperature", 0.0)),
        max_output_tokens=int(data.get("max_output_tokens", 700)),
        sleep=float(data.get("sleep", 0.0)),
        extra_body=extra_body,
    )


def sft_question(row: dict[str, Any]) -> dict[str, Any]:
    question = row.get("sft_question")
    if isinstance(question, dict):
        return question
    return {}


def sft_answer(row: dict[str, Any]) -> dict[str, Any]:
    answer = row.get("sft_answer")
    if isinstance(answer, dict):
        return answer
    return {}


def question_text(row: dict[str, Any]) -> str:
    return str(sft_question(row).get("question") or "").strip()


def answer_text(row: dict[str, Any]) -> str:
    return str(sft_answer(row).get("answer") or "").strip()


def pair_risk_label(row: dict[str, Any]) -> str:
    answer_risk = str(sft_answer(row).get("risk_label") or "").strip()
    question_risk = str(sft_question(row).get("risk_label") or "").strip()
    if answer_risk in RISK_LABELS:
        return answer_risk
    if question_risk in RISK_LABELS:
        return question_risk
    return "public_safe"


def heuristic_reject(question: str, answer: str) -> dict[str, Any] | None:
    if not question:
        return {
            "score": 0,
            "pass_filter": False,
            "quality_level": "不可用",
            "reason": "问题为空，不能构成 SFT 训练样本。",
            "issues": ["empty_question"],
            "suggested_action": "drop",
            "answer_issue_type": "empty",
            "risk_label": "public_safe",
        }

    if not answer:
        return {
            "score": 0,
            "pass_filter": False,
            "quality_level": "不可用",
            "reason": "答案为空，不能构成 SFT 训练样本。",
            "issues": ["empty_answer"],
            "suggested_action": "drop",
            "answer_issue_type": "empty",
            "risk_label": "public_safe",
        }

    if any(pattern in answer for pattern in DEPENDENT_CONTEXT_PATTERNS):
        return {
            "score": 3,
            "pass_filter": False,
            "quality_level": "较差",
            "reason": "答案依赖原始材料或上文，不适合作为独立 SFT 样本。",
            "issues": ["answer_depends_on_source_context"],
            "suggested_action": "rewrite",
            "answer_issue_type": "format_noise",
            "risk_label": "public_safe",
        }

    if len(answer) < 20:
        return {
            "score": 3,
            "pass_filter": False,
            "quality_level": "较差",
            "reason": "答案过短，信息量不足，训练价值较低。",
            "issues": ["answer_too_short"],
            "suggested_action": "rewrite",
            "answer_issue_type": "too_generic",
            "risk_label": "public_safe",
        }

    return None


def normalize_answer_eval(raw: dict[str, Any], pass_score: int) -> dict[str, Any]:
    score = raw.get("score", 0)
    try:
        score = int(round(float(score)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(10, score))

    if score <= 2:
        level = "不可用"
    elif score <= 4:
        level = "较差"
    elif score <= 6:
        level = "可用"
    elif score <= 8:
        level = "良好"
    else:
        level = "优秀"

    issues = raw.get("issues", [])
    if isinstance(issues, str):
        issues = [issues]
    if not isinstance(issues, list):
        issues = []

    risk_label = str(raw.get("risk_label") or "public_safe").strip()
    if risk_label not in RISK_LABELS:
        risk_label = "needs_caution"

    suggested_action = str(raw.get("suggested_action") or "").strip()
    if suggested_action not in {"keep", "rewrite", "drop"}:
        suggested_action = "keep" if score >= pass_score else "drop"

    answer_issue_type = str(raw.get("answer_issue_type") or "none").strip()
    if answer_issue_type not in ANSWER_ISSUE_TYPES:
        answer_issue_type = "none"

    raw_pass_filter = raw.get("pass_filter", score >= pass_score)
    if isinstance(raw_pass_filter, str):
        pass_filter = raw_pass_filter.strip().lower() in {"true", "1", "yes", "y"}
    else:
        pass_filter = bool(raw_pass_filter)
    if score < pass_score or answer_issue_type in {"empty", "unsafe", "off_topic"}:
        pass_filter = False

    return {
        "score": score,
        "pass_filter": pass_filter,
        "quality_level": str(raw.get("quality_level") or level),
        "reason": str(raw.get("reason") or "").strip(),
        "issues": [str(issue) for issue in issues],
        "suggested_action": suggested_action,
        "answer_issue_type": answer_issue_type,
        "risk_label": risk_label,
        "status": str(raw.get("status") or "ok"),
    }


def should_process(row: dict[str, Any]) -> bool:
    answer = sft_answer(row)
    if answer.get("status") not in {None, "ok"}:
        return True
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score generated SFT question-answer pairs and write only training-suitable rows to output."
    )
    parser.add_argument("--input", required=True, help="Input answered JSONL file, usually under labeled_data.")
    parser.add_argument("--output", required=True, help="Filtered output JSONL file containing passing QA rows.")
    parser.add_argument(
        "--scored-output",
        default="",
        help="Optional JSONL file containing all scored QA rows, including rejected rows.",
    )
    parser.add_argument("--config", default="configs/answer_filter.json", help="API config JSON file.")
    parser.add_argument("--limit", type=int, default=0, help="Score at most N rows. 0 means all.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent API request workers.")
    parser.add_argument("--skip-done", action="store_true", help="Skip ids already present in scored-output/output.")
    parser.add_argument("--pass-score", type=int, default=7, help="Minimum score required to keep a QA pair.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    scored_output_path = Path(args.scored_output) if args.scored_output else None

    if args.workers <= 0:
        raise ValueError("--workers must be greater than 0")
    if not 0 <= args.pass_score <= 10:
        raise ValueError("--pass-score must be between 0 and 10")

    rows = [row for row in read_jsonl(input_path) if should_process(row)]
    if args.skip_done:
        done_source = scored_output_path or output_path
        done_ids = load_done_ids(done_source)
        rows = [row for row in rows if row.get("id") not in done_ids]
    if args.limit > 0:
        rows = rows[: args.limit]

    answer_filter = SFTAnswerFilter.from_config_file(args.config, args.pass_score)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if scored_output_path is not None:
        scored_output_path.parent.mkdir(parents=True, exist_ok=True)

    output_mode = "a" if args.skip_done else "w"
    scored_mode = "a" if args.skip_done else "w"
    kept_count = 0
    scored_count = 0

    def evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
        result = answer_filter.evaluate_pair(row)
        output_row = dict(row)
        output_row.pop("headings", None)
        output_row["sft_answer_eval"] = result
        if answer_filter.config.sleep > 0:
            time.sleep(answer_filter.config.sleep)
        return output_row

    with output_path.open(output_mode, encoding="utf-8", newline="\n") as filtered_file:
        scored_file = (
            scored_output_path.open(scored_mode, encoding="utf-8", newline="\n")
            if scored_output_path is not None
            else None
        )
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                future_to_row = {executor.submit(evaluate_row, row): row for row in rows}
                iterator = as_completed(future_to_row)
                if tqdm is not None:
                    iterator = tqdm(iterator, total=len(rows), desc="Answer filter", unit="item")

                for index, future in enumerate(iterator, start=1):
                    row = future_to_row[future]
                    try:
                        output_row = future.result()
                    except Exception as exc:
                        output_row = dict(row)
                        output_row.pop("headings", None)
                        output_row["sft_answer_eval"] = {
                            "score": 0,
                            "pass_filter": False,
                            "quality_level": "不可用",
                            "reason": f"并发任务失败：{exc}",
                            "issues": ["worker_error"],
                            "suggested_action": "drop",
                            "answer_issue_type": "empty",
                            "risk_label": pair_risk_label(row),
                            "status": "worker_error",
                        }

                    result = output_row["sft_answer_eval"]
                    scored_count += 1

                    if scored_file is not None:
                        scored_file.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                        scored_file.flush()

                    if result["pass_filter"]:
                        filtered_file.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                        filtered_file.flush()
                        kept_count += 1

                    if tqdm is not None and hasattr(iterator, "set_postfix"):
                        iterator.set_postfix(kept=kept_count, score=result["score"], status=result["status"])
                    else:
                        print(
                            f"[{index}/{len(rows)}] score={result['score']} "
                            f"pass={result['pass_filter']} kept={kept_count}"
                        )
        finally:
            if scored_file is not None:
                scored_file.close()

    print(f"Scored QA pairs: {scored_count}")
    print(f"Kept QA pairs: {kept_count}")
    print(f"Filtered output: {output_path.resolve()}")
    if scored_output_path is not None:
        print(f"Scored output: {scored_output_path.resolve()}")


if __name__ == "__main__":
    main()
