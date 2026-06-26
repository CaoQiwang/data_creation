from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
WIKI_DATA_DIR = WORKSPACE_DIR / "raw_data" / "wiki"
DEFAULT_INPUT = WIKI_DATA_DIR / "pages" / "military_pages_title_strict.jsonl"
DEFAULT_OUTPUT = WORKSPACE_DIR / "chunk_data" / "intermediate" / "wiki" / "wiki_military_title_strict_chunks.jsonl"
DEFAULT_STATS = WORKSPACE_DIR / "chunk_data" / "intermediate" / "wiki" / "wiki_military_title_strict_chunks_stats.json"

SPACE_RE = re.compile(r"[ \t\u3000]+")
HEADING_RE = re.compile(r"^##\s+(.+?)\.?\s*$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])")


def normalize_text(text: str) -> str:
    lines = [SPACE_RE.sub(" ", line).strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_SPLIT_RE.split(text)
    return [part.strip() for part in parts if part.strip()]


def iter_units(text: str) -> Iterable[tuple[str | None, str]]:
    current_section: str | None = None
    buffer: list[str] = []

    def flush() -> Iterable[tuple[str | None, str]]:
        nonlocal buffer
        if buffer:
            unit = "\n".join(buffer).strip()
            buffer = []
            if unit:
                yield current_section, unit

    for line in normalize_text(text).splitlines():
        match = HEADING_RE.match(line)
        if match:
            yield from flush()
            current_section = match.group(1).strip()
            continue
        buffer.append(line)

    yield from flush()


def split_long_text(text: str, max_chars: int) -> list[str]:
    if text_len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in split_sentences(text):
        sentence_len = text_len(sentence)
        if current and current_len + sentence_len > max_chars:
            chunks.append("".join(current).strip())
            current = []
            current_len = 0
        if sentence_len > max_chars:
            for start in range(0, len(sentence), max_chars):
                part = sentence[start : start + max_chars].strip()
                if part:
                    chunks.append(part)
            continue
        current.append(sentence)
        current_len += sentence_len
    if current:
        chunks.append("".join(current).strip())
    return chunks


def merge_units(
    units: Iterable[tuple[str | None, str]],
    min_chars: int,
    target_chars: int,
    max_chars: int,
) -> Iterable[tuple[str | None, str]]:
    pending_text = ""
    pending_section: str | None = None

    def flush() -> Iterable[tuple[str | None, str]]:
        nonlocal pending_text, pending_section
        if text_len(pending_text) >= min_chars:
            for chunk in split_long_text(pending_text.strip(), max_chars):
                if text_len(chunk) >= min_chars:
                    yield pending_section, chunk
        pending_text = ""
        pending_section = None

    for section, unit in units:
        unit_len = text_len(unit)
        if unit_len < min_chars and not pending_text:
            pending_text = unit
            pending_section = section
            continue

        combined = f"{pending_text}\n{unit}".strip() if pending_text else unit
        if pending_text and text_len(combined) > max_chars:
            yield from flush()
            combined = unit
            pending_section = section

        pending_text = combined
        pending_section = pending_section or section

        if text_len(pending_text) >= target_chars:
            yield from flush()

    yield from flush()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def run(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input)
    output_path = Path(args.output)
    stats_path = Path(args.stats)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    page_count = 0
    chunk_count = 0
    skipped_pages = 0
    source_chunk_counts: dict[str, int] = {}
    min_chars_seen: int | None = None
    max_chars_seen = 0
    total_chars = 0

    with output_path.open("w", encoding="utf-8", newline="\n") as out_f:
        for page in iter_jsonl(input_path):
            page_count += 1
            page_id = str(page.get("id") or "")
            title = str(page.get("title") or "")
            url = str(page.get("url") or "")
            source = f"wiki/{title}?curid={page_id}"
            local_chunk_count = 0

            for section, chunk_text in merge_units(
                iter_units(str(page.get("text") or "")),
                min_chars=args.min_chars,
                target_chars=args.target_chars,
                max_chars=args.max_chars,
            ):
                local_chunk_count += 1
                chunk_count += 1
                chars = text_len(chunk_text)
                min_chars_seen = chars if min_chars_seen is None else min(min_chars_seen, chars)
                max_chars_seen = max(max_chars_seen, chars)
                total_chars += chars
                row = {
                    "id": f"wiki/{page_id}#{local_chunk_count:05d}",
                    "text": chunk_text,
                    "source": source,
                    "title": title,
                    "url": url,
                    "site": "wikipedia",
                    "category": "wiki_military_title_strict",
                    "license": str(page.get("license") or "CC BY-SA"),
                    "page_id": page_id,
                    "revid": str(page.get("revid") or ""),
                    "chunk_index": local_chunk_count,
                    "char_count": chars,
                }
                if section:
                    row["section"] = section
                write_jsonl(out_f, row)

            if local_chunk_count:
                source_chunk_counts[title] = local_chunk_count
            else:
                skipped_pages += 1

    stats = {
        "input": str(input_path),
        "output": str(output_path),
        "page_count": page_count,
        "skipped_pages": skipped_pages,
        "chunk_count": chunk_count,
        "min_chars": min_chars_seen or 0,
        "max_chars": max_chars_seen,
        "avg_chars": round(total_chars / chunk_count, 2) if chunk_count else 0,
        "min_chunk_chars_config": args.min_chars,
        "target_chunk_chars_config": args.target_chars,
        "max_chunk_chars_config": args.max_chars,
        "source_document_count": len(source_chunk_counts),
    }
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def write_jsonl(handle: Any, row: dict[str, Any]) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chunk title-strict military Wikipedia pages into project JSONL chunks.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input military wiki pages JSONL.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output chunk JSONL.")
    parser.add_argument("--stats", default=str(DEFAULT_STATS), help="Output stats JSON.")
    parser.add_argument("--min-chars", type=int, default=180, help="Minimum non-space chars per chunk.")
    parser.add_argument("--target-chars", type=int, default=900, help="Target non-space chars per chunk.")
    parser.add_argument("--max-chars", type=int, default=1600, help="Maximum non-space chars per chunk.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    stats = run(args)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
