from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
WIKI_DATA_DIR = WORKSPACE_DIR / "raw_data" / "wiki"
DEFAULT_INPUT = WIKI_DATA_DIR / "extracted" / "*.jsonl"
DEFAULT_OUTPUT = WIKI_DATA_DIR / "pages" / "military_pages_title_strict.jsonl"
DEFAULT_REJECTED_SAMPLE = WIKI_DATA_DIR / "pages" / "military_title_strict_rejected_sample.jsonl"
DEFAULT_STATS = WIKI_DATA_DIR / "stats" / "military_title_strict_filter_stats.json"

SPACE_RE = re.compile(r"\s+")

TITLE_KEYWORDS = {
    "军事": 10,
    "军队": 9,
    "军人": 7,
    "军官": 7,
    "士兵": 7,
    "军衔": 8,
    "国防": 10,
    "战争": 9,
    "战役": 9,
    "战斗": 8,
    "作战": 9,
    "战术": 9,
    "战略": 8,
    "兵役": 8,
    "征兵": 8,
    "武器": 8,
    "装备": 7,
    "导弹": 8,
    "火炮": 8,
    "坦克": 8,
    "军舰": 8,
    "舰艇": 8,
    "航空母舰": 9,
    "战斗机": 9,
    "轰炸机": 8,
    "无人机": 7,
    "雷达": 7,
    "陆军": 9,
    "海军": 9,
    "空军": 9,
    "火箭军": 9,
    "宪兵": 7,
    "特种部队": 9,
    "边防": 7,
    "防空": 8,
    "后勤": 6,
    "参谋": 6,
    "情报": 6,
}

BODY_KEYWORDS = {
    "军事": 4,
    "军队": 4,
    "军人": 3,
    "国防": 4,
    "战争": 4,
    "战役": 4,
    "战斗": 3,
    "作战": 4,
    "战术": 4,
    "战略": 3,
    "训练": 2,
    "演习": 3,
    "兵力": 3,
    "部队": 4,
    "武装力量": 5,
    "武器": 4,
    "装备": 3,
    "导弹": 4,
    "舰艇": 4,
    "军舰": 4,
    "坦克": 4,
    "火炮": 4,
    "弹药": 3,
    "飞机": 2,
    "战斗机": 4,
    "雷达": 3,
    "指挥": 3,
    "参谋": 3,
    "情报": 3,
    "侦察": 3,
    "防空": 3,
    "陆军": 4,
    "海军": 4,
    "空军": 4,
    "火箭军": 4,
    "特种部队": 4,
    "军衔": 4,
    "兵役": 4,
    "军校": 3,
    "军事史": 5,
    "军事理论": 5,
    "联合国维和": 4,
    "北约": 3,
    "NATO": 3,
    "DARPA": 3,
}

EXCLUDE_TITLE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"列表$|列表",
        r"消歧义",
        r"模板:",
        r"分类:",
        r"文件:",
        r"Category:",
        r"Template:",
        r"File:",
    ]
]

LOW_VALUE_SECTION_RE = re.compile(
    r"(^|\n)##\s*(参考文献|參考文獻|注释|註釋|外部链接|外部連結|参见|參見|相关条目|相關條目)\.?\s*(\n|$)"
)

RISK_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"(制作|制造|制备).{0,10}(炸药|爆炸物|雷管|燃烧瓶)",
        r"(炸药|爆炸物|雷管|毒剂).{0,10}(配方|合成|教程)",
        r"(规避|绕过).{0,10}(监控|侦察|安检|检测)",
    ]
]


