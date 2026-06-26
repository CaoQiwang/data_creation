from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
DEFAULT_EXISTING = WORKSPACE_DIR / "chunk_data" / "intermediate" / "rule_prefilter" / "rule_prefiltered_chunks.jsonl"
DEFAULT_WIKI = WORKSPACE_DIR / "chunk_data" / "intermediate" / "wiki" / "wiki_military_title_strict_prefiltered_chunks.jsonl"
DEFAULT_OUTPUT = WORKSPACE_DIR / "chunk_data" / "v1_chunks.jsonl"
DEFAULT_STATS = WORKSPACE_DIR / "chunk_data" / "v1_chunks_stats.json"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} line {line_no}: {exc}") from exc


def write_row(handle: Any, row: dict[str, Any]) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def copy_source(
    input_path: Path,
    output_handle: Any,
    dataset_source: str,
    dataset_version: str,
    seen_ids: set[str],
) -> tuple[int, int, Counter[str]]:
    written = 0
    duplicate_ids = 0
    category_counts: Counter[str] = Counter()

    for row in iter_jsonl(input_path):
        row_id = str(row.get("id") or "")
        if row_id in seen_ids:
            duplicate_ids += 1
            row["id"] = f"{dataset_source}/{row_id}"
            row_id = row["id"]
        seen_ids.add(row_id)

        row["dataset_version"] = dataset_version
        row["dataset_source"] = dataset_source
        category_counts[str(row.get("category") or row.get("site") or "unknown")] += 1
        write_row(output_handle, row)
        written += 1

    return written, duplicate_ids, category_counts


def run(args: argparse.Namespace) -> dict[str, Any]:
    existing_path = Path(args.existing)
    wiki_path = Path(args.wiki)
    output_path = Path(args.output)
    stats_path = Path(args.stats)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    stats: dict[str, Any] = {
        "dataset_version": args.dataset_version,
        "output": str(output_path),
        "sources": {},
    }

    total = 0
    total_duplicates = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as out_f:
        for dataset_source, input_path in [
            ("existing_rule_prefiltered", existing_path),
            ("wiki_military_title_strict", wiki_path),
        ]:
            written, duplicate_ids, category_counts = copy_source(
                input_path,
                out_f,
                dataset_source,
                args.dataset_version,
                seen_ids,
            )
            total += written
            total_duplicates += duplicate_ids
            stats["sources"][dataset_source] = {
                "input": str(input_path),
                "rows": written,
                "duplicate_ids_rewritten": duplicate_ids,
                "category_counts": dict(category_counts.most_common()),
            }

    stats["total_rows"] = total
    stats["duplicate_ids_rewritten"] = total_duplicates
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build v1 chunk dataset by merging existing filtered chunks with wiki chunks.")
    parser.add_argument("--existing", default=str(DEFAULT_EXISTING), help="Existing filtered chunk JSONL.")
    parser.add_argument("--wiki", default=str(DEFAULT_WIKI), help="Filtered title-strict wiki chunk JSONL.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Merged v1 output JSONL.")
    parser.add_argument("--stats", default=str(DEFAULT_STATS), help="Merged v1 stats JSON.")
    parser.add_argument("--dataset-version", default="v1", help="Dataset version tag to attach to each row.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    stats = run(args)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
