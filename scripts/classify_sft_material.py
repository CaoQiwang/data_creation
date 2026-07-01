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

from evaluate_sft_material import compact_text, expand_env_vars, extract_json_object, load_done_ids, read_jsonl


SYSTEM_PROMPT = """你是军事领域SFT数据的问题分类标注专家。
任务：根据已经生成并通过质量过滤的 SFT 问题，以及候选分类目录，为问题打上最合适的SFT能力分类标签。

分类原则：
1. 只在候选分类ID中选择，不要创造不存在的标签。
2. 分类对象是“问题本身”，不是原始材料。不要因为材料来源、材料正文或出题规划里出现某个词，就给问题打材料主题标签。
3. 优先选择该问题最终会训练的能力标签，例如问答、摘要、对比、研判、文书、计划、提纲、风险辨析、知识整理等。
4. 每个问题只打一个最合适的主标签，不要输出辅标签。
5. 侧别判断要严格：问题关注中国国防、我军、我国军队建设、国内国防法规政策、军队院校教材、国防教育等内容，默认归“我方”；只有问题明确以外国军队、外方国家、对手能力、外军制度、外军行动、外部威胁为分析对象时，才归“他方”。
6. 避免把包含具体攻击、武器制造、规避监控、行动实施等可操作伤害内容的问题标为可训练的操作类能力；这类内容应给出更高风险标签。
7. 如果候选分类中没有明显合适的标签，不要硬选。此时返回 primary_label_id 为 null，confidence 不高于 0.35，reason 中说明“其他：现有分类无法准确覆盖该问题”。
8. 如果问题军事相关性弱、主题太泛、任务边界不清，或只能归入非常宽泛的“其他”，也返回 primary_label_id 为 null。
9. 只有在分类路径和问题主题/任务能力有直接对应关系时才选择标签；弱关键词重合不能作为选择依据。

只返回一个JSON对象，不要输出Markdown，不要输出多余解释。JSON字段：
{
  "primary_label_id": "候选分类ID或null；找不到合适分类时必须为null",
  "task_types": ["qa/summary/extraction/classification/comparison/reasoning/rewrite/json_generation/critique/refusal/drafting/plan/outline"],
  "source_type": "textbook/law_regulation/policy_document/press_conference/news_report/white_paper/open_report/other",
  "risk_label": "public_safe/needs_caution/refuse_or_exclude",
  "confidence": 0.0-1.0,
  "reason": "一句话说明问题分类依据；找不到合适分类时以“其他：”开头说明原因",
  "evidence_keywords": ["关键词1", "关键词2"]
}
"""


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}")
ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass
class ClassifierConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    retries: int = 2
    temperature: float = 0.0
    max_output_tokens: int = 700
    max_input_chars: int = 4500
    sleep: float = 0.0
    extra_body: dict[str, Any] | None = None
    candidate_count: int = 60


