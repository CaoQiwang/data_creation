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


SYSTEM_PROMPT = """你是军事领域 SFT 数据构造流程中的“出题规划”专家。
你的任务不是给材料打分，也不是筛选材料；你的任务是判断给定 chunk 适合生成多少个问题、适合生成哪些类型的问题。

核心判断标准：
这个 chunk 是否包含足够明确、可依据的军事/国防/安全相关信息，能够支持生成若干个有答案依据的问题？

重点考虑：
1. 是否与军事、国防、国家安全、军队建设、法规政策、战略形势、装备知识、军事历史等领域相关。
2. 是否有明确的信息点可以出题，例如事实、定义、时间线、因果关系、分类、对比、措施、影响、原则、流程。
3. 不要因为文风普通、段落不够完整、来源不是权威文章就减少出题；只要能支撑有依据的问题，就可以推荐出题。
4. 推荐 0 个问题的情况：严重乱码、目录/索引/参考文献/版权页/广告、几乎无信息量、无军事相关性、上下文严重残缺、主要是格式噪声，或包含不宜出题的可操作伤害细节。
5. 安全边界：如果材料包含具体攻击、规避监控、武器制造、行动实施等可操作伤害细节，普通问答数量应为 0；若适合安全教育，只推荐 refusal、critique、reasoning 等安全边界类问题。
6. 优先推荐 qa、reasoning、comparison、summary 等独立可回答的问题类型；谨慎推荐 extraction。

推荐问题数量：
0：不建议出题。
1或2：信息点较少、主题很窄、冷门实体事实风险较高，或只适合生成一个稳妥问题。
3或更多：材料中有多个相对清楚且彼此不同的信息点或能力方向，可生成多个不同角度的问题。
请根据材料的信息密度、主题宽度、事实风险和可训练能力方向自由推荐数量，不要为了凑数而推荐过多问题。

推荐问题类型只能从以下枚举中选择：qa、summary、extraction、classification、comparison、reasoning、rewrite、json_generation、critique、refusal、drafting、plan、outline。
推荐问题类型应贴合材料特点。材料只是后续生成问题的“选题种子”，不是最终 SFT 的上下文，因此推荐的类型必须能生成独立可回答的问题。

材料类型与可用题型矩阵：
- 政策法规、条例制度、规范性文件：qa、classification、json_generation、outline、critique；适合围绕概念解释、条目分类、制度结构、执行边界和改进建议出题。
- 白皮书、理论文章、重要讲话、政策解读：summary、reasoning、outline、drafting、critique、qa；适合围绕核心观点、原则逻辑、实践启示、学习提纲和宣讲稿出题。
- 评论文章、观点分析、形势观察：reasoning、critique、comparison、drafting、summary；适合围绕观点评析、利弊分析、趋势判断和短评写作出题。
- 基层管理、政治工作、教育训练、作风建设、保障服务报道：plan、critique、reasoning、qa、drafting；适合围绕工作方案、问题诊断、经验启示、通知倡议和改进措施出题。
- 装备技术、科研创新、信息化建设、能力建设材料：qa、comparison、classification、json_generation、reasoning；适合围绕概念功能、技术分类、能力差异、发展趋势和结构化整理出题。
- 军事历史、战例战史、人物事件：summary、comparison、reasoning、outline、qa；适合围绕历史背景、阶段脉络、经验教训和对比分析出题。若是冷门细节，减少数量并转为更通用的问题。
- 新闻简讯、会议活动、人物事迹、军民关系报道：qa、summary、reasoning、drafting；适合围绕事件意义、经验做法、精神品质、宣传稿或简短总结出题，避免依赖具体原文细节。
- 明确且通用的清单、要素、时间线、指标、分类体系：classification、json_generation、qa；可少量使用 extraction，但不得生成“从材料中提取”式阅读理解问题。
- 存在对象差异、阶段差异、利弊关系、前后变化：comparison、reasoning、classification。
- 风险较高或可能诱导攻击实施、规避监控、武器制造、行动步骤等操作细节：refusal、critique、reasoning；普通知识问答数量应为 0 或极少。
- 冷门人物、部队番号、装备型号、具体战斗等事实密集材料：少推荐 summary/reasoning/extraction，多推荐边界清楚的 qa 或 comparison，且推荐数量应保守。

为了提高题型多样性，不要总是只推荐 qa、summary、reasoning、comparison。只要材料适配，就应主动推荐 plan、critique、outline、drafting、classification、json_generation 等类型；但不要为了多样性硬塞不适配的类型。
必须给出 question_type_plan，并把每种题型的出题数量写死。question_type_plan 中所有 count 之和必须等于 recommended_question_count；后续问题生成阶段会严格按照这个计划执行。

只返回一个 JSON 对象，不要输出 Markdown，不要输出多余解释。JSON 字段为：
{
  "reason": "一句话说明该 chunk 的出题规划依据",
  "issues": ["主要问题1", "主要问题2"],
  "suggested_use": "建议如何用于问题生成；若不适合则写不建议用于出题",
  "recommended_question_count": 0 或正整数,
  "recommended_question_types": ["qa/reasoning/summary 等，按推荐优先级排序"],
  "question_type_plan": [
    {
      "question_type": "qa/summary/extraction/classification/comparison/reasoning/rewrite/json_generation/critique/refusal/drafting/plan/outline",
      "count": 1,
      "reason": "一句话说明为什么该材料适合生成这个题型"
    }
  ],
  "question_count_reason": "一句话说明为什么推荐这个问题数量和类型"
}
"""


ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
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
    "drafting",
    "plan",
    "outline",
}


