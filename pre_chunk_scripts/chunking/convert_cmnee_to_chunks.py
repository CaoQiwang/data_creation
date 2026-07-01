from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
DEFAULT_INPUT = WORKSPACE_DIR / "raw_data" / "CMNEE"
DEFAULT_OUTPUT = WORKSPACE_DIR / "chunk_data" / "cmnee_chunks.jsonl"
DEFAULT_STATS = WORKSPACE_DIR / "chunk_data" / "cmnee_chunks_stats.json"
DEFAULT_SPLITS = ("train", "valid", "test")

SPACE_RE = re.compile(r"[ \t\u3000]+")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_text(text: str) -> str:
    text = CONTROL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def load_split(input_dir: Path, split: str) -> list[dict[str, Any]]:
    path = input_dir / f"{split}.json"
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return data


def iter_chunks(input_dir: Path, splits: Iterable[str]) -> Iterable[dict[str, Any]]:
    for split in splits:
        for index, row in enumerate(load_split(input_dir, split), start=1):
            source_id = str(row.get("id") or index)
            text = normalize_text(str(row.get("text") or ""))
            if not text:
                continue

            event_list = row.get("event_list") or []
            coref_arguments = row.get("coref_arguments") or []
            event_types = sorted(
                {
                    str(event.get("event_type"))
                    for event in event_list
                    if isinstance(event, dict) and event.get("event_type")
                }
            )

            yield {
                "id": f"CMNEE/{split}/{source_id}",
                "text": text,
                "source": f"raw_data/CMNEE/{split}.json",
                "title": "",
                "category": "cmnee_event_extraction",
                "chunk_index": index,
                "char_count": text_len(text),
                "dataset_version": "cmnee_v1",
                "dataset_source": "CMNEE",
                "split": split,
                "cmnee_id": source_id,
                "cmnee_event_types": event_types,
                "cmnee_event_count": len(event_list) if isinstance(event_list, list) else 0,
                "cmnee_event_list": event_list,
                "cmnee_coref_arguments": coref_arguments,
            }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            written.append(row)
    return written


def build_stats(rows: list[dict[str, Any]], output: Path, splits: tuple[str, ...]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split") or "unknown") for row in rows)
    event_type_counts: Counter[str] = Counter()
    char_counts: list[int] = []
    event_counts: list[int] = []

    for row in rows:
        char_counts.append(int(row.get("char_count") or 0))
        event_counts.append(int(row.get("cmnee_event_count") or 0))
        event_type_counts.update(str(t) for t in row.get("cmnee_event_types") or [])

    return {
        "dataset_version": "cmnee_v1",
        "output": str(output),
        "splits": list(splits),
        "rows": len(rows),
        "split_counts": dict(split_counts),
        "char_count": {
            "min": min(char_counts) if char_counts else 0,
            "max": max(char_counts) if char_counts else 0,
            "avg": round(sum(char_counts) / len(char_counts), 2) if char_counts else 0,
        },
        "event_count": {
            "min": min(event_counts) if event_counts else 0,
            "max": max(event_counts) if event_counts else 0,
            "avg": round(sum(event_counts) / len(event_counts), 2) if event_counts else 0,
        },
        "event_type_counts": dict(event_type_counts.most_common()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert CMNEE JSON files into chunk_data JSONL.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Directory containing CMNEE train/valid/test JSON files.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output chunk JSONL path.")
    parser.add_argument("--stats", default=str(DEFAULT_STATS), help="Output stats JSON path.")
    parser.add_argument(
        "--splits",
        nargs="+",
        default=list(DEFAULT_SPLITS),
        help="CMNEE splits to convert, without .json suffix.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input).resolve()
    output = Path(args.output).resolve()
    stats_path = Path(args.stats).resolve()
    splits = tuple(str(split) for split in args.splits)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    for split in splits:
        path = input_dir / f"{split}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing CMNEE split file: {path}")

    rows = write_jsonl(output, iter_chunks(input_dir, splits))
    stats = build_stats(rows, output, splits)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
