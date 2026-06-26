from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"[ \t\u3000]+")
HTML_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")
SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")
CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百]+[章节]|[一二三四五六七八九十]+[、.])")
PAREN_ENUM_RE = re.compile(r"^[（(][一二三四五六七八九十]+[）)]")
SPEAKER_RE = re.compile(
    r"(记者|问|答|发言人|主持人|国防部新闻发言人|张晓刚|吴谦|蒋斌|谭克非|任国强|杨宇军)\s*[：:]"
)


@dataclass
class TxtChunk:
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


def normalize_text(text: str) -> str:
    text = HTML_RE.sub("", text)
    text = URL_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]


def split_speaker_turns(text: str) -> list[str]:
    matches = list(SPEAKER_RE.finditer(text))
    if len(matches) < 2:
        return []

    turns: list[str] = []
    prefix = text[: matches[0].start()].strip()
    if prefix:
        turns.append(prefix)

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        turn = text[match.start() : end].strip()
        if turn:
            turns.append(turn)

    return turns


def infer_section(line: str) -> str | None:
    candidate = line.strip()
    if not candidate:
        return None
    if len(candidate) > 80:
        return None
    if CHAPTER_RE.match(candidate) or PAREN_ENUM_RE.match(candidate):
        return candidate
    if candidate in {"目录", "前言", "结束语", "附录", "思考题"}:
        return candidate
    return None


def iter_units(text: str) -> Iterable[tuple[str | None, str]]:
    current_section: str | None = None
    paragraph_buffer: list[str] = []
    in_toc = False

    def flush_buffer() -> Iterable[tuple[str | None, str]]:
        nonlocal paragraph_buffer
        paragraph = "\n".join(paragraph_buffer).strip()
        paragraph_buffer = []
        if paragraph:
            turns = split_speaker_turns(paragraph)
            if turns:
                for turn in turns:
                    yield current_section, turn
            else:
                yield current_section, paragraph

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            yield from flush_buffer()
            continue

        if line == "目录":
            yield from flush_buffer()
            in_toc = True
            continue

        section = infer_section(line)
        if in_toc:
            if section and line != "目录":
                in_toc = False
                current_section = section
                continue
            continue
        if section:
            yield from flush_buffer()
            current_section = section
            continue

        paragraph_buffer.append(line)

    yield from flush_buffer()


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
            yield pending_section, pending_text.strip()
        pending_text = ""
        pending_section = None

    for section, unit in units:
        if text_len(unit) < min_chars and not pending_text:
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


def build_chunks(
    txt_paths: Iterable[Path],
    input_root: Path,
    min_chars: int,
    target_chars: int,
    max_chars: int,
) -> list[TxtChunk]:
    chunks: list[TxtChunk] = []

    for path in sorted(txt_paths):
        source = path.relative_to(input_root).as_posix()
        text = normalize_text(read_text(path))
        chunk_index = 0

        for _section, merged_text in merge_units(
            iter_units(text),
            min_chars=min_chars,
            target_chars=target_chars,
            max_chars=max_chars,
        ):
            for part in split_long_text(merged_text, max_chars):
                if text_len(part) < min_chars:
                    continue
                chunk_index += 1
                chunks.append(
                    TxtChunk(
                        id=f"{source}#{chunk_index:05d}",
                        text=part,
                        source=source,
                        chunk_index=chunk_index,
                        char_count=text_len(part),
                    )
                )

        if chunk_index == 0 and text_len(text) >= min_chars:
            for part in split_long_text(text, max_chars):
                if text_len(part) < min_chars:
                    continue
                chunk_index += 1
                chunks.append(
                    TxtChunk(
                        id=f"{source}#{chunk_index:05d}",
                        text=part,
                        source=source,
                        chunk_index=chunk_index,
                        char_count=text_len(part),
                    )
                )

    return chunks


def write_outputs(chunks: list[TxtChunk], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_dir / "txt_structured_chunks.jsonl"

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert raw TXT files into structured chunk data."
    )
    parser.add_argument(
        "--input",
        default="raw_data/txt",
        help="Input TXT directory.",
    )
    parser.add_argument(
        "--output",
        default="chunk_data",
        help="Directory for generated structured chunk files.",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=60,
        help="Minimum non-whitespace characters for one output chunk.",
    )
    parser.add_argument(
        "--target-chars",
        type=int,
        default=900,
        help="Preferred non-whitespace characters per merged chunk.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1800,
        help="Maximum non-whitespace characters for one output chunk.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_root.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_root}")
    if args.min_chars <= 0:
        raise ValueError("--min-chars must be greater than 0")
    if args.target_chars < args.min_chars:
        raise ValueError("--target-chars must be greater than or equal to --min-chars")
    if args.max_chars < args.target_chars:
        raise ValueError("--max-chars must be greater than or equal to --target-chars")

    txt_paths = list(input_root.rglob("*.txt"))
    chunks = build_chunks(
        txt_paths=txt_paths,
        input_root=input_root,
        min_chars=args.min_chars,
        target_chars=args.target_chars,
        max_chars=args.max_chars,
    )
    write_outputs(chunks, output_dir)

    print(f"TXT files: {len(txt_paths)}")
    print(f"Chunks written: {len(chunks)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
