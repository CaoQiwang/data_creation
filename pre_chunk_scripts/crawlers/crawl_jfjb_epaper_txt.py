from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urlparse

import requests

# Example:
# python pre_chunk_scripts\crawlers\crawl_jfjb_epaper_txt.py --date 2026-06-29 --paper-number 01
# python pre_chunk_scripts\crawlers\crawl_jfjb_epaper_txt.py --seed "http://www.81.cn/szb_223187/szblb/index.html?paperNumber=01&paperName=jfjb&paperDate=2026-06-29"

DEFAULT_OUTPUT = "raw_data/txt/1/jfjb_epaper"
DEFAULT_USER_AGENT = "sft-data-research-crawler/1.0 (+local dataset construction)"
JSON_BASE_URLS = {
    "jfjb": "http://www.81.cn/_szb/jfjb/{yyyy}/{mm}/{dd}/index.json",
}
LIST_PATHS = {
    "jfjb": "/szb_223187/szblb/index.html",
}
CONTENT_PATHS = {
    "jfjb": "/szb_223187/szbxq/index.html",
}

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"[ \t\u3000]+")
NEWLINE_RE = re.compile(r"\n{3,}")


@dataclass
class Article:
    url: str
    title: str
    subtitle: str
    guide_title: str
    author: str
    publish_date: str
    source: str
    paper_name: str
    paper_number: str
    paper_section: str
    article_id: str
    text: str


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.links: list[str] = []
        self._current_block: list[str] | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if tag == "a" and attr_map.get("href"):
            self.links.append(attr_map["href"])
        if tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self._current_block = []
        elif tag == "br" and self._current_block is not None:
            self._current_block.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"p", "div", "li", "h1", "h2", "h3"}:
            text = clean_text("".join(self._current_block or []))
            if text:
                self.blocks.append(text)
            self._current_block = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._current_block is not None:
            self._current_block.append(data)


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = CONTROL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return NEWLINE_RE.sub("\n\n", text).strip()


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def parse_html_text(markup: str) -> str:
    parser = TextHTMLParser()
    parser.feed(markup or "")
    parser.close()
    blocks: list[str] = []
    seen: set[str] = set()
    for block in parser.blocks:
        if text_len(block) < 2 or block in seen:
            continue
        seen.add(block)
        blocks.append(block)
    return clean_text("\n\n".join(blocks))


def make_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        }
    )
    return session


def date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_seed(seed: str) -> tuple[str | None, date | None, str | None]:
    query = parse_qs(urlparse(seed).query)
    paper_name = (query.get("paperName") or [None])[0]
    paper_date = (query.get("paperDate") or [None])[0]
    paper_number = (query.get("paperNumber") or [None])[0]
    parsed_date = parse_date(paper_date) if paper_date else None
    return paper_name, parsed_date, paper_number


def json_url(paper_name: str, paper_date: date) -> str:
    template = JSON_BASE_URLS[paper_name]
    return template.format(
        yyyy=f"{paper_date.year:04d}",
        mm=f"{paper_date.month:02d}",
        dd=f"{paper_date.day:02d}",
    )


def article_url(paper_name: str, paper_date: str, paper_number: str, article_id: str) -> str:
    query = urlencode(
        {
            "paperName": paper_name,
            "paperDate": paper_date,
            "paperNumber": paper_number,
            "articleid": article_id,
        }
    )
    return f"http://www.81.cn{CONTENT_PATHS[paper_name]}?{query}"


def fetch_paper_json(
    session: requests.Session,
    paper_name: str,
    paper_date: date,
    timeout: float,
) -> dict | None:
    url = json_url(paper_name, paper_date)
    response = session.get(url, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def iter_articles(
    paper_data: dict,
    paper_name: str,
    selected_numbers: set[str],
    min_chars: int,
) -> Iterable[Article]:
    for paper in paper_data.get("paperInfo") or []:
        paper_number = str(paper.get("paperNumber") or "").zfill(2)
        if selected_numbers and paper_number not in selected_numbers:
            continue
        paper_date = str(paper.get("paperData") or "")
        paper_section = clean_text(str(paper.get("paperBk") or ""))
        source_name = clean_text(str(paper.get("paperName") or "解放军报"))
        for item in paper.get("xyList") or []:
            article_id = str(item.get("id") or "")
            title = clean_text(str(item.get("title") or ""))
            subtitle = clean_text(str(item.get("title2") or ""))
            guide_title = clean_text(str(item.get("guideTitle") or ""))
            author = clean_text(str(item.get("author") or ""))
            body = parse_html_text(str(item.get("content") or ""))
            if text_len(body) < min_chars:
                continue
            if not title:
                title = body.splitlines()[0][:40]
            yield Article(
                url=article_url(paper_name, paper_date, paper_number, article_id),
                title=title,
                subtitle=subtitle,
                guide_title=guide_title,
                author=author,
                publish_date=paper_date,
                source=source_name,
                paper_name=source_name,
                paper_number=paper_number,
                paper_section=paper_section,
                article_id=article_id,
                text=body,
            )


def safe_filename(text: str, max_length: int = 90) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:max_length] or "untitled"


def article_filename(article: Article) -> str:
    digest = hashlib.sha1(article.url.encode("utf-8")).hexdigest()[:10]
    date_part = re.sub(r"\D+", "", article.publish_date)
    title_part = safe_filename(article.title)
    return f"{date_part}_{article.paper_number}_{title_part}_{digest}.txt"


