from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

# python crawlers\crawl_81cn_txt.py --section 11 --max-list-pages 20 --max-pages 1000 --max-depth 2 --min-chars 300 --delay 1


DEFAULT_SEEDS = ["https://www.81.cn/"]
DEFAULT_OUTPUT = "raw_data/txt/1/81cn_news"
SECTION_PRESETS = {
    "11": ("http://www.81.cn/yw_208727/index.html", "raw_data/txt/1/11要闻"),
    "12": ("http://www.81.cn/xx_207779/index.html", "raw_data/txt/1/12学习"),
    "13": ("http://www.81.cn/ll_208543/index.html", "raw_data/txt/1/13理论"),
    "14": ("http://www.81.cn/pl_208541/index.html", "raw_data/txt/1/14评论"),
    "15": ("http://www.81.cn/ss_208539/index.html", "raw_data/txt/1/15时事"),
    "yw": ("http://www.81.cn/yw_208727/index.html", "raw_data/txt/1/11要闻"),
    "xx": ("http://www.81.cn/xx_207779/index.html", "raw_data/txt/1/12学习"),
    "ll": ("http://www.81.cn/ll_208543/index.html", "raw_data/txt/1/13理论"),
    "pl": ("http://www.81.cn/pl_208541/index.html", "raw_data/txt/1/14评论"),
    "ss": ("http://www.81.cn/ss_208539/index.html", "raw_data/txt/1/15时事"),
}
SECTION_PATH_PREFIXES = {
    "11": ("/yw_208727/",),
    "12": ("/xx_207779/",),
    "13": ("/ll_208543/",),
    "14": ("/pl_208541/",),
    "15": ("/ss_208539/",),
    "yw": ("/yw_208727/",),
    "xx": ("/xx_207779/",),
    "ll": ("/ll_208543/",),
    "pl": ("/pl_208541/",),
    "ss": ("/ss_208539/",),
}
SECTION_LIST_PAGE_LIMITS = {
    "11": 5,
    "12": 5,
    "13": 10,
    "14": 5,
    "15": 5,
    "yw": 5,
    "xx": 5,
    "ll": 10,
    "pl": 5,
    "ss": 5,
}
ALLOWED_HOST_SUFFIXES = ("81.cn",)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"[ \t\u3000]+")
NEWLINE_RE = re.compile(r"\n{3,}")
DATE_RE = re.compile(
    r"20\d{2}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}:\d{2})?"
    r"|20\d{2}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2})?"
)
BAD_TITLE_PARTS = ("中国军网", "解放军报", "军事", "首页")


@dataclass
class Article:
    url: str
    title: str
    publish_date: str
    source: str
    text: str


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.blocks: list[str] = []
        self._tag_stack: list[str] = []
        self._current_block: list[str] | None = None
        self._in_title = False
        self._in_heading = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}

        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return

        if tag == "a" and attr_map.get("href"):
            self.links.append(attr_map["href"])
        elif tag == "meta":
            key = (
                attr_map.get("property")
                or attr_map.get("name")
                or attr_map.get("itemprop")
                or ""
            ).strip().lower()
            value = attr_map.get("content", "").strip()
            if key and value:
                self.meta[key] = value
        elif tag == "title":
            self._in_title = True
        elif tag in {"h1", "h2"}:
            self._in_heading = True
            self._current_block = []
        elif tag in {"p", "li"}:
            self._current_block = []
        elif tag == "br" and self._current_block is not None:
            self._current_block.append("\n")

        self._tag_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return

        if tag == "title":
            self._in_title = False
        elif tag in {"h1", "h2"}:
            text = clean_text("".join(self._current_block or []))
            if text:
                self.heading_parts.append(text)
            self._in_heading = False
            self._current_block = None
        elif tag in {"p", "li"}:
            text = clean_text("".join(self._current_block or []))
            if text:
                self.blocks.append(text)
            self._current_block = None

        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._current_block is not None:
            self._current_block.append(data)


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = CONTROL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return NEWLINE_RE.sub("\n\n", text).strip()


