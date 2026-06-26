from __future__ import annotations

import argparse
import bz2
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import IO, Any

from wikiextractor.extract import Extractor


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
WIKI_DATA_DIR = WORKSPACE_DIR / "raw_data" / "wiki"
DEFAULT_INPUT = WIKI_DATA_DIR / "zhwiki-latest-pages-articles-multistream.xml" / "zhwiki-latest-pages-articles-multistream.xml"
DEFAULT_OUTPUT = WIKI_DATA_DIR / "extracted"
DEFAULT_STATS = WIKI_DATA_DIR / "stats" / "wiki_extract_stats.json"

SPACE_RE = re.compile(r"[ \t\u3000]+")
BLANK_RE = re.compile(r"\n{3,}")


class RollingJsonlWriter:
    def __init__(self, output_dir: Path, max_bytes: int) -> None:
        self.output_dir = output_dir
        self.max_bytes = max_bytes
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.index = 0
        self.current_bytes = 0
        self.handle: IO[str] | None = None
        self.files: list[dict[str, Any]] = []
        self._open_next()

    def _open_next(self) -> None:
        if self.handle is not None:
            self.handle.close()
        path = self.output_dir / f"wiki_{self.index:04d}.jsonl"
        self.handle = path.open("w", encoding="utf-8", newline="\n")
        self.files.append({"path": str(path), "bytes": 0, "records": 0})
        self.current_bytes = 0
        self.index += 1

    def write(self, row: dict[str, Any]) -> None:
        line = json.dumps(row, ensure_ascii=False) + "\n"
        line_bytes = len(line.encode("utf-8"))
        if self.current_bytes and self.current_bytes + line_bytes > self.max_bytes:
            self._open_next()
        assert self.handle is not None
        self.handle.write(line)
        self.current_bytes += line_bytes
        self.files[-1]["bytes"] += line_bytes
        self.files[-1]["records"] += 1

    def close(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def parse_size(value: str) -> int:
    value = value.strip().upper()
    multiplier = 1
    if value.endswith("K"):
        multiplier = 1024
        value = value[:-1]
    elif value.endswith("M"):
        multiplier = 1024**2
        value = value[:-1]
    elif value.endswith("G"):
        multiplier = 1024**3
        value = value[:-1]
    return int(float(value) * multiplier)


def open_input(path: Path) -> IO[bytes]:
    if path.suffix == ".bz2":
        return bz2.open(path, "rb")
    return path.open("rb")


def strip_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def child_text(element: ET.Element, name: str, default: str = "") -> str:
    for child in element:
        if strip_namespace(child.tag) == name:
            return child.text or default
    return default


def find_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if strip_namespace(child.tag) == name:
            return child
    return None


def normalize_text(text: str) -> str:
    lines = [SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return BLANK_RE.sub("\n\n", text).strip()


def clean_wiki_text(page_id: str, revid: str, title: str, raw_text: str, urlbase: str) -> str:
    extractor = Extractor(page_id, revid, urlbase, title, [raw_text])
    parts = extractor.clean_text(
        raw_text,
        mark_headers=True,
        expand_templates=False,
        html_safe=False,
    )
    return normalize_text("\n".join(parts))


def iter_pages(input_path: Path) -> Any:
    with open_input(input_path) as stream:
        for _event, element in ET.iterparse(stream, events=("end",)):
            if strip_namespace(element.tag) != "page":
                continue

            title = child_text(element, "title")
            ns = child_text(element, "ns", default="-1")
            page_id = child_text(element, "id")
            revision = find_child(element, "revision")
            revid = ""
            raw_text = ""
            if revision is not None:
                revid = child_text(revision, "id")
                raw_text = child_text(revision, "text")

            yield {
                "id": page_id,
                "revid": revid,
                "title": title,
                "ns": ns,
                "raw_text": raw_text,
            }
            element.clear()


def run(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input)
    output_dir = Path(args.output)
    stats_path = Path(args.stats)
    writer = RollingJsonlWriter(output_dir, parse_size(args.bytes))

    start = time.time()
    seen = written = skipped_ns = skipped_empty = clean_errors = 0

    try:
        for page in iter_pages(input_path):
            seen += 1
            if page["ns"] != "0":
                skipped_ns += 1
                continue
            raw_text = str(page.get("raw_text") or "")
            if not raw_text.strip():
                skipped_empty += 1
                continue

            try:
                text = clean_wiki_text(
                    str(page["id"]),
                    str(page["revid"]),
                    str(page["title"]),
                    raw_text,
                    args.urlbase,
                )
            except Exception as exc:
                clean_errors += 1
                logging.warning("clean failed for page %s %s: %s", page["id"], page["title"], exc)
                continue

            if len(text) < args.min_text_chars:
                skipped_empty += 1
                continue

            row = {
                "id": str(page["id"]),
                "revid": str(page["revid"]),
                "url": f"{args.urlbase}?curid={page['id']}",
                "title": str(page["title"]),
                "text": text,
                "source": str(input_path),
                "site": "wikipedia",
                "license": "CC BY-SA",
            }
            writer.write(row)
            written += 1

            if args.limit and written >= args.limit:
                break
            if seen % args.progress_every == 0:
                elapsed = max(time.time() - start, 1)
                logging.info(
                    "seen=%d written=%d skipped_ns=%d skipped_empty=%d rate=%.1f pages/s",
                    seen,
                    written,
                    skipped_ns,
                    skipped_empty,
                    seen / elapsed,
                )
    finally:
        writer.close()

    stats = {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "seen_pages": seen,
        "written_articles": written,
        "skipped_non_main_namespace": skipped_ns,
        "skipped_empty_or_short": skipped_empty,
        "clean_errors": clean_errors,
        "seconds": round(time.time() - start, 2),
        "files": writer.files,
    }
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows-friendly Wikipedia XML to cleaned JSONL extractor.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Wikipedia XML or XML.bz2 dump path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory for JSONL shards.")
    parser.add_argument("--stats", default=str(DEFAULT_STATS), help="Stats JSON path.")
    parser.add_argument("--bytes", default="200M", help="Maximum bytes per output JSONL shard.")
    parser.add_argument("--urlbase", default="https://zh.wikipedia.org/wiki", help="URL base for curid links.")
    parser.add_argument("--min-text-chars", type=int, default=80, help="Skip cleaned articles shorter than this.")
    parser.add_argument("--limit", type=int, default=0, help="Stop after writing this many articles; 0 means no limit.")
    parser.add_argument("--progress-every", type=int, default=100000, help="Log progress every N seen pages.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")
    stats = run(args)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
