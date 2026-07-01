#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert filtered QA data into ms-swift messages-format SFT JSONL."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert final filtered QA JSONL to ms-swift SFT messages format."
    )
    parser.add_argument("--input", required=True, help="Filtered QA JSONL path.")
    parser.add_argument("--output", required=True, help="Output ms-swift JSONL path.")
    parser.add_argument(
        "--stats-output",
        default="",
        help="Optional stats JSON path. Defaults to <output>.stats.json.",
    )
    parser.add_argument(
        "--system",
        default="",
        help="Optional system prompt to prepend to every sample.",
    )
    parser.add_argument(
        "--include-metadata",
        action="store_true",
        help="Keep lightweight metadata in output rows. Default output only has messages.",
    )
    parser.add_argument(
        "--include-bad-status",
        action="store_true",
        help="Include rows whose question/answer/eval status is not ok.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_no}")
            rows.append(obj)
    return rows


def nested_get(row: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    cur: Any = row
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def row_status_ok(row: dict[str, Any]) -> bool:
    status_paths = (
        ("sft_question", "status"),
        ("sft_question_eval", "status"),
        ("sft_answer", "status"),
        ("sft_answer_eval", "status"),
    )
    for path in status_paths:
        status = nested_get(row, path)
        if status not in (None, "", "ok"):
            return False
    answer_eval = nested_get(row, ("sft_answer_eval",), {})
    if isinstance(answer_eval, dict) and answer_eval.get("pass_filter") is False:
        return False
    question_eval = nested_get(row, ("sft_question_eval",), {})
    if isinstance(question_eval, dict) and question_eval.get("pass_filter") is False:
        return False
    return True


def build_output_row(
    row: dict[str, Any],
    question: str,
    answer: str,
    system_prompt: str,
    include_metadata: bool,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(
        [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    )

    out: dict[str, Any] = {"messages": messages}
    if include_metadata:
        out["metadata"] = {
            "id": row.get("id", ""),
            "material_id": row.get("material_id", ""),
            "source": row.get("source", ""),
            "category": row.get("category", ""),
            "question_type": nested_get(row, ("sft_question", "question_type"), ""),
            "question_score": nested_get(row, ("sft_question_eval", "score"), None),
            "answer_score": nested_get(row, ("sft_answer_eval", "score"), None),
            "taxonomy_label_id": nested_get(row, ("sft_question_taxonomy_labels", "primary", "id"), ""),
            "taxonomy_label_path": nested_get(row, ("sft_question_taxonomy_labels", "primary", "path"), []),
            "taxonomy_confidence": nested_get(row, ("sft_question_taxonomy_labels", "confidence"), None),
        }
    return out


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    stats_path = (
        Path(args.stats_output)
        if args.stats_output
        else output_path.with_suffix(".stats.json")
    )

    rows = load_jsonl(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    counters: dict[str, Counter[str]] = {
        "skip_reason": Counter(),
        "question_type": Counter(),
        "answer_score": Counter(),
        "question_score": Counter(),
    }

    written = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            question = clean_text(nested_get(row, ("sft_question", "question")))
            answer = clean_text(nested_get(row, ("sft_answer", "answer")))

            if not question:
                counters["skip_reason"]["missing_question"] += 1
                continue
            if not answer:
                counters["skip_reason"]["missing_answer"] += 1
                continue
            if not args.include_bad_status and not row_status_ok(row):
                counters["skip_reason"]["bad_status"] += 1
                continue

            out = build_output_row(
                row=row,
                question=question,
                answer=answer,
                system_prompt=args.system.strip(),
                include_metadata=args.include_metadata,
            )
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            written += 1

            qtype = clean_text(nested_get(row, ("sft_question", "question_type"), "unknown"))
            ascore = clean_text(nested_get(row, ("sft_answer_eval", "score"), "unknown"))
            qscore = clean_text(nested_get(row, ("sft_question_eval", "score"), "unknown"))
            counters["question_type"][qtype or "unknown"] += 1
            counters["answer_score"][ascore or "unknown"] += 1
            counters["question_score"][qscore or "unknown"] += 1

    stats = {
        "input": str(input_path),
        "output": str(output_path),
        "total_rows": len(rows),
        "written_rows": written,
        "skipped_rows": len(rows) - written,
        "skip_reason_counts": dict(counters["skip_reason"]),
        "question_type_counts": dict(counters["question_type"]),
        "answer_score_counts": dict(counters["answer_score"]),
        "question_score_counts": dict(counters["question_score"]),
        "format": "ms-swift messages jsonl",
        "system_prompt_included": bool(args.system.strip()),
        "metadata_included": bool(args.include_metadata),
    }
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Input rows:     {len(rows)}")
    print(f"Written rows:   {written}")
    print(f"Skipped rows:   {len(rows) - written}")
    print(f"Output:         {output_path}")
    print(f"Stats:          {stats_path}")


if __name__ == "__main__":
    main()