def text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    if base_url:
        url = urljoin(base_url, url)
    url, _fragment = urldefrag(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return parsed.geturl()


def make_section_list_pages(seed_url: str, max_list_page: int) -> list[str]:
    if max_list_page < 2:
        return []
    parsed = urlparse(seed_url)
    path = parsed.path
    if not path.endswith("/index.html"):
        return []
    base_path = path[: -len("index.html")]
    return [
        parsed._replace(path=f"{base_path}index_{page_num}.html").geturl()
        for page_num in range(2, max_list_page + 1)
    ]


def is_allowed_host(url: str, host_suffixes: tuple[str, ...]) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    return any(host == suffix or host.endswith("." + suffix) for suffix in host_suffixes)


def looks_crawlable(url: str) -> bool:
    path = urlparse(url).path.lower()
    if not path or path.endswith("/"):
        return True
    if path.endswith((".html", ".htm", ".shtml", ".shtm")):
        return True
    return False


def is_allowed_path(url: str, path_prefixes: tuple[str, ...]) -> bool:
    if not path_prefixes:
        return True
    path = urlparse(url).path
    return any(path.startswith(prefix) for prefix in path_prefixes)


def looks_like_article_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return bool(re.search(r"/\d{6,}\.(?:s?html?|shtm)$", path))


def make_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        }
    )
    return session


def fetch_html(session: requests.Session, url: str, timeout: float) -> str | None:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if content_type and "html" not in content_type and "text/plain" not in content_type:
        return None
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def parse_page(markup: str) -> PageParser:
    parser = PageParser()
    parser.feed(markup)
    parser.close()
    return parser


def pick_title(parser: PageParser) -> str:
    candidates = [
        parser.meta.get("og:title", ""),
        parser.meta.get("twitter:title", ""),
        *parser.heading_parts[:2],
        clean_text("".join(parser.title_parts)),
    ]
    for candidate in candidates:
        title = clean_text(candidate)
        if not title:
            continue
        for part in BAD_TITLE_PARTS:
            title = re.sub(rf"\s*[-_—|]\s*{re.escape(part)}.*$", "", title)
        title = title.strip(" -_|—")
        if text_len(title) >= 4:
            return title
    return ""


def pick_publish_date(parser: PageParser, markup: str) -> str:
    for key in (
        "article:published_time",
        "pubdate",
        "publishdate",
        "publish_date",
        "date",
        "createdate",
    ):
        value = parser.meta.get(key, "")
        if value:
            return value.strip()

    match = DATE_RE.search(markup)
    return match.group(0) if match else ""


def pick_source(parser: PageParser, markup: str) -> str:
    for key in ("source", "mediaid", "author"):
        value = parser.meta.get(key, "")
        if value:
            return clean_text(value)

    source_match = re.search(r"来源[:：]\s*([^<\n\r]{2,40})", markup)
    if source_match:
        return clean_text(source_match.group(1))
    return ""


def extract_article(markup: str, url: str, min_chars: int) -> Article | None:
    parser = parse_page(markup)
    title = pick_title(parser)
    blocks = []
    for block in parser.blocks:
        if block == title:
            continue
        if any(
            marker in block
            for marker in (
                "责任编辑",
                "分享到",
                "扫一扫",
                "上一篇",
                "下一篇",
                "纠错/举报",
                "互联网新闻信息服务许可证",
                "本网站刊登的新闻信息",
                "Copyright",
                "All Rights Reserved",
            )
        ):
            continue
        if text_len(block) >= 12:
            blocks.append(block)

    text = clean_text("\n\n".join(blocks))
    if text_len(text) < min_chars:
        return None

    if not title:
        title = text.splitlines()[0][:40]

    return Article(
        url=url,
        title=title,
        publish_date=pick_publish_date(parser, markup),
        source=pick_source(parser, markup),
        text=text,
    )