class SFTQuestionClassifier:
    def __init__(self, config: ClassifierConfig, labels: list[dict[str, Any]]) -> None:
        self.config = config
        self.labels = labels
        self._label_tokens = [make_tokens(label_text(label)) for label in labels]

    @classmethod
    def from_files(cls, config_path: str | Path, taxonomy_path: str | Path) -> "SFTQuestionClassifier":
        config = load_classify_config(Path(config_path))
        taxonomy = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
        labels = load_taxonomy_labels(taxonomy)
        if not isinstance(labels, list) or not labels:
            raise ValueError("Taxonomy file must contain a non-empty labels array.")
        return cls(config, labels)

    def classify_row(self, row: dict[str, Any]) -> dict[str, Any]:
        candidates = self.select_candidates(row)
        prompt = self._build_user_prompt(row, candidates)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                content = self._chat_completion(messages)
                return normalize_classification(extract_json_object(content), candidates)
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
            "primary": None,
            "task_types": [],
            "source_type": "other",
            "risk_label": "needs_caution",
            "confidence": 0.0,
            "reason": f"API分类失败：{last_error}",
            "evidence_keywords": [],
            "candidate_label_ids": [candidate["id"] for candidate in candidates],
            "status": "api_error",
        }

    def select_candidates(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        text_parts = [
            question_text(row),
            str(sft_question(row).get("question_type", "")),
            str(sft_question(row).get("reason", "")),
        ]
        question_eval = row.get("sft_question_eval")
        if isinstance(question_eval, dict):
            text_parts.extend(
                [
                    str(question_eval.get("reason", "")),
                    str(question_eval.get("rewrite_suggestion", "")),
                ]
            )
        text = "\n".join(text_parts)
        text_tokens = make_tokens(text)
        text_lower = text.lower()

        scored: list[tuple[float, dict[str, Any]]] = []
        for label, tokens in zip(self.labels, self._label_tokens):
            score = 0.0
            label_parts = [str(label.get(key, "")) for key in ("side_name", "l1", "l2", "leaf")]
            for part in label_parts:
                part = part.strip()
                if part and part.lower() in text_lower:
                    score += 8.0
            overlap = text_tokens.intersection(tokens)
            score += len(overlap) * 1.5
            if str(label.get("l1", "")) in text:
                score += 3.0
            if str(label.get("l2", "")) in text:
                score += 4.0
            scored.append((score, label))

        scored.sort(key=lambda item: item[0], reverse=True)
        positive = [label for score, label in scored if score > 0]
        if len(positive) >= self.config.candidate_count:
            return positive[: self.config.candidate_count]
        selected_ids = {label["id"] for label in positive}
        fallback = [label for _, label in scored if label["id"] not in selected_ids]
        return (positive + fallback)[: self.config.candidate_count]

    def _build_user_prompt(self, row: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
        question = sft_question(row)
        question_eval = row.get("sft_question_eval", {})
        candidate_lines = [format_candidate_for_prompt(item) for item in candidates]
        context = {
            "id": row.get("id", ""),
            "material_id": row.get("material_id", ""),
            "source": row.get("source", ""),
            "question": question.get("question", ""),
            "question_type": question.get("question_type", ""),
            "expected_answer_format": question.get("expected_answer_format", ""),
            "difficulty": question.get("difficulty", ""),
            "risk_label": question.get("risk_label", ""),
            "generation_reason": question.get("reason", ""),
            "question_eval": question_eval,
        }

        return "\n".join(
            [
                "请为下面这个已生成的问题选择分类标签。",
                "分类依据应以 question 字段和问题任务能力为主；source、material_id 只用于审计，不应替代问题本身。",
                "",
                "问题信息：",
                compact_text(json.dumps(context, ensure_ascii=False), self.config.max_input_chars),
                "",
                "候选分类：",
                "\n".join(candidate_lines),
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


def load_classify_config(path: Path) -> ClassifierConfig:
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

    return ClassifierConfig(
        base_url=str(data.get("base_url", "https://api.siliconflow.cn/v1")),
        api_key=str(api_key),
        model=str(data.get("model", "Qwen/Qwen3-8B")),
        timeout=int(data.get("timeout", 60)),
        retries=int(data.get("retries", 2)),
        temperature=float(data.get("temperature", 0.0)),
        max_output_tokens=int(data.get("max_output_tokens", 700)),
        max_input_chars=int(data.get("max_input_chars", 4500)),
        sleep=float(data.get("sleep", 0.0)),
        extra_body=extra_body,
        candidate_count=int(data.get("candidate_count", 60)),
    )


def load_taxonomy_labels(taxonomy: Any) -> list[dict[str, Any]]:
    if isinstance(taxonomy, list):
        raw_labels = taxonomy
    elif isinstance(taxonomy, dict):
        raw_labels = taxonomy.get("labels") or taxonomy.get("leaf_catalog") or []
    else:
        raw_labels = []

    if not isinstance(raw_labels, list):
        return []
    side_counts = {"friendly": 0, "opponent": 0, "other": 0}
    labels: list[dict[str, Any]] = []
    for label in raw_labels:
        if not isinstance(label, dict):
            continue
        normalized = normalize_label(label, side_counts)
        if normalized["id"]:
            labels.append(normalized)
    return labels


def normalize_label(label: dict[str, Any], side_counts: dict[str, int] | None = None) -> dict[str, Any]:
    label_id = str(label.get("id") or label.get("label_id") or "").strip()
    path = normalize_label_path(label)

    side = str(label.get("side") or "").strip()
    side_name = str(label.get("side_name") or "").strip()
    if not side and label_id:
        side = "friendly" if label_id.startswith("F") else "opponent" if label_id.startswith("O") else ""
    if not side_name:
        side_name = "我方" if side == "friendly" else "他方" if side == "opponent" else ""
    if not side_name and path:
        side_name = path[0]

    l1 = str(label.get("l1") or label.get("level1") or (path[1] if len(path) > 1 else "")).strip()
    l2 = str(label.get("l2") or label.get("level2") or (path[2] if len(path) > 2 else "")).strip()
    leaf = str(
        label.get("leaf")
        or label.get("level3")
        or label.get("name")
        or label.get("leaf_name")
        or (path[-1] if path else "")
    ).strip()
    if not path:
        path = [item for item in (side_name, l1, l2, leaf) if item]
    elif path[0] not in {"我方", "他方"} and side_name:
        path = [side_name, *path]
    if not label_id:
        label_id = make_generated_label_id(side, side_counts)

    return {
        "id": label_id,
        "side": side,
        "side_name": side_name,
        "l1": l1,
        "l2": l2,
        "leaf": leaf,
        "path": path,
    }


def normalize_label_path(label: dict[str, Any]) -> list[str]:
    raw_path = label.get("path") or label.get("full_path")
    if isinstance(raw_path, list):
        return [str(item).strip() for item in raw_path if str(item).strip()]
    if isinstance(raw_path, str):
        splitter = ">" if ">" in raw_path else "/"
        return [item.strip() for item in raw_path.split(splitter) if item.strip()]
    return []


def make_generated_label_id(side: str, side_counts: dict[str, int] | None) -> str:
    if side == "friendly":
        key, prefix = "friendly", "F"
    elif side == "opponent":
        key, prefix = "opponent", "O"
    else:
        key, prefix = "other", "X"
    if side_counts is None:
        return ""
    side_counts[key] = side_counts.get(key, 0) + 1
    return f"{prefix}{side_counts[key]:04d}"


def make_tokens(text: str) -> set[str]:
    tokens = {match.group(0).lower() for match in TOKEN_RE.finditer(text)}
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    tokens.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return {token for token in tokens if token.strip()}


def label_text(label: dict[str, Any]) -> str:
    path_text = " ".join(str(item) for item in label.get("path", []))
    return " ".join([path_text, str(label.get("side_name", "")), str(label.get("l1", "")), str(label.get("l2", "")), str(label.get("leaf", ""))])


def format_candidate_for_prompt(label: dict[str, Any]) -> str:
    path = label.get("path")
    if isinstance(path, list) and path:
        path_text = "/".join(str(item) for item in path if str(item).strip())
    else:
        path_text = "/".join(
            str(label.get(key, "")).strip()
            for key in ("side_name", "l1", "l2", "leaf")
            if str(label.get(key, "")).strip()
        )
    return f'{label["id"]} {path_text}'


def normalize_classification(raw: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_by_id = {str(candidate["id"]): candidate for candidate in candidates}

    primary_id = raw.get("primary_label_id")
    primary = candidate_by_id.get(str(primary_id)) if primary_id is not None else None

    task_types = raw.get("task_types", [])
    if isinstance(task_types, str):
        task_types = [task_types]
    if not isinstance(task_types, list):
        task_types = []

    confidence = raw.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    risk_label = str(raw.get("risk_label") or "public_safe")
    if risk_label not in {"public_safe", "needs_caution", "refuse_or_exclude"}:
        risk_label = "needs_caution"

    evidence_keywords = raw.get("evidence_keywords", [])
    if isinstance(evidence_keywords, str):
        evidence_keywords = [evidence_keywords]
    if not isinstance(evidence_keywords, list):
        evidence_keywords = []

    return {
        "primary": primary,
        "task_types": [str(item) for item in task_types],
        "source_type": str(raw.get("source_type") or "other"),
        "risk_label": risk_label,
        "confidence": confidence,
        "reason": str(raw.get("reason") or ""),
        "evidence_keywords": [str(item) for item in evidence_keywords],
        "candidate_label_ids": [candidate["id"] for candidate in candidates],
        "status": "ok" if primary else "no_primary_label",
    }


def sft_question(row: dict[str, Any]) -> dict[str, Any]:
    question = row.get("sft_question")
    if isinstance(question, dict):
        return question
    return {}


def question_text(row: dict[str, Any]) -> str:
    return str(sft_question(row).get("question") or "").strip()


def question_score(row: dict[str, Any]) -> int:
    result = row.get("sft_question_eval")
    if not isinstance(result, dict):
        return 0
    try:
        return int(result.get("score", 0))
    except (TypeError, ValueError):
        return 0


def should_classify(row: dict[str, Any], min_question_score: int, include_refuse_risk: bool) -> bool:
    question = sft_question(row)
    if not question_text(row):
        return False
    if question.get("status") not in {None, "ok"}:
        return False
    if not include_refuse_risk and question.get("risk_label") == "refuse_or_exclude":
        return False
    question_eval = row.get("sft_question_eval")
    if isinstance(question_eval, dict) and question_eval.get("pass_filter") is False:
        return False
    if min_question_score > 0 and question_score(row) < min_question_score:
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify generated SFT question JSONL rows with an LLM and taxonomy labels."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input question JSONL file, preferably after filter_sft_questions.py.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output classified question JSONL file, recommended under labeled_data.",
    )
    parser.add_argument("--config", default="configs/classify.json", help="API config JSON file.")
    parser.add_argument(
        "--taxonomy",
        default="configs/military_sft_taxonomy_compact.json",
        help="Compact taxonomy JSON generated by build_taxonomy_summary.py.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Classify at most N rows. 0 means all.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent API request workers.")
    parser.add_argument("--skip-done", action="store_true", help="Skip ids already present in output.")
    parser.add_argument(
        "--min-question-score",
        type=int,
        default=0,
        help="Only classify rows whose sft_question_eval.score is at least this value. 0 means no threshold.",
    )
    parser.add_argument(
        "--include-refuse-risk",
        action="store_true",
        help="Also classify questions marked refuse_or_exclude. By default they are skipped.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if args.min_question_score < 0:
        raise ValueError("--min-question-score must be greater than or equal to 0")

    rows = [
        row
        for row in read_jsonl(input_path)
        if should_classify(row, args.min_question_score, args.include_refuse_risk)
    ]
    if args.skip_done:
        done_ids = load_done_ids(output_path)
        rows = [row for row in rows if row.get("id") not in done_ids]
    if args.limit > 0:
        rows = rows[: args.limit]
    if args.workers <= 0:
        raise ValueError("--workers must be greater than 0")

    classifier = SFTQuestionClassifier.from_files(args.config, args.taxonomy)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.skip_done else "w"

    def classify_row(row: dict[str, Any]) -> dict[str, Any]:
        result = classifier.classify_row(row)
        output_row = dict(row)
        output_row.pop("headings", None)
        output_row["sft_question_taxonomy_labels"] = result
        if classifier.config.sleep > 0:
            time.sleep(classifier.config.sleep)
        return output_row

    with output_path.open(mode, encoding="utf-8", newline="\n") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_row = {executor.submit(classify_row, row): row for row in rows}
            iterator = as_completed(future_to_row)
            if tqdm is not None:
                iterator = tqdm(iterator, total=len(rows), desc="Classifying", unit="item")

            for index, future in enumerate(iterator, start=1):
                row = future_to_row[future]
                try:
                    output_row = future.result()
                except Exception as exc:
                    output_row = dict(row)
                    output_row.pop("headings", None)
                    output_row["sft_question_taxonomy_labels"] = {
                        "primary": None,
                        "task_types": [],
                        "source_type": "other",
                        "risk_label": "needs_caution",
                        "confidence": 0.0,
                        "reason": f"并发任务失败：{exc}",
                        "evidence_keywords": [],
                        "candidate_label_ids": [],
                        "status": "worker_error",
                    }

                result = output_row["sft_question_taxonomy_labels"]
                f.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                f.flush()

                primary = result["primary"]["id"] if result.get("primary") else "none"
                if tqdm is not None and hasattr(iterator, "set_postfix"):
                    iterator.set_postfix(primary=primary, risk=result["risk_label"])
                else:
                    print(f"[{index}/{len(rows)}] primary={primary} risk={result['risk_label']}")

    print(f"Classified question rows: {len(rows)}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
