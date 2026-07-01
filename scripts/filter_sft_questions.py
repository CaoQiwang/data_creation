from __future__ import annotations

import argparse
import json
import os
import re
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


SYSTEM_PROMPT = """你是军事领域 SFT 数据构造流程中的“问题质量过滤”评估专家。
你的任务是评估已经生成的问题是否适合进入后续答案生成阶段。

评分核心：
这个问题需要像真实用户会直接提出的问题，并且不太冷门，即不过于依赖原始材料，能被模型独立、稳健、安全地回答

评分范围为 0-10 分，必须是整数：
0-2 分：不可用。问题为空、乱码、明显不通顺、无法理解、严重依赖原文上下文，或要求可操作伤害内容。
3-4 分：较差。问题过泛、信息不足、多个不相关问题硬拼、表达别扭，或答案边界不清，进入答案生成后大概率产出低质量样本。
5-6 分：可用但一般。问题基本可回答，但训练价值有限、角度普通、约束不够清楚，或需要轻微改写后更好。
7-8 分：良好。问题自然、独立、边界清楚，适合生成结构化、解释性、概括性、对比性或分析性 SFT 答案。
9-10 分：优秀。问题真实、清晰、有训练价值，能引导模型输出准确、稳健、结构清楚且安全的高质量答案。

重点检查：
1. 独立性：不能出现“根据材料”“结合上文”“文中提到”“上述内容”等依赖原文的表达。
2. 可回答性：问题应有明确任务和范围，不能只问“怎么看”“有什么启示”却没有主题边界。
3. 训练价值：优先保留能训练解释、归纳、对比、分类、政策解读、风险辨析、结构化整理能力的问题。
4. 安全边界：如果问题要求攻击实施、武器制造、规避侦察、突破系统、行动步骤等可操作伤害内容，应判为不通过；安全科普、风险识别、原则性说明可以保留。
5. 表达质量：中文自然、没有明显病句、没有重复凑数、不是多个不相干问题拼接。

只返回一个 JSON 对象，不要输出 Markdown，不要输出多余解释。JSON 字段为：
{
  "score": 0-10 的整数,
  "pass_filter": true 或 false,
  "quality_level": "不可用/较差/可用/良好/优秀",
  "reason": "一句话说明评分和是否通过的主要原因",
  "issues": ["主要问题1", "主要问题2"],
  "suggested_action": "keep/rewrite/drop",
  "rewrite_suggestion": "如建议改写，给出一个更好的问题；否则为空字符串",
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


@dataclass
class QuestionFilterConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    retries: int = 2
    temperature: float = 0.0
    max_output_tokens: int = 500
    sleep: float = 0.0
    extra_body: dict[str, Any] | None = None


class SFTQuestionFilter:
    def __init__(self, config: QuestionFilterConfig, pass_score: int) -> None:
        self.config = config
        self.pass_score = pass_score

    @classmethod
    def from_config_file(cls, path: str | Path, pass_score: int) -> "SFTQuestionFilter":
        return cls(load_question_filter_config(Path(path)), pass_score)

    def evaluate_question(self, row: dict[str, Any]) -> dict[str, Any]:
        question = question_text(row)
        heuristic_result = heuristic_reject(question)
        if heuristic_result is not None:
            return normalize_question_eval(heuristic_result, self.pass_score)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_user_prompt(row)},
        ]

        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                content = self._chat_completion(messages)
                return normalize_question_eval(extract_json_object(content), self.pass_score)
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
            "reason": f"API问题评分失败：{last_error}",
            "issues": ["api_error"],
            "suggested_action": "drop",
            "rewrite_suggestion": "",
            "risk_label": question_risk_label(row),
            "status": "api_error",
        }

    def _build_user_prompt(self, row: dict[str, Any]) -> str:
        question = sft_question(row)
        eval_context = {
            "question": question.get("question", ""),
            "question_type": question.get("question_type", ""),
            "expected_answer_format": question.get("expected_answer_format", ""),
            "difficulty": question.get("difficulty", ""),
            "risk_label": question.get("risk_label", ""),
            "generation_reason": question.get("reason", ""),
            "material_eval": row.get("sft_material_eval", {}),
        }
        return "请评估下面这个生成问题是否适合进入答案生成阶段：\n\n" + json.dumps(
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


def load_question_filter_config(path: Path) -> QuestionFilterConfig:
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

    return QuestionFilterConfig(
        base_url=str(data.get("base_url", "https://api.siliconflow.cn/v1")),
        api_key=str(api_key),
        model=str(data.get("model", "Qwen/Qwen3-8B")),
        timeout=int(data.get("timeout", 60)),
        retries=int(data.get("retries", 2)),
        temperature=float(data.get("temperature", 0.0)),
        max_output_tokens=int(data.get("max_output_tokens", 500)),
        sleep=float(data.get("sleep", 0.0)),
        extra_body=extra_body,
    )


def sft_question(row: dict[str, Any]) -> dict[str, Any]:
    question = row.get("sft_question")
    if isinstance(question, dict):
        return question
    return {}


def question_text(row: dict[str, Any]) -> str:
    return str(sft_question(row).get("question") or "").strip()


def question_risk_label(row: dict[str, Any]) -> str:
    risk_label = str(sft_question(row).get("risk_label") or "public_safe").strip()
    if risk_label in RISK_LABELS:
        return risk_label
    return "public_safe"


def heuristic_reject(question: str) -> dict[str, Any] | None:
    if not question:
        return {
            "score": 0,
            "pass_filter": False,
            "quality_level": "不可用",
            "reason": "问题为空，无法进入答案生成阶段。",
            "issues": ["empty_question"],
            "suggested_action": "drop",
            "rewrite_suggestion": "",
            "risk_label": "public_safe",
        }

    if any(pattern in question for pattern in DEPENDENT_CONTEXT_PATTERNS):
        return {
            "score": 2,
            "pass_filter": False,
            "quality_level": "不可用",
            "reason": "问题依赖原始材料或上文，不能被模型独立回答。",
            "issues": ["depends_on_source_context"],
            "suggested_action": "rewrite",
            "rewrite_suggestion": remove_context_dependency(question),
            "risk_label": "public_safe",
        }

    if len(question) < 8:
        return {
            "score": 2,
            "pass_filter": False,
            "quality_level": "不可用",
            "reason": "问题过短，任务边界不清。",
            "issues": ["too_short"],
            "suggested_action": "rewrite",
            "rewrite_suggestion": "",
            "risk_label": "public_safe",
        }

    return None


def remove_context_dependency(question: str) -> str:
    rewritten = question
    for pattern in DEPENDENT_CONTEXT_PATTERNS:
        rewritten = rewritten.replace(pattern, "")
    rewritten = re.sub(r"^[，,。:：\s]+", "", rewritten).strip()
    return rewritten


def normalize_question_eval(raw: dict[str, Any], pass_score: int) -> dict[str, Any]:
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

    raw_pass_filter = raw.get("pass_filter", score >= pass_score)
    if isinstance(raw_pass_filter, str):
        pass_filter = raw_pass_filter.strip().lower() in {"true", "1", "yes", "y"}
    else:
        pass_filter = bool(raw_pass_filter)
    if score < pass_score or risk_label == "refuse_or_exclude":
        pass_filter = False

    return {
        "score": score,
        "pass_filter": pass_filter,
        "quality_level": str(raw.get("quality_level") or level),
        "reason": str(raw.get("reason") or "").strip(),
        "issues": [str(issue) for issue in issues],
        "suggested_action": suggested_action,
        "rewrite_suggestion": str(raw.get("rewrite_suggestion") or "").strip(),
        "risk_label": risk_label,
        "status": str(raw.get("status") or "ok"),
    }


def should_process(row: dict[str, Any], include_refuse_risk: bool) -> bool:
    question = sft_question(row)
    if not question_text(row):
        return True
    if question.get("status") not in {None, "ok"}:
        return True
    if not include_refuse_risk and question.get("risk_label") == "refuse_or_exclude":
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score generated SFT questions with an LLM and write only passing rows to output."
    )
    parser.add_argument("--input", required=True, help="Input question JSONL file, usually under labeled_data.")
    parser.add_argument("--output", required=True, help="Filtered output JSONL file containing passing question rows.")
    parser.add_argument(
        "--scored-output",
        default="",
        help="Optional JSONL file containing all scored question rows, including rejected rows.",
    )
    parser.add_argument("--config", default="configs/question_filter.json", help="API config JSON file.")
    parser.add_argument("--limit", type=int, default=0, help="Score at most N rows. 0 means all.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent API request workers.")
    parser.add_argument("--skip-done", action="store_true", help="Skip ids already present in scored-output/output.")
    parser.add_argument("--pass-score", type=int, default=7, help="Minimum score required to keep a question.")
    parser.add_argument(
        "--include-refuse-risk",
        action="store_true",
        help="Also score questions marked refuse_or_exclude. By default they are skipped.",
    )
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

    rows = [row for row in read_jsonl(input_path) if should_process(row, args.include_refuse_risk)]
    if args.skip_done:
        done_source = scored_output_path or output_path
        done_ids = load_done_ids(done_source)
        rows = [row for row in rows if row.get("id") not in done_ids]
    if args.limit > 0:
        rows = rows[: args.limit]

    question_filter = SFTQuestionFilter.from_config_file(args.config, args.pass_score)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if scored_output_path is not None:
        scored_output_path.parent.mkdir(parents=True, exist_ok=True)

    output_mode = "a" if args.skip_done else "w"
    scored_mode = "a" if args.skip_done else "w"
    kept_count = 0
    scored_count = 0

    def evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
        result = question_filter.evaluate_question(row)
        output_row = dict(row)
        output_row.pop("headings", None)
        output_row["sft_question_eval"] = result
        if question_filter.config.sleep > 0:
            time.sleep(question_filter.config.sleep)
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
                    iterator = tqdm(iterator, total=len(rows), desc="Question filter", unit="item")

                for index, future in enumerate(iterator, start=1):
                    row = future_to_row[future]
                    try:
                        output_row = future.result()
                    except Exception as exc:
                        output_row = dict(row)
                        output_row.pop("headings", None)
                        output_row["sft_question_eval"] = {
                            "score": 0,
                            "pass_filter": False,
                            "quality_level": "不可用",
                            "reason": f"并发任务失败：{exc}",
                            "issues": ["worker_error"],
                            "suggested_action": "drop",
                            "rewrite_suggestion": "",
                            "risk_label": question_risk_label(row),
                            "status": "worker_error",
                        }

                    result = output_row["sft_question_eval"]
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

    print(f"Scored questions: {scored_count}")
    print(f"Kept questions: {kept_count}")
    print(f"Filtered output: {output_path.resolve()}")
    if scored_output_path is not None:
        print(f"Scored output: {scored_output_path.resolve()}")


if __name__ == "__main__":
    main()
