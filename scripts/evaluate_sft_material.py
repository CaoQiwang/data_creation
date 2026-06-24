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


SYSTEM_PROMPT = """你是军事领域SFT数据构造的数据质检专家。
请评估给定材料是否适合作为军事大模型SFT数据的提问材料。

评分范围为0到10分，必须是整数：
0-2分：不可用。乱码、目录、广告、极短文本、无军事相关性、事实严重残缺，或不适合作为问答材料。
3-4分：较差。相关性弱、信息量少、上下文不足、表达混乱，只能少量参考。
5-6分：可用。主题相关但质量一般，可构造简单问答。
7-8分：良好。军事、国防、安全、法规、政策、战略、装备等相关，信息较完整，适合构造多条SFT问答。
9-10分：优秀。权威、清晰、结构完整、信息密度高，适合构造高质量军事领域SFT样本。

重点考虑：
1. 军事、国防、国家安全、军队建设、法规政策、战略形势、装备知识等领域相关性。
2. 信息完整度和事实密度，是否能支撑有价值的问题与答案。
3. 文本清晰度，是否存在乱码、OCR错误、格式噪声、目录残留、网页尾注等。
4. 训练价值，是否适合生成问答、解释、归纳、对比、政策解读类SFT数据。
5. 安全边界。若材料包含具体攻击、规避监控、武器制造、行动实施等可操作伤害细节，应降低分数并说明风险。

只返回一个JSON对象，不要输出Markdown，不要输出多余解释。JSON字段：
{
  "score": 0-10的整数,
  "quality_level": "不可用/较差/可用/良好/优秀",
  "reason": "一句话说明评分理由",
  "issues": ["主要问题1", "主要问题2"],
  "suggested_use": "建议如何用于SFT，若不可用则写不建议使用"
}
"""


ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass
class EvaluatorConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    retries: int = 2
    temperature: float = 0.0
    max_output_tokens: int = 400
    max_input_chars: int = 5000
    sleep: float = 0.0
    extra_body: dict[str, Any] | None = None


class SFTMaterialEvaluator:
    def __init__(self, config: EvaluatorConfig) -> None:
        self.config = config

    @classmethod
    def from_config_file(cls, path: str | Path) -> "SFTMaterialEvaluator":
        config = load_eval_config(Path(path))
        return cls(config)

    def evaluate_text(self, text: str) -> dict[str, Any]:
        prompt = self._build_user_prompt(text)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                content = self._chat_completion(messages)
                return normalize_eval(extract_json_object(content))
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
            "quality_level": "不可用",
            "reason": f"API评估失败：{last_error}",
            "issues": ["api_error"],
            "suggested_use": "不建议使用，需重新评估",
        }

    def _build_user_prompt(self, text: str) -> str:
        text = compact_text(text, self.config.max_input_chars)
        return f"请评估下面这条材料：\n\n{text}"

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


def expand_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        return ENV_VAR_RE.sub(lambda match: os.getenv(match.group(1), ""), value)
    return value


def load_eval_config(path: Path) -> EvaluatorConfig:
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

    return EvaluatorConfig(
        base_url=str(data.get("base_url", "https://api.siliconflow.cn/v1")),
        api_key=str(api_key),
        model=str(data.get("model", "Qwen/Qwen3-8B")),
        timeout=int(data.get("timeout", 60)),
        retries=int(data.get("retries", 2)),
        temperature=float(data.get("temperature", 0.0)),
        max_output_tokens=int(data.get("max_output_tokens", 400)),
        max_input_chars=int(data.get("max_input_chars", 5000)),
        sleep=float(data.get("sleep", 0.0)),
        extra_body=extra_body,
    )


def compact_text(text: str, max_chars: int) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return f"{text[:half].strip()}\n\n...[中间内容已截断]...\n\n{text[-half:].strip()}"


def extract_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])


def normalize_eval(raw: dict[str, Any]) -> dict[str, Any]:
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

    return {
        "score": score,
        "quality_level": str(raw.get("quality_level") or level),
        "reason": str(raw.get("reason") or ""),
        "issues": [str(issue) for issue in issues],
        "suggested_use": str(raw.get("suggested_use") or ""),
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
            if "text" not in row:
                raise ValueError(f"Missing required field 'text' on line {line_no}")
            rows.append(row)
    return rows


def load_done_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()

    done_ids: set[str] = set()
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            row_id = row.get("id")
            if isinstance(row_id, str):
                done_ids.add(row_id)
    return done_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate chunkdata JSONL rows by reading only their text field."
    )
    parser.add_argument("--input", required=True, help="Input chunk_data JSONL file.")
    parser.add_argument("--output", required=True, help="Output evaluation JSONL file, recommended under labeled_data.")
    parser.add_argument("--config", default="configs/eval.json", help="API config JSON file.")
    parser.add_argument("--limit", type=int, default=0, help="Evaluate at most N rows. 0 means all.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent API request workers.")
    parser.add_argument("--skip-done", action="store_true", help="Skip ids already present in output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    rows = read_jsonl(input_path)
    if args.skip_done:
        done_ids = load_done_ids(output_path)
        rows = [row for row in rows if row.get("id") not in done_ids]
    if args.limit > 0:
        rows = rows[: args.limit]
    if args.workers <= 0:
        raise ValueError("--workers must be greater than 0")

    evaluator = SFTMaterialEvaluator.from_config_file(args.config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.skip_done else "w"

    def evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
        result = evaluator.evaluate_text(str(row["text"]))
        output_row = dict(row)
        output_row.pop("headings", None)
        output_row["sft_material_eval"] = result
        if evaluator.config.sleep > 0:
            time.sleep(evaluator.config.sleep)
        return output_row

    with output_path.open(mode, encoding="utf-8", newline="\n") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_row = {executor.submit(evaluate_row, row): row for row in rows}
            iterator = as_completed(future_to_row)
            if tqdm is not None:
                iterator = tqdm(iterator, total=len(rows), desc="Evaluating", unit="item")

            for index, future in enumerate(iterator, start=1):
                row = future_to_row[future]
                try:
                    output_row = future.result()
                except Exception as exc:
                    output_row = dict(row)
                    output_row.pop("headings", None)
                    output_row["sft_material_eval"] = {
                        "score": 0,
                        "quality_level": "不可用",
                        "reason": f"并发任务失败：{exc}",
                        "issues": ["worker_error"],
                        "suggested_use": "不建议使用，需重新评估",
                    }

                result = output_row["sft_material_eval"]
                f.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                f.flush()

                if tqdm is not None and hasattr(iterator, "set_postfix"):
                    iterator.set_postfix(score=result["score"], level=result["quality_level"])
                else:
                    print(
                        f"[{index}/{len(rows)}] score={result['score']} "
                        f"level={result['quality_level']}"
                    )

    print(f"Evaluated rows: {len(rows)}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