def compact(text: str, max_chars: int = 6000) -> str:
    text = SPACE_RE.sub(" ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def keyword_score(text: str, weights: dict[str, int]) -> tuple[int, list[str]]:
    score = 0
    hits: list[str] = []
    lower = text.lower()
    for keyword, weight in weights.items():
        count = lower.count(keyword.lower())
        if count:
            score += min(count, 5) * weight
            hits.append(keyword)
    return score, sorted(hits)


def strip_low_value_tail(text: str) -> str:
    match = LOW_VALUE_SECTION_RE.search(text)
    if not match:
        return text
    return text[: match.start()].strip()


def classify_page(row: dict[str, Any], min_score: int, body_chars: int, title_min_score: int) -> dict[str, Any]:
    title = str(row.get("title") or "")
    text = str(row.get("text") or "")
    body = compact(text, body_chars)

    excluded_title = any(pattern.search(title) for pattern in EXCLUDE_TITLE_PATTERNS)
    title_score, title_hits = keyword_score(title, TITLE_KEYWORDS)
    body_score, body_hits = keyword_score(body, BODY_KEYWORDS)
    risk_hits = [pattern.pattern for pattern in RISK_PATTERNS if pattern.search(text)]

    score = title_score + body_score
    if excluded_title:
        score -= 20
    if risk_hits:
        score -= 20

    title_ok = title_score >= title_min_score
    keep = score >= min_score and title_ok and not excluded_title and not risk_hits
    return {
        "keep": keep,
        "score": score,
        "title_score": title_score,
        "body_score": body_score,
        "title_hits": title_hits,
        "body_hits": body_hits[:30],
        "title_ok": title_ok,
        "excluded_title": excluded_title,
        "risk_hits": risk_hits,
        "reason": "军事关键词命中，页面主题相关" if keep else "军事相关性不足或命中排除规则",
    }


def iter_jsonl_files(pattern: str) -> Any:
    for path in sorted(glob.glob(pattern)):
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield path, line_no, json.loads(line)
                except json.JSONDecodeError:
                    continue


def write_row(handle: Any, row: dict[str, Any]) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    rejected_sample = Path(args.rejected_sample)
    stats_path = Path(args.stats)
    output.parent.mkdir(parents=True, exist_ok=True)
    rejected_sample.parent.mkdir(parents=True, exist_ok=True)

    total = kept = rejected = 0
    score_buckets: Counter[str] = Counter()
    title_hit_counts: Counter[str] = Counter()
    body_hit_counts: Counter[str] = Counter()
    rejected_written = 0

    with output.open("w", encoding="utf-8", newline="\n") as out_f, rejected_sample.open(
        "w", encoding="utf-8", newline="\n"
    ) as rej_f:
        for _path, _line_no, row in iter_jsonl_files(args.input):
            total += 1
            result = classify_page(row, args.min_score, args.body_chars, args.title_min_score)
            score_buckets[str(min(max(result["score"], 0), 99) // 5 * 5)] += 1

            if result["keep"]:
                kept += 1
                text = strip_low_value_tail(str(row.get("text") or ""))
                row["text"] = text
                row["source_type"] = "wiki_military_page"
                row["wiki_military_filter"] = result
                for hit in result["title_hits"]:
                    title_hit_counts[hit] += 1
                for hit in result["body_hits"]:
                    body_hit_counts[hit] += 1
                write_row(out_f, row)
            else:
                rejected += 1
                if rejected_written < args.rejected_sample_size:
                    row["wiki_military_filter"] = result
                    write_row(rej_f, row)
                    rejected_written += 1

    stats = {
        "input": args.input,
        "output": str(output),
        "rejected_sample": str(rejected_sample),
        "total_pages": total,
        "kept_pages": kept,
        "rejected_pages": rejected,
        "keep_rate": round(kept / total, 4) if total else 0.0,
        "min_score": args.min_score,
        "title_min_score": args.title_min_score,
        "body_chars": args.body_chars,
        "top_title_hits": dict(title_hit_counts.most_common(50)),
        "top_body_hits": dict(body_hit_counts.most_common(50)),
        "score_buckets": dict(sorted(score_buckets.items(), key=lambda item: int(item[0]))),
    }
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Filter extracted Chinese Wikipedia pages for military-related topics.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input JSONL glob from extracted wiki pages.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Kept military pages JSONL.")
    parser.add_argument("--rejected-sample", default=str(DEFAULT_REJECTED_SAMPLE), help="Small rejected sample JSONL.")
    parser.add_argument("--stats", default=str(DEFAULT_STATS), help="Stats JSON path.")
    parser.add_argument("--min-score", type=int, default=12, help="Minimum weighted keyword score to keep a page.")
    parser.add_argument(
        "--title-min-score",
        type=int,
        default=7,
        help="Minimum title keyword score. Use 0 for recall-first broad filtering.",
    )
    parser.add_argument("--body-chars", type=int, default=6000, help="Only score this many leading body chars.")
    parser.add_argument("--rejected-sample-size", type=int, default=200, help="Number of rejected rows to sample.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    stats = run(args)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
