from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
HTML_RE = re.compile(r"<[^>]+>")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"[ \t\u3000]+")
CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百]+章|附录)\b")
SECTION_RE = re.compile(r"^第[一二三四五六七八九十百]+节\b")
CN_ENUM_RE = re.compile(r"^[一二三四五六七八九十]+[、 ]")
PAREN_ENUM_RE = re.compile(r"^[（(][一二三四五六七八九十]+[）)]")
NUMBER_ENUM_RE = re.compile(r"^\d+[.、 ]")


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    chunk_index: int
    char_count: int


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def normalize_line(line: str) -> str:
    line = IMAGE_RE.sub("", line)
    line = LINK_RE.sub(r"\1", line)
    line = HTML_RE.sub("", line)
    line = CONTROL_RE.sub("", line)
    line = SPACE_RE.sub(" ", line)
    return line.strip()


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def infer_heading_level(
    title: str, markdown_level: int, current_depth: int
) -> int:
    if CHAPTER_RE.match(title):
        return 1
    if SECTION_RE.match(title):
        return 2
    if CN_ENUM_RE.match(title):
        return 3
    if PAREN_ENUM_RE.match(title):
        return 4
    if NUMBER_ENUM_RE.match(title):
        return 5
    if current_depth and markdown_level <= current_depth:
        return min(current_depth + 1, 6)
    return min(markdown_level, 6)


def iter_paragraphs(markdown: str) -> Iterable[tuple[list[str], str]]:
    headings: list[str] = []
    buffer: list[str] = []
    in_code_block = False

    def flush() -> Iterable[tuple[list[str], str]]:
        nonlocal buffer
        paragraph = "\n".join(buffer).strip()
        buffer = []
        if paragraph:
            yield headings.copy(), paragraph

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            yield from flush()
            title = normalize_line(heading_match.group(2))
            if title:
                level = infer_heading_level(
                    title, len(heading_match.group(1)), len(headings)
                )
                headings = headings[: level - 1]
                headings.append(title)
            continue

        normalized = normalize_line(line)
        if not normalized:
            yield from flush()
            continue

        if re.fullmatch(r"[-*_]{3,}", normalized):
            yield from flush()
            continue

        buffer.append(normalized)

    yield from flush()


def split_long_text(text: str, max_chars: int) -> list[str]:
    if text_len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[。！？!?；;])", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
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


def common_heading_prefix(left: list[str], right: list[str]) -> list[str]:
    prefix: list[str] = []
    for left_item, right_item in zip(left, right):
        if left_item != right_item:
            break
        prefix.append(left_item)
    return prefix


def build_chunks(
    md_paths: Iterable[Path],
    raw_root: Path,
    min_chars: int,
    max_chars: int,
    target_chars: int,
    merge_small: bool,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    for path in sorted(md_paths):
        source = path.relative_to(raw_root).as_posix()
        markdown = read_text(path)
        pending_text = ""
        pending_headings: list[str] = []
        source_index = 0

        def emit(text: str, headings: list[str]) -> None:
            nonlocal source_index
            for part in split_long_text(text, max_chars):
                if text_len(part) < min_chars:
                    continue
                source_index += 1
                chunks.append(
                    Chunk(
                        id=f"{source}#{source_index:05d}",
                        text=part,
                        source=source,
                        chunk_index=source_index,
                        char_count=text_len(part),
                    )
                )

        def flush_pending() -> None:
            nonlocal pending_text, pending_headings
            if pending_text and text_len(pending_text) >= min_chars:
                emit(pending_text, pending_headings)
            pending_text = ""
            pending_headings = []

        for headings, paragraph in iter_paragraphs(markdown):
            paragraph_len = text_len(paragraph)

            if merge_small:
                common_headings = (
                    common_heading_prefix(pending_headings, headings)
                    if pending_headings
                    else headings
                )
                same_context = bool(common_headings)
                combined = f"{pending_text}\n{paragraph}".strip()
                combined_len = text_len(combined)

                if pending_text and (not same_context or combined_len > max_chars):
                    flush_pending()
                    combined = paragraph
                    combined_len = paragraph_len
                    common_headings = headings

                pending_text = combined
                pending_headings = common_headings

                if combined_len >= target_chars:
                    flush_pending()
                continue

            if pending_text:
                combined = f"{pending_text}\n{paragraph}".strip()
                combined_headings = pending_headings or headings
                if text_len(combined) <= max_chars:
                    emit(combined, combined_headings)
                    pending_text = ""
                    pending_headings = []
                    continue
                emit(pending_text, pending_headings)
                pending_text = ""
                pending_headings = []

            emit(paragraph, headings)

        flush_pending()

    return chunks


def write_outputs(chunks: list[Chunk], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_dir / "md_paragraph_chunks.jsonl"

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read Markdown files from raw_data, chunk paragraphs, filter short text, and save text chunks."
    )
    parser.add_argument("--input", default="raw_data", help="Input raw data directory.")
    parser.add_argument(
        "--output", default="chunk_data", help="Directory for generated chunk files."
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=80,
        help="Minimum non-whitespace characters for one output chunk.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1800,
        help="Maximum non-whitespace characters for one output chunk.",
    )
    parser.add_argument(
        "--target-chars",
        type=int,
        default=900,
        help="Preferred non-whitespace characters per merged chunk.",
    )
    parser.add_argument(
        "--no-merge-small",
        action="store_true",
        help="Drop short paragraphs directly instead of merging nearby short paragraphs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_root = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not raw_root.exists():
        raise FileNotFoundError(f"Input directory does not exist: {raw_root}")
    if args.min_chars <= 0:
        raise ValueError("--min-chars must be greater than 0")
    if args.max_chars < args.min_chars:
        raise ValueError("--max-chars must be greater than or equal to --min-chars")
    if args.target_chars < args.min_chars:
        raise ValueError("--target-chars must be greater than or equal to --min-chars")
    if args.target_chars > args.max_chars:
        raise ValueError("--target-chars must be less than or equal to --max-chars")

    md_paths = list(raw_root.rglob("*.md"))
    chunks = build_chunks(
        md_paths=md_paths,
        raw_root=raw_root,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        target_chars=args.target_chars,
        merge_small=not args.no_merge_small,
    )
    write_outputs(chunks, output_dir)

    print(f"Markdown files: {len(md_paths)}")
    print(f"Chunks written: {len(chunks)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