def format_article(article: Article) -> str:
    header = [
        article.title,
        article.guide_title,
        article.subtitle,
        article.author,
        f"来源：{article.source}" if article.source else "",
        f"发布日期：{article.publish_date}" if article.publish_date else "",
        f"版面：第{article.paper_number}版 {article.paper_section}".strip(),
        f"原文链接：{article.url}",
    ]
    return clean_text("\n".join(line for line in header if line) + "\n\n" + article.text)


def load_seen_urls(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    seen: set[str] = set()
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = row.get("url")
            if isinstance(url, str):
                seen.add(url)
    return seen


def append_index(index_path: Path, article: Article, file_path: Path) -> None:
    row = asdict(article)
    row.pop("text", None)
    row["file"] = file_path.as_posix()
    with index_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_paper_numbers(values: list[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        if value.lower() == "all":
            return set()
        for part in value.split(","):
            part = part.strip()
            if part:
                result.add(part.zfill(2))
    return result


def crawl(args: argparse.Namespace) -> None:
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / args.index_name
    seen_urls = load_seen_urls(index_path)
    saved_hashes: set[str] = set()
    selected_numbers = normalize_paper_numbers(args.paper_number)

    session = make_session(args.user_agent)
    saved_count = 0
    fetched_count = 0

    for paper_date in date_range(args.start_date, args.end_date):
        try:
            paper_data = fetch_paper_json(session, args.paper_name, paper_date, args.timeout)
        except Exception as exc:
            print(f"[error] {paper_date} -> {exc}")
            time.sleep(args.delay)
            continue

        fetched_count += 1
        if not paper_data:
            print(f"[missing] {paper_date}")
            time.sleep(args.delay)
            continue

        day_saved = 0
        for article in iter_articles(paper_data, args.paper_name, selected_numbers, args.min_chars):
            if article.url in seen_urls and not args.overwrite:
                print(f"[seen] {article.title}")
                continue

            content = format_article(article)
            content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
            if content_hash in saved_hashes:
                print(f"[dup] {article.title}")
                continue
            saved_hashes.add(content_hash)

            file_path = output_dir / article_filename(article)
            if file_path.exists() and not args.overwrite:
                print(f"[exists] {file_path.name}")
                continue

            file_path.write_text(content + "\n", encoding="utf-8")
            append_index(index_path, article, file_path)
            seen_urls.add(article.url)
            saved_count += 1
            day_saved += 1
            print(f"[saved] {saved_count} {paper_date} {article.paper_number} {article.title}")

        print(f"[date] {paper_date} saved {day_saved}")
        time.sleep(args.delay)

    print(f"Fetched paper JSON files: {fetched_count}")
    print(f"Saved articles: {saved_count}")
    print(f"Output directory: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl PLA Daily epaper JSON from 81.cn and save article text as TXT files."
    )
    parser.add_argument(
        "--seed",
        help="Reference epaper URL. Query params paperName, paperDate, and paperNumber are used as defaults.",
    )
    parser.add_argument("--date", help="Single date to crawl, in YYYY-MM-DD.")
    parser.add_argument("--start-date", help="Start date for a date range, in YYYY-MM-DD.")
    parser.add_argument("--end-date", help="End date for a date range, in YYYY-MM-DD.")
    parser.add_argument(
        "--paper-name",
        default="jfjb",
        choices=sorted(JSON_BASE_URLS),
        help="Paper code. Defaults to jfjb (解放军报).",
    )
    parser.add_argument(
        "--paper-number",
        action="append",
        default=[],
        help="Paper number to save, e.g. 01. Pass multiple times, comma-separated values, or all. Defaults to all.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Directory for downloaded TXT articles.")
    parser.add_argument("--min-chars", type=int, default=200, help="Minimum article body length.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between paper JSON requests in seconds.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent sent with HTTP requests.")
    parser.add_argument("--index-name", default="_crawl_index.jsonl", help="Index file written under output.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing TXT files.")
    args = parser.parse_args()

    seed_paper_name = None
    seed_date = None
    seed_paper_number = None
    if args.seed:
        seed_paper_name, seed_date, seed_paper_number = parse_seed(args.seed)

    if seed_paper_name:
        if seed_paper_name not in JSON_BASE_URLS:
            raise ValueError(f"Unsupported paperName from --seed: {seed_paper_name}")
        args.paper_name = seed_paper_name

    if not args.paper_number and seed_paper_number:
        args.paper_number = [seed_paper_number]
    if not args.paper_number:
        args.paper_number = ["all"]

    if args.date:
        args.start_date = parse_date(args.date)
        args.end_date = args.start_date
    else:
        start_value = args.start_date or (seed_date.isoformat() if seed_date else None)
        end_value = args.end_date or start_value
        if not start_value:
            raise ValueError("Provide --date, --start-date, or --seed with paperDate.")
        args.start_date = parse_date(start_value)
        args.end_date = parse_date(end_value)

    if args.end_date < args.start_date:
        raise ValueError("--end-date must be greater than or equal to --start-date")
    if args.min_chars <= 0:
        raise ValueError("--min-chars must be greater than 0")
    if args.delay < 0:
        raise ValueError("--delay must be greater than or equal to 0")
    return args


def main() -> None:
    crawl(parse_args())


if __name__ == "__main__":
    main()
