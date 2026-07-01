from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"[ \t\u3000]+")
NEWLINE_RE = re.compile(r"\n{3,}")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；!?;])")
REFERENCE_HEADING_RE = re.compile(
    r"^\s*(?:参考文献|参\s*考\s*文\s*献|References?|REFERENCES|参考资料|注释)\s*[:：]?\s*$",
    re.I,
)
REFERENCE_HEADING_INLINE_RE = re.compile(
    r"(?:参考\s*文\s*献|References?|REFERENCES|参考资料|注释)\s*[:：]?",
    re.I,
)
ABSTRACT_KEYWORD_RE = re.compile(r"^\s*(?:摘\s*要|关键词|中图分类号|文献标识码|文章编号|DOI)\s*[:：]")
HEADER_FOOTER_RE = re.compile(
    r"^\s*(?:第\s*\d+\s*[卷期]|Vol\.\s*\d+|No\.\s*\d+|国\s*防\s*科\s*技|NATIONAL DEFENSE TECHNOLOGY|"
    r"\d{4}\s*年\s*第\s*\d+\s*期|总第\s*\d+\s*期|^\d+\s*$)\s*",
    re.I,
)
AUTHOR_PROFILE_RE = re.compile(r"^\s*作者简介\s*[:：]")


@dataclass
class PdfChunk:
    id: str
    text: str
    source: str
    title: str
    chunk_index: int
    char_count: int
    page_start: int
    page_end: int


def import_pdf_backend():
    try:
        import pdfplumber  # type: ignore

        return "pdfplumber", pdfplumber
    except Exception:
        try:
            import pypdf  # type: ignore

            return "pypdf", pypdf
        except Exception as exc:
            raise RuntimeError(
                "Neither pdfplumber nor pypdf is available. Use the bundled Codex Python "
                "runtime or install one of them."
            ) from exc


def clean_line(line: str) -> str:
    line = CONTROL_RE.sub("", line or "")
    line = SPACE_RE.sub(" ", line).strip()
    line = line.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return line


