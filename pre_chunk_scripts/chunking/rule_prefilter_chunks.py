from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


DEFAULT_INPUT = Path("chunk_data/intermediate/base/all_text_chunks.jsonl")
DEFAULT_OUTPUT = Path("chunk_data/intermediate/rule_prefilter/rule_prefiltered_chunks.jsonl")
DEFAULT_REJECTED = Path("chunk_data/intermediate/rule_prefilter/rule_rejected_chunks.jsonl")
DEFAULT_STATS = Path("chunk_data/intermediate/rule_prefilter/rule_prefilter_stats.json")

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"\d")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"\s+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

MILITARY_KEYWORDS = {
    "军事",
    "军队",
    "军人",
    "军兵种",
    "国防",
    "武装",
    "战争",
    "战役",
    "战斗",
    "作战",
    "战场",
    "战术",
    "战略",
    "训练",
    "演习",
    "兵力",
    "部队",
    "装备",
    "武器",
    "导弹",
    "舰艇",
    "飞机",
    "雷达",
    "火炮",
    "弹药",
    "后勤",
    "指挥",
    "情报",
    "侦察",
    "防空",
    "海军",
    "陆军",
    "空军",
    "火箭军",
    "联合作战",
    "国家安全",
    "安全形势",
    "边防",
    "维和",
    "反恐",
    "DARPA",
    "NATO",
    "北约",
}

LOW_VALUE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^\s*(目录|目\s*录|contents)\s*$",
        r"^\s*(参考文献|references|bibliography)\s*$",
        r"版权所有|copyright|免责声明",
        r"扫一扫|关注公众号|点击下载|返回顶部",
        r"第\s*\d+\s*页\s*/\s*共\s*\d+\s*页",
    ]
]

REFERENCE_HEADING_RE = re.compile(
    r"(^|\n)\s*(参考文献|主要参考文献|参考资料|references|bibliography|works cited)\s*[:：]?\s*(\n|$)",
    re.IGNORECASE,
)

REFERENCE_LINE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^\s*(\[\s*\d+\s*\]|\d+\s*[.．、])\s*\S+",
        r"\bdoi\s*[:：]?\s*10\.\d{4,9}/",
        r"\[[JMNCDRSP]\]",
        r"\b(et\s+al\.|ibid\.|vol\.|no\.|pp\.)\b",
        r"\b(issn|isbn)\b",
        r"https?://|www\.",
        r"\d{4}\s*[,，]\s*\d+\s*[(（]\s*\d+\s*[)）]\s*[:：]\s*\d+\s*[-－]\s*\d+",
        r"\d{4}\s*[,，]\s*\d+\s*[:：]\s*\d+\s*[-－]\s*\d+",
    ]
]

ACTIONABLE_RISK_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"制作.{0,8}(炸药|爆炸物|雷管|燃烧瓶)",
        r"(炸药|爆炸物|雷管|毒剂).{0,8}(配方|制备|合成|制作)",
        r"(绕过|规避).{0,8}(监控|安检|侦察|检测)",
        r"(暗杀|投毒|破坏).{0,12}(步骤|流程|方法|教程)",
    ]
]

# These tokens are frequent in UTF-8/GBK mojibake, but uncommon in clean Chinese
# prose when they appear densely together.
MOJIBAKE_TOKENS = [
    "鈥",
    "銆",
    "鍥",
    "涓",
    "涔",
    "绋",
    "鐨",
    "戠",
    "嗗",
    "嬫",
    "槸",
    "",
    "€",
    "\ufffd",
]


def compact_space(text: str) -> str:
    return SPACE_RE.sub(" ", text).strip()


def stable_text_hash(text: str) -> str:
    normalized = compact_space(text).lower()
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()


def count_pattern_hits(patterns: list[re.Pattern[str]], text: str) -> int:
    return sum(1 for pattern in patterns if pattern.search(text))


