#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build unified v2 chunk_data from current raw/intermediate sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TXT_ROOT = ROOT / "raw_data" / "txt"
DEFAULT_MD_ROOT = ROOT / "raw_data" / "md_from_pdf"
DEFAULT_PDF_GFK = ROOT / "chunk_data" / "intermediate" / "pdf_guofang_keji" / "pdf_paragraph_chunks.jsonl"
DEFAULT_PDF_JSL = ROOT / "chunk_data" / "intermediate" / "pdf_junshi_lishi" / "pdf_paragraph_chunks.jsonl"
DEFAULT_WIKI = ROOT / "chunk_data" / "intermediate" / "wiki" / "wiki_military_title_strict_prefiltered_chunks.jsonl"
DEFAULT_OUT = ROOT / "chunk_data" / "v2_chunks.jsonl"
DEFAULT_STATS = ROOT / "chunk_data" / "v2_chunks_stats.json"

MOJIBAKE_RE = re.compile(r"[锛鍐鏂閲勬槸绋簨鐨瑙规垬艰粛浜軍€俓]")
COMMON_CN_RE = re.compile(r"[的一是在和了有中国军事军队战争国防装备人民]")
SPACE_RE = re.compile(r"[ \t\u3000]+")
BLANK_RE = re.compile(r"\n{3,}")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；!?;])")
REF_HEADING_RE = re.compile(r"^\s*(参考文献|主要参考文献|References?|Bibliography)\s*[:：]?\s*$", re.I)


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def mojibake_score(text: str) -> int:
    if not text:
        return 0
    return len(MOJIBAKE_RE.findall(text)) - len(COMMON_CN_RE.findall(text)) // 8


def repair_mojibake(text: str) -> str:
    """Repair common UTF-8-as-GBK mojibake when it clearly improves text."""
    if mojibake_score(text) < 4:
        return text
    candidates: list[str] = []
    for enc in ("gb18030", "gbk"):
        try:
            candidates.append(text.encode(enc).decode("utf-8"))
        except UnicodeError:
            try:
                candidates.append(text.encode(enc, errors="ignore").decode("utf-8", errors="ignore"))
            except UnicodeError:
                pass
    candidates = [c for c in candidates if c and len(c) > len(text) * 0.65]
    if not candidates:
        return text
    best = min(candidates, key=mojibake_score)
    if mojibake_score(best) + 3 < mojibake_score(text):
        return best
    return text


def clean_text(text: str) -> str:
    text = repair_mojibake(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "")
    text = SPACE_RE.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)
    return BLANK_RE.sub("\n\n", text).strip()


def strip_references(text: str) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if REF_HEADING_RE.match(line.strip()):
            kept = "\n".join(lines[:idx]).strip()
            if len(kept) >= 100:
                return kept
    return text