def safe_filename(text: str, max_length: int = 90) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:max_length] or "untitled"


def article_filename(article: Article) -> str:
    digest = hashlib.sha1(article.url.encode("utf-8")).hexdigest()[:10]
    date_part = ""
    date_match = re.search(r"20\d{2}[-年]\d{1,2}[-月]\d{1,2}", article.publish_date)
    if date_match:
        date_part = re.sub(r"\D+", "", date_match.group(0)) + "_"
    return f"{date_part}{safe_filename(article.title)}_{digest}.txt"


def format_article(article: Article) -> str:
    header = [
        article.title,
        f"来源：{article.source}" if article.source else "",
        f"发布时间：{article.publish_date}" if article.publish_date else "",
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


def make_robot_parser(seed_url: str, user_agent: str) -> RobotFileParser:
    parsed = urlparse(seed_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    robot_parser = RobotFileParser(robots_url)
    robot_parser.set_url(robots_url)
    try:
        robot_parser.read()
    except Exception:
        robot_parser = RobotFileParser()
        robot_parser.parse([])
    return robot_parser


def iter_seed_urls(args: argparse.Namespace) -> Iterable[str]:
    for seed in args.seed:
        normalized = normalize_url(seed)
        if normalized:
            yield normalized
    if args.seed_file:
        with Path(args.seed_file).open("r", encoding="utf-8") as f:
            for line in f:
                normalized = normalize_url(line.strip())
                if normalized:
                    yield normalized


def crawl(args: argparse.Namespace) -> None:
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / args.index_name

    host_suffixes = tuple(args.host_suffix)
    session = make_session(args.user_agent)
    queue = deque((url, 0) for url in iter_seed_urls(args))
    seen_pages = load_seen_urls(index_path)
    saved_content_hashes: set[str] = set()
    robots_by_host: dict[str, RobotFileParser] = {}
    saved_count = 0
    fetched_count = 0

    while queue and fetched_count < args.max_pages:
        url, depth = queue.popleft()
        if url in seen_pages:
            continue
        if not is_allowed_host(url, host_suffixes) or not looks_crawlable(url):
            continue
        if not is_allowed_path(url, args.path_prefix):
            continue

        host = urlparse(url).netloc.lower()
        if args.respect_robots:
            robot_parser = robots_by_host.get(host)
            if robot_parser is None:
                robot_parser = make_robot_parser(url, args.user_agent)
                robots_by_host[host] = robot_parser
            if not robot_parser.can_fetch(args.user_agent, url):
                print(f"[robots] skip {url}")
                seen_pages.add(url)
                continue

        try:
            markup = fetch_html(session, url, args.timeout)
        except Exception as exc:
            print(f"[error] {url} -> {exc}")
            seen_pages.add(url)
            continue

        fetched_count += 1
        seen_pages.add(url)
        if not markup:
            continue

        parser = parse_page(markup)
        if depth < args.max_depth:
            article_urls: list[str] = []
            page_urls: list[str] = []
            for href in parser.links:
                next_url = normalize_url(href, url)
                if not next_url:
                    continue
                if next_url in seen_pages:
                    continue
                if (
                    is_allowed_host(next_url, host_suffixes)
                    and looks_crawlable(next_url)
                    and is_allowed_path(next_url, args.path_prefix)
                ):
                    if looks_like_article_url(next_url):
                        article_urls.append(next_url)
                    else:
                        page_urls.append(next_url)
            for next_url in page_urls:
                queue.append((next_url, depth + 1))
            for next_url in reversed(article_urls):
                queue.appendleft((next_url, depth + 1))

        if not looks_like_article_url(url):
            print(f"[page] {fetched_count}/{args.max_pages} {url}")
            time.sleep(args.delay)
            continue

        article = extract_article(markup, url, args.min_chars)
        if article is None:
            print(f"[skip] {url}")
            time.sleep(args.delay)
            continue

        content = format_article(article)
        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
        if content_hash in saved_content_hashes:
            print(f"[dup] {article.title}")
            time.sleep(args.delay)
            continue
        saved_content_hashes.add(content_hash)

        file_path = output_dir / article_filename(article)
        if file_path.exists() and not args.overwrite:
            print(f"[exists] {file_path.name}")
            time.sleep(args.delay)
            continue

        file_path.write_text(content + "\n", encoding="utf-8")
        append_index(index_path, article, file_path)
        saved_count += 1
        print(f"[saved] {saved_count} {article.title}")
        time.sleep(args.delay)

    print(f"Fetched pages: {fetched_count}")
    print(f"Saved articles: {saved_count}")
    print(f"Output directory: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl public China Military Online (81.cn) pages and save article text as TXT files."
    )
    parser.add_argument(
        "--seed",
        action="append",
        default=[],
        help="Seed URL. Can be passed multiple times. Defaults to https://www.81.cn/.",
    )
    parser.add_argument("--seed-file", help="Optional text file containing one seed URL per line.")
    parser.add_argument(
        "--section",
        choices=sorted(SECTION_PRESETS),
        help="Use a preset 81.cn section: 11/yw, 12/xx, 13/ll, 14/pl, or 15/ss.",
    )
    parser.add_argument(
        "--max-list-pages",
        type=int,
        help="Highest section list page to seed, e.g. 5 adds index_2.html through index_5.html.",
    )
    parser.add_argument(
        "--allow-cross-section",
        action="store_true",
        help="When --section is used, allow following 81.cn links outside that section.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Directory for downloaded TXT articles.",
    )
    parser.add_argument("--max-pages", type=int, default=200, help="Maximum pages to fetch.")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum crawl depth from seeds.")
    parser.add_argument("--min-chars", type=int, default=200, help="Minimum article body length.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--host-suffix",
        action="append",
        default=[],
        help="Allowed host suffix. Defaults to 81.cn. Can be passed multiple times.",
    )
    parser.add_argument(
        "--user-agent",
        default="sft-data-research-crawler/1.0 (+local dataset construction)",
        help="User-Agent sent with HTTP requests.",
    )
    parser.add_argument(
        "--index-name",
        default="_crawl_index.jsonl",
        help="Index file written under the output directory.",
    )
    parser.add_argument(
        "--ignore-robots",
        dest="respect_robots",
        action="store_false",
        help="Do not check robots.txt before fetching.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing TXT files.")
    args = parser.parse_args()

    if args.section:
        seed_url, output_dir = SECTION_PRESETS[args.section]
        if not args.seed and not args.seed_file:
            max_list_page = args.max_list_pages or SECTION_LIST_PAGE_LIMITS[args.section]
            args.seed = [seed_url] + make_section_list_pages(seed_url, max_list_page)
        if args.output is None:
            args.output = output_dir
        args.path_prefix = (
            ()
            if args.allow_cross_section
            else SECTION_PATH_PREFIXES[args.section]
        )
    else:
        args.path_prefix = ()
    if args.output is None:
        args.output = DEFAULT_OUTPUT
    if not args.seed and not args.seed_file:
        args.seed = DEFAULT_SEEDS.copy()
    if not args.host_suffix:
        args.host_suffix = list(ALLOWED_HOST_SUFFIXES)
    if args.max_pages <= 0:
        raise ValueError("--max-pages must be greater than 0")
    if args.max_depth < 0:
        raise ValueError("--max-depth must be greater than or equal to 0")
    if args.min_chars <= 0:
        raise ValueError("--min-chars must be greater than 0")
    if args.delay < 0:
        raise ValueError("--delay must be greater than or equal to 0")
    return args


def main() -> None:
    crawl(parse_args())


if __name__ == "__main__":
    main()
