from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CATALOG_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def parse_catalog_links(catalog_path: Path) -> list[Path]:
    links: list[Path] = []
    if not catalog_path.exists():
        return links

    for line in catalog_path.read_text(encoding="utf-8").splitlines():
        match = CATALOG_LINK_RE.search(line)
        if not match:
            continue
        rel_path = match.group(1).replace("/", "\\")
        links.append((catalog_path.parent / rel_path).resolve())
    return links


def iter_taxonomy_files(root: Path) -> list[Path]:
    catalog_files = [
        root / "01-我方能力目录.md",
        root / "02-他方能力目录.md",
    ]

    files: list[Path] = []
    for catalog_file in catalog_files:
        files.extend(parse_catalog_links(catalog_file))

    existing_files = [path for path in files if path.exists()]
    seen = set()
    result: list[Path] = []
    for path in existing_files:
        key = path.resolve()
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def side_from_path(path: Path) -> tuple[str, str]:
    parts = {part.lower() for part in path.parts}
    if "friendly" in parts:
        return "friendly", "我方"
    if "opponent" in parts:
        return "opponent", "他方"
    return "unknown", "未分侧"


def parse_taxonomy_file(path: Path, root: Path) -> list[dict[str, Any]]:
    side, _ = side_from_path(path)
    level1 = ""
    current_level2 = ""
    entries: list[dict[str, Any]] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 1:
                level1 = title
            elif level == 2:
                current_level2 = title
            continue

        bullet = BULLET_RE.match(line)
        if not bullet or not level1:
            continue

        level3 = bullet.group(1).strip()
        if not level3:
            continue

        level2 = current_level2 or "未分组"
        entries.append(
            {
                "side": side,
                "source_path": path.relative_to(root).as_posix(),
                "level1": level1,
                "level2": level2,
                "level3": level3,
                "full_path": "/".join([level1, level2, level3]),
            }
        )

    return entries


def build_leaf_catalog(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    files = iter_taxonomy_files(root)
    labels: list[dict[str, Any]] = []
    missing_from_catalog: list[str] = []

    for catalog_file in [root / "01-我方能力目录.md", root / "02-他方能力目录.md"]:
        for linked_path in parse_catalog_links(catalog_file):
            if not linked_path.exists():
                missing_from_catalog.append(linked_path.relative_to(root).as_posix())

    for path in files:
        labels.extend(parse_taxonomy_file(path, root))

    return labels, missing_from_catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build leaf catalog JSON from taxonomy markdown files.")
    parser.add_argument("--taxonomy-root", default="../military_sft_taxonomy", help="Taxonomy markdown root.")
    parser.add_argument(
        "--output",
        default="configs/military_sft_taxonomy_compact.json",
        help="Output leaf catalog JSON. The filename is kept for compatibility.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.taxonomy_root).resolve()
    output = Path(args.output)
    labels, missing_from_catalog = build_leaf_catalog(root)
    if not labels:
        raise ValueError(f"No taxonomy labels found under {root}. Refuse to overwrite output with an empty catalog.")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Taxonomy labels: {len(labels)}")
    if missing_from_catalog:
        print("Missing files referenced by catalog:")
        for item in missing_from_catalog:
            print(f"  - {item}")
    print(f"Output: {output.resolve()}")


if __name__ == "__main__":
    main()