def paragraphs(text: str) -> list[str]:
    text = strip_references(clean_text(text))
    parts = re.split(r"\n\s*\n", text)
    if len(parts) == 1:
        parts = re.split(r"\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 20]


def split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current = ""
    for sent in SENTENCE_SPLIT_RE.split(text):
        sent = sent.strip()
        if not sent:
            continue
        if current and len(current) + len(sent) > max_chars:
            pieces.append(current.strip())
            current = sent
        else:
            current = f"{current}{sent}" if current else sent
    if current:
        pieces.append(current.strip())
    final: list[str] = []
    for piece in pieces or [text]:
        if len(piece) <= max_chars:
            final.append(piece)
        else:
            final.extend(piece[i : i + max_chars] for i in range(0, len(piece), max_chars))
    return final


def merge_paragraphs(parts: Iterable[str], target_chars: int, max_chars: int, min_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in parts:
        for piece in split_long(para, max_chars):
            piece_len = len(piece)
            if current and current_len + piece_len + 2 > max_chars:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_len = 0
            current.append(piece)
            current_len += piece_len + 2
            if current_len >= target_chars:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_len = 0
    if current:
        chunks.append("\n\n".join(current).strip())
    return [c for c in chunks if len(c) >= min_chars]


def norm_hash(text: str) -> str:
    norm = re.sub(r"\s+", "", text)
    return hashlib.sha1(norm.encode("utf-8", errors="ignore")).hexdigest()


def iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def make_chunk(
    *,
    chunk_id: str,
    text: str,
    dataset_source: str,
    source: str,
    title: str,
    chunk_index: int,
    extra: dict | None = None,
) -> dict:
    row = {
        "id": chunk_id,
        "text": text,
        "source": source,
        "title": title,
        "chunk_index": chunk_index,
        "char_count": len(text),
        "dataset_version": "v2",
        "dataset_source": dataset_source,
    }
    if extra:
        for key, value in extra.items():
            if key not in row and value not in (None, ""):
                row[key] = value
    return row


def iter_raw_files(root: Path, suffixes: tuple[str, ...], dataset_source: str, args: argparse.Namespace) -> Iterable[dict]:
    if not root.exists():
        return
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes):
        rel = path.relative_to(ROOT).as_posix()
        text = read_text(path)
        parts = paragraphs(text)
        chunks = merge_paragraphs(parts, args.target_chars, args.max_chars, args.min_chars)
        title = path.stem
        for idx, chunk_text in enumerate(chunks, 1):
            yield make_chunk(
                chunk_id=f"{dataset_source}/{rel}#{idx:05d}",
                text=chunk_text,
                source=rel,
                title=title,
                chunk_index=idx,
                dataset_source=dataset_source,
                extra={"file_path": rel},
            )


def iter_existing_jsonl(path: Path, dataset_source: str, prefix: str, min_chars: int) -> Iterable[dict]:
    for idx, row in enumerate(iter_jsonl(path), 1):
        text = clean_text(str(row.get("text", "")))
        if len(text) < min_chars:
            continue
        source = clean_text(str(row.get("source") or row.get("url") or path.as_posix()))
        title = clean_text(str(row.get("title") or Path(source).stem or dataset_source))
        extra = {
            "url": row.get("url"),
            "site": row.get("site"),
            "category": row.get("category"),
            "license": row.get("license"),
            "page_id": row.get("page_id"),
            "revid": row.get("revid"),
            "page_start": row.get("page_start"),
            "page_end": row.get("page_end"),
            "original_id": row.get("id"),
        }
        yield make_chunk(
            chunk_id=f"{prefix}#{idx:06d}",
            text=text,
            source=source,
            title=title,
            chunk_index=int(row.get("chunk_index") or idx),
            dataset_source=dataset_source,
            extra=extra,
        )


def build(args: argparse.Namespace) -> dict:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    stats = {
        "dataset_version": "v2",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "output": args.output.as_posix(),
        "sources": {},
        "total_chunks": 0,
        "total_chars": 0,
        "duplicates_skipped": 0,
        "too_short_skipped": 0,
    }
    source_counts: Counter[str] = Counter()
    source_chars: Counter[str] = Counter()
    examples: defaultdict[str, list[str]] = defaultdict(list)

    streams = [
        iter_raw_files(args.txt_root, (".txt",), "raw_txt_v2", args),
        iter_raw_files(args.md_root, (".md", ".markdown"), "raw_md_v2", args),
        iter_existing_jsonl(args.pdf_guofang_keji, "pdf_guofang_keji_v2", "pdf_gfk", args.min_chars),
        iter_existing_jsonl(args.pdf_junshi_lishi, "pdf_junshi_lishi_v2", "pdf_jsl", args.min_chars),
    ]
    if args.include_wiki:
        streams.append(iter_existing_jsonl(args.wiki, "wiki_military_title_strict_v2", "wiki", args.min_chars))

    with args.output.open("w", encoding="utf-8", newline="\n") as out:
        for stream in streams:
            for row in stream:
                text = row["text"]
                if len(text) < args.min_chars:
                    stats["too_short_skipped"] += 1
                    continue
                h = norm_hash(text)
                if h in seen:
                    stats["duplicates_skipped"] += 1
                    continue
                seen.add(h)
                src = row["dataset_source"]
                source_counts[src] += 1
                source_chars[src] += len(text)
                if len(examples[src]) < 3:
                    examples[src].append(row["id"])
                stats["total_chunks"] += 1
                stats["total_chars"] += len(text)
                out.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats["sources"] = {
        src: {"chunks": source_counts[src], "chars": source_chars[src], "examples": examples[src]}
        for src in sorted(source_counts)
    }
    stats["dedupe_hashes"] = len(seen)
    args.stats_output.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--txt-root", type=Path, default=DEFAULT_TXT_ROOT)
    parser.add_argument("--md-root", type=Path, default=DEFAULT_MD_ROOT)
    parser.add_argument("--pdf-guofang-keji", type=Path, default=DEFAULT_PDF_GFK)
    parser.add_argument("--pdf-junshi-lishi", type=Path, default=DEFAULT_PDF_JSL)
    parser.add_argument("--wiki", type=Path, default=DEFAULT_WIKI)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--stats-output", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--min-chars", type=int, default=80)
    parser.add_argument("--target-chars", type=int, default=900)
    parser.add_argument("--max-chars", type=int, default=1800)
    parser.add_argument("--include-wiki", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    args.txt_root = args.txt_root.resolve()
    args.md_root = args.md_root.resolve()
    args.pdf_guofang_keji = args.pdf_guofang_keji.resolve()
    args.pdf_junshi_lishi = args.pdf_junshi_lishi.resolve()
    args.wiki = args.wiki.resolve()
    args.output = args.output.resolve()
    args.stats_output = args.stats_output.resolve()
    return args


def main() -> None:
    stats = build(parse_args())
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