def longest_repeated_char_run(text: str) -> int:
    if not text:
        return 0
    best = 1
    current = 1
    prev = text[0]
    for ch in text[1:]:
        if ch == prev:
            current += 1
            best = max(best, current)
        else:
            current = 1
            prev = ch
    return best


def duplicate_line_ratio(text: str) -> float:
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 8]
    if len(lines) < 4:
        return 0.0
    counts = Counter(lines)
    repeated = sum(count for count in counts.values() if count > 1)
    return repeated / len(lines)


def reference_stats(text: str) -> tuple[bool, int, int, float]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False, 0, 0, 0.0

    ref_heading = bool(REFERENCE_HEADING_RE.search(text))
    reference_like = 0
    for line in lines:
        if any(pattern.search(line) for pattern in REFERENCE_LINE_PATTERNS):
            reference_like += 1

    return ref_heading, reference_like, len(lines), reference_like / len(lines)


def keyword_hits(text: str) -> list[str]:
    text_lower = text.lower()
    hits: list[str] = []
    for keyword in MILITARY_KEYWORDS:
        if keyword.lower() in text_lower:
            hits.append(keyword)
    return sorted(hits)


def detect_mojibake(text: str) -> tuple[int, float, list[str]]:
    hits = {token: text.count(token) for token in MOJIBAKE_TOKENS if token in text}
    hit_count = sum(hits.values())
    density = hit_count / max(len(text), 1)
    return hit_count, density, sorted(hits)