def clean_text(text: str) -> str:
    text = CONTROL_RE.sub("", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [clean_line(line) for line in text.splitlines()]
    return NEWLINE_RE.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def extract_pages_with_pdfplumber(pdf_path: Path, pdfplumber_module) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    with pdfplumber_module.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            pages.append((page_num, text))
    return pages


def extract_pages_with_pypdf(pdf_path: Path, pypdf_module) -> list[tuple[int, str]]:
    reader = pypdf_module.PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for page_num, page in enumerate(reader.pages, start=1):
        pages.append((page_num, page.extract_text() or ""))
    return pages


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    backend_name, backend = import_pdf_backend()
    if backend_name == "pdfplumber":
        return extract_pages_with_pdfplumber(pdf_path, backend)
    return extract_pages_with_pypdf(pdf_path, backend)


def strip_references_from_pages(pages: list[tuple[int, str]], keep_author_profile: bool) -> list[tuple[int, str]]:
    stripped_pages: list[tuple[int, str]] = []
    in_references = False
    for page_num, text in pages:
        kept_lines: list[str] = []
        for raw_line in text.splitlines():
            line = clean_line(raw_line)
            if not line:
                continue
            if REFERENCE_HEADING_RE.match(line):
                in_references = True
                break
            inline_ref = REFERENCE_HEADING_INLINE_RE.search(line)
            if inline_ref:
                prefix = clean_line(line[: inline_ref.start()])
                if prefix:
                    kept_lines.append(prefix)
                in_references = True
                break
            if in_references:
                continue
            if not keep_author_profile and AUTHOR_PROFILE_RE.match(line):
                in_references = True
                break
            kept_lines.append(line)
        if kept_lines:
            stripped_pages.append((page_num, "\n".join(kept_lines)))
        if in_references:
            break
    return stripped_pages


def is_noise_line(line: str) -> bool:
    if not line:
        return True
    if HEADER_FOOTER_RE.fullmatch(line):
        return True
    if "NATIONAL DEFENSE TECHNOLOGY" in line:
        return True
    if re.search(r"Vol\.\s*\d+,\s*No\.\s*\d+", line, re.I):
        return True
    if re.fullmatch(r"\d{4}\s*年\s*\d+\s*月", line):
        return True
    if re.fullmatch(r"\d+\s+国防科技\s+\d{4}\s*年第\s*\d+\s*期.*", line):
        return True
    if line == "万方数据":
        return True
    if re.fullmatch(r"[-–—_]{3,}", line):
        return True
    if re.fullmatch(r"\d+\s+国防科技\s+\d{4}.*", line):
        return True
    if re.fullmatch(r"第\s*\d+\s*页\s*/\s*共\s*\d+\s*页", line):
        return True
    return False


def should_join_without_space(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left.endswith("-") and re.match(r"^[A-Za-z]", right):
        return True
    if re.search(r"[，,、（(“\"《：:；;]$", left):
        return True
    if re.search(r"[\u4e00-\u9fff]$", left) and re.match(r"^[\u4e00-\u9fffA-Za-z0-9]", right):
        return True
    return False


def normalize_paragraph_lines(lines: list[str]) -> str:
    paragraph = ""
    for line in lines:
        if not paragraph:
            paragraph = line
        elif paragraph.endswith("-") and re.match(r"^[A-Za-z]", line):
            paragraph = paragraph[:-1] + line
        elif should_join_without_space(paragraph, line):
            paragraph += line
        else:
            paragraph += "\n" + line
    return clean_text(paragraph)


def iter_page_paragraphs(pages: list[tuple[int, str]]) -> Iterable[tuple[int, int, str]]:
    buffer: list[str] = []
    buffer_start_page = 0
    buffer_end_page = 0

    def flush() -> tuple[int, int, str] | None:
        nonlocal buffer, buffer_start_page, buffer_end_page
        if not buffer:
            return None
        paragraph = normalize_paragraph_lines(buffer)
        start_page = buffer_start_page
        end_page = buffer_end_page
        buffer = []
        buffer_start_page = 0
        buffer_end_page = 0
        if paragraph:
            return start_page, end_page, paragraph
        return None

    for page_num, page_text in pages:
        raw_lines = page_text.splitlines()
        for raw_line in raw_lines:
            line = clean_line(raw_line)
            if is_noise_line(line):
                item = flush()
                if item:
                    yield item
                continue

            # Keep common academic metadata as separate small units; they may be
            # merged later if useful, but should not glue into the first body paragraph.
            if ABSTRACT_KEYWORD_RE.match(line):
                item = flush()
                if item:
                    yield item
                yield page_num, page_num, line
                continue

            if not buffer:
                buffer_start_page = page_num
            buffer_end_page = page_num
            buffer.append(line)

            if re.search(r"[。！？!?]$", line):
                item = flush()
                if item:
                    yield item

        item = flush()
        if item:
            yield item


def split_long_text(text: str, max_chars: int) -> list[str]:
    if text_len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in SENTENCE_SPLIT_RE.split(text):
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


def infer_title(pdf_path: Path, paragraphs: list[tuple[int, int, str]]) -> str:
    stem_title = clean_text(pdf_path.stem)
    if stem_title:
        return stem_title
    for _start, _end, paragraph in paragraphs[:8]:
        if text_len(paragraph) < 4:
            continue
        if ABSTRACT_KEYWORD_RE.match(paragraph):
            continue
        if len(paragraph) <= 120:
            return paragraph
    return pdf_path.stem


def build_pdf_chunks(
    pdf_path: Path,
    input_root: Path,
    min_chars: int,
    target_chars: int,
    max_chars: int,
    keep_author_profile: bool,
) -> list[PdfChunk]:
    pages = extract_pages(pdf_path)
    pages = strip_references_from_pages(pages, keep_author_profile=keep_author_profile)
    paragraphs = list(iter_page_paragraphs(pages))
    title = infer_title(pdf_path, paragraphs)
    source = pdf_path.relative_to(input_root).as_posix()

    chunks: list[PdfChunk] = []
    pending_text = ""
    pending_start = 0
    pending_end = 0
    chunk_index = 0

    def emit(text: str, start_page: int, end_page: int) -> None:
        nonlocal chunk_index
        for part in split_long_text(text, max_chars):
            if text_len(part) < min_chars:
                continue
            chunk_index += 1
            chunks.append(
                PdfChunk(
                    id=f"{source}#{chunk_index:05d}",
                    text=part,
                    source=source,
                    title=title,
                    chunk_index=chunk_index,
                    char_count=text_len(part),
                    page_start=start_page,
                    page_end=end_page,
                )
            )

    def flush_pending() -> None:
        nonlocal pending_text, pending_start, pending_end
        if text_len(pending_text) >= min_chars:
            emit(pending_text.strip(), pending_start, pending_end)
        pending_text = ""
        pending_start = 0
        pending_end = 0

    for start_page, end_page, paragraph in paragraphs:
        paragraph = clean_text(paragraph)
        if not paragraph:
            continue
        if text_len(paragraph) < min_chars and not pending_text:
            pending_text = paragraph
            pending_start = start_page
            pending_end = end_page
            continue
        combined = f"{pending_text}\n{paragraph}".strip() if pending_text else paragraph
        if pending_text and text_len(combined) > max_chars:
            flush_pending()
            combined = paragraph
            pending_start = start_page
        elif not pending_text:
            pending_start = start_page
        pending_text = combined
        pending_end = end_page
        if text_len(pending_text) >= target_chars:
            flush_pending()

    flush_pending()
    return chunks


def write_jsonl(chunks: list[PdfChunk], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def write_stats(stats: dict, stats_path: Path) -> None:
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDF files into paragraph-like JSONL chunks and remove references."
    )
    parser.add_argument("input", help="PDF file or directory containing PDF files.")
    parser.add_argument(
        "--output",
        default="chunk_data/intermediate/pdf/pdf_paragraph_chunks.jsonl",
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--stats-output",
        default=None,
        help="Optional stats JSON path. Defaults to output path with _stats.json suffix.",
    )
    parser.add_argument("--recursive", action="store_true", help="Read PDFs recursively when input is a directory.")
    parser.add_argument("--min-chars", type=int, default=80, help="Minimum non-whitespace characters per chunk.")
    parser.add_argument("--target-chars", type=int, default=900, help="Preferred characters per merged chunk.")
    parser.add_argument("--max-chars", type=int, default=1800, help="Maximum characters per chunk.")
    parser.add_argument(
        "--keep-author-profile",
        action="store_true",
        help="Keep author-profile sections after the body. By default they are dropped.",
    )
    parser.add_argument("--continue-on-error", action="store_true", help="Continue if one PDF fails.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    stats_path = (
        Path(args.stats_output).resolve()
        if args.stats_output
        else output_path.with_name(output_path.stem + "_stats.json")
    )

    if not input_path.exists():
        raise FileNotFoundError(f"Input does not exist: {input_path}")
    if args.min_chars <= 0:
        raise ValueError("--min-chars must be greater than 0")
    if args.target_chars < args.min_chars:
        raise ValueError("--target-chars must be greater than or equal to --min-chars")
    if args.max_chars < args.target_chars:
        raise ValueError("--max-chars must be greater than or equal to --target-chars")

    if input_path.is_file():
        pdf_paths = [input_path]
        input_root = input_path.parent
    else:
        pattern = "**/*.pdf" if args.recursive else "*.pdf"
        pdf_paths = sorted(input_path.glob(pattern))
        input_root = input_path

    all_chunks: list[PdfChunk] = []
    errors: list[dict[str, str]] = []
    per_file: list[dict[str, object]] = []

    for pdf_path in pdf_paths:
        try:
            chunks = build_pdf_chunks(
                pdf_path=pdf_path,
                input_root=input_root,
                min_chars=args.min_chars,
                target_chars=args.target_chars,
                max_chars=args.max_chars,
                keep_author_profile=args.keep_author_profile,
            )
        except Exception as exc:
            if not args.continue_on_error:
                raise
            errors.append({"file": str(pdf_path), "error": repr(exc)})
            print(f"[error] {pdf_path} -> {exc}")
            continue
        all_chunks.extend(chunks)
        per_file.append(
            {
                "file": pdf_path.relative_to(input_root).as_posix(),
                "chunks": len(chunks),
                "chars": sum(chunk.char_count for chunk in chunks),
            }
        )
        print(f"[ok] {pdf_path.name}: {len(chunks)} chunks")

    write_jsonl(all_chunks, output_path)
    write_stats(
        {
            "input": str(input_path),
            "pdf_files": len(pdf_paths),
            "processed_files": len(per_file),
            "chunks": len(all_chunks),
            "chars": sum(chunk.char_count for chunk in all_chunks),
            "errors": errors,
            "files": per_file,
        },
        stats_path,
    )

    print(f"PDF files: {len(pdf_paths)}")
    print(f"Processed files: {len(per_file)}")
    print(f"Chunks written: {len(all_chunks)}")
    print(f"Output JSONL: {output_path}")
    print(f"Stats JSON: {stats_path}")


if __name__ == "__main__":
    main()