def normalize_question_type_plan(raw: Any, question_count: int, fallback_types: list[str]) -> list[dict[str, Any]]:
    if question_count <= 0:
        return []

    plan: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            question_type = str(item.get("question_type") or "").strip()
            if question_type not in QUESTION_TYPES:
                continue
            try:
                count = int(round(float(item.get("count", 1))))
            except (TypeError, ValueError):
                count = 1
            count = max(0, count)
            if count <= 0:
                continue
            plan.append(
                {
                    "question_type": question_type,
                    "count": count,
                    "reason": str(item.get("reason") or "").strip(),
                }
            )

    if not plan:
        types = fallback_types or ["qa"]
        remaining = question_count
        for index, question_type in enumerate(types):
            if remaining <= 0:
                break
            count = 1 if index < len(types) - 1 else remaining
            plan.append({"question_type": question_type, "count": count, "reason": "由推荐题型列表回退生成。"})
            remaining -= count

    total = sum(item["count"] for item in plan)
    if total > question_count:
        overflow = total - question_count
        for item in reversed(plan):
            if overflow <= 0:
                break
            reducible = min(item["count"], overflow)
            item["count"] -= reducible
            overflow -= reducible
        plan = [item for item in plan if item["count"] > 0]
    elif total < question_count and plan:
        plan[-1]["count"] += question_count - total

    return plan


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
            "reason": f"API评估失败：{last_error}",
            "issues": ["api_error"],
            "suggested_use": "不建议使用，需重新评估",
            "recommended_question_count": 0,
            "recommended_question_types": [],
            "question_type_plan": [],
            "question_count_reason": "API评估失败，无法推荐问题数量和类型。",
        }

    def _build_user_prompt(self, text: str) -> str:
        text = compact_text(text, self.config.max_input_chars)
        return f"请评估下面这条 chunk 是否适合用于生成问题：\n\n{text}"

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
    issues = raw.get("issues", [])
    if isinstance(issues, str):
        issues = [issues]
    if not isinstance(issues, list):
        issues = []

    raw_plan_count = 0
    raw_plan = raw.get("question_type_plan")
    if isinstance(raw_plan, list):
        for item in raw_plan:
            if not isinstance(item, dict):
                continue
            try:
                raw_plan_count += max(0, int(round(float(item.get("count", 0)))))
            except (TypeError, ValueError):
                continue

    question_count = raw.get("recommended_question_count")
    try:
        question_count = int(round(float(question_count)))
    except (TypeError, ValueError):
        question_count = raw_plan_count or 1
    question_count = max(0, question_count)

    question_types = raw.get("recommended_question_types", [])
    if isinstance(question_types, str):
        question_types = [item.strip() for item in re.split(r"[,，/、\s]+", question_types) if item.strip()]
    if not isinstance(question_types, list):
        question_types = []

    normalized_types: list[str] = []
    for question_type in question_types:
        question_type = str(question_type).strip()
        if question_type in QUESTION_TYPES and question_type not in normalized_types:
            normalized_types.append(question_type)
    if question_count > 0 and not normalized_types:
        normalized_types = ["qa"]

    question_type_plan = normalize_question_type_plan(
        raw_plan,
        question_count,
        normalized_types,
    )
    normalized_types = []
    for item in question_type_plan:
        question_type = item["question_type"]
        if question_type not in normalized_types:
            normalized_types.append(question_type)

    return {
        "reason": str(raw.get("reason") or ""),
        "issues": [str(issue) for issue in issues],
        "suggested_use": str(raw.get("suggested_use") or ""),
        "recommended_question_count": question_count,
        "recommended_question_types": normalized_types,
        "question_type_plan": question_type_plan,
        "question_count_reason": str(raw.get("question_count_reason") or ""),
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
                        "reason": f"并发任务失败：{exc}",
                        "issues": ["worker_error"],
                        "suggested_use": "不建议使用，需重新评估",
                        "recommended_question_count": 0,
                        "recommended_question_types": [],
                        "question_type_plan": [],
                        "question_count_reason": "并发任务失败，无法推荐问题数量和类型。",
                    }

                result = output_row["sft_material_eval"]
                f.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                f.flush()

                if tqdm is not None and hasattr(iterator, "set_postfix"):
                    iterator.set_postfix(q_count=result["recommended_question_count"])
                else:
                    print(
                        f"[{index}/{len(rows)}] "
                        f"recommended_question_count={result['recommended_question_count']}"
                    )

    print(f"Planned rows: {len(rows)}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