def score_row(row: dict[str, Any], seen_hashes: set[str], args: argparse.Namespace) -> dict[str, Any]:
    text = str(row.get("text") or "")
    source = str(row.get("source") or "")
    text_hash = stable_text_hash(text)
    char_count = len(text)
    compact = compact_space(text)
    compact_len = len(compact)
    chinese_count = len(CHINESE_RE.findall(text))
    latin_count = len(LATIN_RE.findall(text))
    digit_count = len(DIGIT_RE.findall(text))
    control_count = len(CONTROL_RE.findall(text))
    pua_count = sum(1 for ch in text if "\ue000" <= ch <= "\uf8ff")
    url_count = len(URL_RE.findall(text))
    repeated_run = longest_repeated_char_run(text)
    repeated_lines = duplicate_line_ratio(text)
    low_value_hits = count_pattern_hits(LOW_VALUE_PATTERNS, text)
    risk_hits = count_pattern_hits(ACTIONABLE_RISK_PATTERNS, text)
    ref_heading, ref_line_count, line_count, ref_line_ratio = reference_stats(text)
    mojibake_count, mojibake_density, mojibake_tokens = detect_mojibake(text)
    military_hits = keyword_hits(text + "\n" + source)

    non_space_len = max(len(text.replace(" ", "").replace("\n", "").replace("\t", "")), 1)
    chinese_ratio = chinese_count / non_space_len
    latin_ratio = latin_count / non_space_len
    digit_ratio = digit_count / non_space_len
    unique_ratio = len(set(compact)) / max(compact_len, 1)

    score = 10.0
    issues: list[str] = []
    fatal = False

    if char_count < args.min_chars:
        score -= 5.0
        issues.append("too_short")
        fatal = True
    elif char_count < args.soft_min_chars:
        score -= 2.0
        issues.append("short_text")

    if char_count > args.max_chars:
        score -= 1.0
        issues.append("too_long")

    if not compact:
        score = 0.0
        issues.append("empty_text")
        fatal = True

    if control_count:
        score -= min(3.0, control_count * 0.5)
        issues.append("control_chars")

    if pua_count:
        score -= min(6.0, pua_count * 0.2)
        issues.append("private_use_chars")
        if pua_count >= args.max_pua_chars:
            fatal = True

    if mojibake_density >= args.max_mojibake_density or mojibake_count >= args.max_mojibake_hits:
        score -= 6.0
        issues.append("suspected_mojibake")
        fatal = True
    elif mojibake_count:
        score -= min(2.0, mojibake_count * 0.05)
        issues.append("possible_mojibake")

    if chinese_ratio < args.min_chinese_ratio and latin_ratio < 0.55:
        score -= 2.0
        issues.append("low_chinese_ratio")

    if digit_ratio > args.max_digit_ratio:
        score -= 1.5
        issues.append("digit_heavy")

    if unique_ratio < args.min_unique_ratio:
        score -= 2.0
        issues.append("low_unique_char_ratio")

    if repeated_run >= args.max_repeated_char_run:
        score -= 2.0
        issues.append("repeated_char_noise")

    if repeated_lines >= args.max_duplicate_line_ratio:
        score -= 2.0
        issues.append("duplicate_line_noise")

    if low_value_hits:
        score -= min(3.0, low_value_hits * 1.0)
        issues.append("low_value_boilerplate")

    if ref_heading and ref_line_count >= args.min_reference_lines:
        score -= 6.0
        issues.append("reference_section")
        fatal = True
    elif ref_line_count >= args.min_reference_lines and ref_line_ratio >= args.max_reference_line_ratio:
        score -= 5.0
        issues.append("reference_like_list")
        fatal = True
    elif ref_line_count >= 2 and ref_line_ratio >= 0.6:
        score -= 2.0
        issues.append("reference_heavy")

    if url_count >= args.max_urls:
        score -= 1.0
        issues.append("url_heavy")

    if not military_hits:
        score -= args.non_military_penalty
        issues.append("weak_military_relevance")

    if risk_hits:
        score -= 6.0
        issues.append("actionable_harm_risk")
        fatal = True

    if args.dedupe and text_hash in seen_hashes:
        score -= 5.0
        issues.append("duplicate_text")
        fatal = True

    score = max(0.0, min(10.0, score))
    keep = (score >= args.min_score) and not fatal

    if keep and args.dedupe:
        seen_hashes.add(text_hash)

    if score >= 8:
        quality_level = "good"
    elif score >= 5:
        quality_level = "usable"
    elif score >= 3:
        quality_level = "poor"
    else:
        quality_level = "reject"

    return {
        "keep": keep,
        "score": round(score, 2),
        "quality_level": quality_level,
        "issues": issues,
        "reason": build_reason(keep, issues, military_hits),
        "metrics": {
            "char_count": char_count,
            "chinese_ratio": round(chinese_ratio, 4),
            "latin_ratio": round(latin_ratio, 4),
            "digit_ratio": round(digit_ratio, 4),
            "unique_ratio": round(unique_ratio, 4),
            "control_count": control_count,
            "private_use_char_count": pua_count,
            "mojibake_count": mojibake_count,
            "mojibake_density": round(mojibake_density, 4),
            "mojibake_tokens": mojibake_tokens[:12],
            "repeated_char_run": repeated_run,
            "duplicate_line_ratio": round(repeated_lines, 4),
            "reference_heading": ref_heading,
            "reference_line_count": ref_line_count,
            "line_count": line_count,
            "reference_line_ratio": round(ref_line_ratio, 4),
            "url_count": url_count,
            "military_keyword_hits": military_hits[:20],
        },
    }


def build_reason(keep: bool, issues: list[str], military_hits: list[str]) -> str:
    if keep:
        if military_hits:
            return "规则初筛通过：文本长度、噪声和军事相关性满足要求。"
        return "规则初筛通过：整体质量可用，但军事关键词较弱，建议后续复核。"
    if not issues:
        return "规则初筛未通过：综合分低于阈值。"
    return "规则初筛未通过：" + "、".join(issues[:5])


