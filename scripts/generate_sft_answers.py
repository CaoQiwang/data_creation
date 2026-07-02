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


SYSTEM_PROMPT = """你是军事领域SFT数据构造专家。
任务：只根据用户给出的问题生成答案，用于构造军事大模型SFT训练样本。

回答原则：
1. 只能根据问题本身作答，不会看到原始材料或上下文。
2. 答案应准确、稳健、结构清晰，适合作为SFT样本的output。
3. 对概念解释、历史启示、政策法规、公开知识类问题，可以给出通用且审慎的回答。
4. 如果问题要求具体攻击实施、武器制造、规避侦察、突破系统、行动步骤等可操作伤害内容，应安全拒答并转向原则性、合规性或风险识别说明。
5. 不要声称“根据材料”“文中提到”，因为你没有看到原文。
6. 不要输出Markdown代码块，不要输出多余解释。

只返回一个JSON对象，字段如下：
{
  "answer": "可直接作为SFT样本output的答案",
  "risk_label": "public_safe/needs_caution/refuse_or_exclude",
  "quality_notes": "一句话说明答案特点或安全处理方式"
}
"""


@dataclass
class AnswerConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    retries: int = 2
    temperature: float = 0.2
    max_output_tokens: int = 1200
    sleep: float = 0.0
    extra_body: dict[str, Any] | None = None


class SFTAnswerGenerator:
    def __init__(self, config: AnswerConfig) -> None:
        self.config = config

    @classmethod
    def from_config_file(cls, path: str | Path) -> "SFTAnswerGenerator":
        return cls(load_answer_config(Path(path)))

    def generate_answer(self, question: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question.strip()},
        ]

        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                content = self._chat_completion(messages)
                return normalize_answer(extract_json_object(content))
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
            "answer": "",
            "risk_label": "needs_caution",
            "quality_notes": f"API答案生成失败：{last_error}",
            "status": "api_error",
        }

    def _chat_completion(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
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


def load_answer_config(path: Path) -> AnswerConfig:
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

    return AnswerConfig(
        base_url=str(data.get("base_url", "https://api.siliconflow.cn/v1")),
        api_key=str(api_key),
        model=str(data.get("model", "Qwen/Qwen3-8B")),
        timeout=int(data.get("timeout", 60)),
        retries=int(data.get("retries", 2)),
        temperature=float(data.get("temperature", 0.2)),
        max_output_tokens=int(data.get("max_output_tokens", 1200)),
        sleep=float(data.get("sleep", 0.0)),
        extra_body=extra_body,
    )


def normalize_answer(raw: dict[str, Any]) -> dict[str, Any]:
    answer = str(raw.get("answer") or "").strip()
    risk_label = str(raw.get("risk_label") or "public_safe").strip()
    if risk_label not in {"public_safe", "needs_caution", "refuse_or_exclude"}:
        risk_label = "needs_caution"

    return {
        "answer": answer,
        "risk_label": risk_label,
        "quality_notes": str(raw.get("quality_notes") or "").strip(),
        "status": "ok" if answer else "empty_answer",
    }


def sft_question(row: dict[str, Any]) -> dict[str, Any]:
    question = row.get("sft_question")
    if isinstance(question, dict):
        return question
    return {}


def question_text(row: dict[str, Any]) -> str:
    return str(sft_question(row).get("question") or "").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate answers from questions only and append sft_answer to each JSONL row."
    )
    parser.add_argument("--input", required=True, help="Input question JSONL file, usually under labeled_data.")
    parser.add_argument("--output", required=True, help="Output answered JSONL file, recommended under labeled_data.")
    parser.add_argument("--config", default="configs/answer.json", help="API config JSON file.")
    parser.add_argument("--limit", type=int, default=0, help="Generate at most N answers. 0 means all.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent API request workers.")
    parser.add_argument("--skip-done", action="store_true", help="Skip ids already present in output.")
    parser.add_argument(
        "--include-refuse-risk",
        action="store_true",
        help="Also answer questions marked refuse_or_exclude. By default they are skipped.",
    )
    return parser.parse_args()


def should_process(row: dict[str, Any], include_refuse_risk: bool) -> bool:
    question = sft_question(row)
    if not question_text(row):
        return False
    if question.get("status") not in {None, "ok"}:
        return False
    if not include_refuse_risk and question.get("risk_label") == "refuse_or_exclude":
        return False
    return True


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    rows = [row for row in read_jsonl(input_path) if should_process(row, args.include_refuse_risk)]
    if args.skip_done:
        done_ids = load_done_ids(output_path)
        rows = [row for row in rows if row.get("id") not in done_ids]
    if args.limit > 0:
        rows = rows[: args.limit]
    if args.workers <= 0:
        raise ValueError("--workers must be greater than 0")

    generator = SFTAnswerGenerator.from_config_file(args.config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.skip_done else "w"

    def generate_row(row: dict[str, Any]) -> dict[str, Any]:
        result = generator.generate_answer(question_text(row))
        result["answer_from_question_only"] = True
        result["question"] = question_text(row)
        output_row = dict(row)
        output_row.pop("headings", None)
        output_row["sft_answer"] = result
        if generator.config.sleep > 0:
            time.sleep(generator.config.sleep)
        return output_row

    with output_path.open(mode, encoding="utf-8", newline="\n") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_row = {executor.submit(generate_row, row): row for row in rows}
            iterator = as_completed(future_to_row)
            if tqdm is not None:
                iterator = tqdm(iterator, total=len(rows), desc="Answers", unit="item")

            for count, future in enumerate(iterator, start=1):
                row = future_to_row[future]
                try:
                    output_row = future.result()
                except Exception as exc:
                    output_row = dict(row)
                    output_row.pop("headings", None)
                    output_row["sft_answer"] = {
                        "answer": "",
                        "risk_label": "needs_caution",
                        "quality_notes": f"并发任务失败：{exc}",
                        "status": "worker_error",
                        "answer_from_question_only": True,
                        "question": question_text(row),
                    }

                f.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                f.flush()

                result = output_row["sft_answer"]
                if tqdm is not None and hasattr(iterator, "set_postfix"):
                    iterator.set_postfix(status=result["status"], risk=result["risk_label"])
                else:
                    print(f"[{count}/{len(rows)}] status={result['status']} risk={result['risk_label']}")

    print(f"Generated answers: {len(rows)}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