def iter_jsonl(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_no, {
                    "id": f"__invalid_json_line_{line_no}",
                    "text": "",
                    "source": str(path),
                    "rule_prefilter_parse_error": str(exc),
                }


def write_jsonl_row(handle: Any, row: dict[str, Any]) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input)
    output_path = Path(args.output)
    rejected_path = Path(args.rejected)
    stats_path = Path(args.stats)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    seen_hashes: set[str] = set()
    issue_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    score_buckets: Counter[str] = Counter()
    total = kept = rejected = 0

    rows = iter_jsonl(input_path)
    if tqdm is not None and not args.no_progress:
        rows = tqdm(rows, desc="rule prefilter", unit="row")

    with output_path.open("w", encoding="utf-8", newline="\n") as kept_f, rejected_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as rejected_f:
        for _, row in rows:
            total += 1
            result = score_row(row, seen_hashes, args)
            row["rule_prefilter"] = result

            for issue in result["issues"]:
                issue_counts[issue] += 1
            source_counts[str(row.get("source", "")).split("/")[0].split("\\")[0]] += 1
            score_buckets[str(int(result["score"] // 1))] += 1

            if result["keep"]:
                kept += 1
                write_jsonl_row(kept_f, row)
            else:
                rejected += 1
                write_jsonl_row(rejected_f, row)

    stats = {
        "input": str(input_path),
        "output": str(output_path),
        "rejected_output": str(rejected_path),
        "total": total,
        "kept": kept,
        "rejected": rejected,
        "keep_rate": round(kept / total, 4) if total else 0.0,
        "min_score": args.min_score,
        "issue_counts": dict(issue_counts.most_common()),
        "source_prefix_counts": dict(source_counts.most_common()),
        "score_buckets": dict(sorted(score_buckets.items(), key=lambda item: int(item[0]))),
    }
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rule-based first-pass filter for chunk_data JSONL files.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input JSONL path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Kept JSONL output path.")
    parser.add_argument("--rejected", default=str(DEFAULT_REJECTED), help="Rejected JSONL output path.")
    parser.add_argument("--stats", default=str(DEFAULT_STATS), help="Stats JSON output path.")
    parser.add_argument("--min-score", type=float, default=5.0, help="Minimum rule score to keep a chunk.")
    parser.add_argument("--min-chars", type=int, default=120, help="Hard minimum text length.")
    parser.add_argument("--soft-min-chars", type=int, default=260, help="Soft minimum text length.")
    parser.add_argument("--max-chars", type=int, default=5000, help="Text length above this is penalized.")
    parser.add_argument("--min-chinese-ratio", type=float, default=0.25, help="Minimum Chinese character ratio.")
    parser.add_argument("--max-digit-ratio", type=float, default=0.35, help="Maximum digit ratio before penalty.")
    parser.add_argument("--min-unique-ratio", type=float, default=0.035, help="Minimum unique character ratio.")
    parser.add_argument("--max-repeated-char-run", type=int, default=12, help="Maximum repeated char run.")
    parser.add_argument("--max-duplicate-line-ratio", type=float, default=0.35, help="Maximum duplicate line ratio.")
    parser.add_argument("--max-urls", type=int, default=4, help="Maximum URL count before penalty.")
    parser.add_argument(
        "--min-reference-lines",
        type=int,
        default=4,
        help="Minimum citation-like lines before rejecting a reference section/list.",
    )
    parser.add_argument(
        "--max-reference-line-ratio",
        type=float,
        default=0.45,
        help="Reject when citation-like lines reach this ratio and min-reference-lines is met.",
    )
    parser.add_argument("--max-pua-chars", type=int, default=5, help="Private-use chars at/above this are fatal.")
    parser.add_argument("--max-mojibake-hits", type=int, default=12, help="Mojibake token count at/above this is fatal.")
    parser.add_argument(
        "--max-mojibake-density",
        type=float,
        default=0.012,
        help="Mojibake token density at/above this is fatal.",
    )
    parser.add_argument("--non-military-penalty", type=float, default=3.0, help="Penalty for weak military relevance.")
    parser.add_argument("--dedupe", action=argparse.BooleanOptionalAction, default=True, help="Drop duplicate text.")
    parser.add_argument("--no-progress", action="store_true", help="Disable tqdm progress bar.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    stats = run(args)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
