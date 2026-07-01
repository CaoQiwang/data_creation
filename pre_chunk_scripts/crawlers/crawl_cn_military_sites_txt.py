from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Examples:
# python pre_chunk_scripts\crawlers\crawl_cn_military_sites_txt.py --preset all --output-root raw_data\txt\2
# python pre_chunk_scripts\crawlers\crawl_cn_military_sites_txt.py --preset 81cn --max-pages 3000 --max-depth 3

DEFAULT_OUTPUT_ROOT = "raw_data/txt/2"
DEFAULT_USER_AGENT = "sft-data-research-crawler/1.0 (+local dataset construction)"

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"[ \t\u3000]+")
NEWLINE_RE = re.compile(r"\n{3,}")
DATE_RE = re.compile(
    r"20\d{2}年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2})?"
    r"|20\d{2}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2})?"
    r"|20\d{2}/\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2})?"
)
SOURCE_RE = re.compile(r"(?:来源|稿件来源|信息来源)\s*[:：]\s*([^<\n\r]{2,60})")


SITE_PRESETS = {
    "81cn": {
        "label": "中国军网",
        "output": "cn_military_81cn",
        "host_suffixes": ("81.cn",),
        "path_prefixes": (
            "/yw_208727/",
            "/xx_207779/",
            "/ll_208543/",
            "/pl_208541/",
            "/ss_208539/",
            "/bz_208549/",
            "/jw_208551/",
            "/zq_208553/",
            "/lj_208555/",
            "/hj_208557/",
            "/kj_208559/",
            "/hjj_208561/",
            "/wjj_208563/",
            "/byds_206407/",
        ),
        "seeds": (
            "http://www.81.cn/yw_208727/index.html",
            "http://www.81.cn/xx_207779/index.html",
            "http://www.81.cn/ll_208543/index.html",
            "http://www.81.cn/pl_208541/index.html",
            "http://www.81.cn/ss_208539/index.html",
            "http://www.81.cn/bz_208549/index.html",
            "http://www.81.cn/jw_208551/index.html",
            "http://www.81.cn/zq_208553/index.html",
            "http://www.81.cn/lj_208555/index.html",
            "http://www.81.cn/hj_208557/index.html",
            "http://www.81.cn/kj_208559/index.html",
            "http://www.81.cn/hjj_208561/index.html",
            "http://www.81.cn/wjj_208563/index.html",
        ),
        "article_regex": r"/\d{6,}\.(?:s?html?|shtm)$",
        "list_pages": 30,
    },
    "mod": {
        "label": "国防部",
        "output": "cn_military_mod",
        "host_suffixes": ("mod.gov.cn",),
        "path_prefixes": ("/gfbw/", "/jmsd/", "/wqzb/", "/zt/"),
        "seeds": (
            "http://www.mod.gov.cn/gfbw/qwfb/index.html",
            "http://www.mod.gov.cn/gfbw/qwfb/jwbgt_214033/index.html",
            "http://www.mod.gov.cn/gfbw/qwfb/jwlhcmb_214034/index.html",
            "http://www.mod.gov.cn/gfbw/xwfyr/index.html",
            "http://www.mod.gov.cn/gfbw/jsxd/index.html",
            "http://www.mod.gov.cn/gfbw/gc/index.html",
        ),
        "article_regex": r"/\d{6,}\.(?:s?html?|shtm)$",
        "list_pages": 20,
    },
    "people_military": {
        "label": "人民网军事",
        "output": "cn_military_people",
        "host_suffixes": ("people.com.cn",),
        "path_prefixes": ("/",),
        "seeds": (
            "http://military.people.com.cn/",
            "http://military.people.com.cn/GB/172467/index.html",
            "http://military.people.com.cn/GB/52936/index.html",
            "http://military.people.com.cn/GB/1076/index.html",
        ),
        "article_regex": r"/n1/20\d{2}/\d{4}/c\d+-\d+\.html$",
        "list_pages": 15,
    },
    "cctv_military": {
        "label": "央视军事",
        "output": "cn_military_cctv",
        "host_suffixes": ("cctv.com",),
        "path_prefixes": ("/",),
        "seeds": (
            "https://military.cctv.com/",
            "https://military.cctv.com/yaowen/index.shtml",
            "https://military.cctv.com/china/index.shtml",
        ),
        "article_regex": r"/20\d{2}/\d{2}/\d{2}/ARTI[^/]+\.shtml$",
        "list_pages": 20,
    },
    "xinhua_mil": {
        "label": "新华社军事",
        "output": "cn_military_xinhua",
        "host_suffixes": ("news.cn", "xinhuanet.com"),
        "path_prefixes": ("/mil/",),
        "seeds": (
            "http://www.news.cn/mil/index.htm",
            "http://www.news.cn/mil/yaowen.htm",
            "http://www.news.cn/mil/zhongguo.htm",
            "http://www.news.cn/mil/guandian.htm",
            "http://www.news.cn/mil/guofangdongyuan.htm",
            "http://www.news.cn/mil/junminronghe.htm",
        ),
        "article_regex": r"/mil/(?:20\d{2}-\d{2}/\d{2}|20\d{2}-\d{2}-\d{2})/c_\d+\.htm$",
        "list_pages": 10,
    },
}


@dataclass
class Article:
    url: str
    title: str
    publish_date: str
    source: str
    site: str
    text: str


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.blocks: list[str] = []
        self._in_title = False
        self._current_block: list[str] | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if tag in {"script", "style", "noscript", "svg", "iframe"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
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
        elif tag in {"h1", "h2", "h3", "p", "li"}:
            self._current_block = []
        elif tag == "br" and self._current_block is not None:
            self._current_block.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "iframe"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
        elif tag in {"h1", "h2", "h3", "p", "li"}:
            text = clean_text("".join(self._current_block or []))
            if text:
                if tag in {"h1", "h2", "h3"}:
                    self.heading_parts.append(text)
                self.blocks.append(text)
            self._current_block = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
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


def parse_page(markup: str) -> PageParser:
    parser = PageParser()
    parser.feed(markup)
    parser.close()
    return parser


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    if not url:
        return None
    url = url.replace("&amp;", "&").strip()
    if base_url:
        url = urljoin(base_url, url)
    url, _fragment = urldefrag(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return parsed.geturl()


def is_allowed_host(url: str, host_suffixes: tuple[str, ...]) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    return any(host == suffix or host.endswith("." + suffix) for suffix in host_suffixes)


def is_allowed_path(url: str, path_prefixes: tuple[str, ...]) -> bool:
    if not path_prefixes:
        return True
    path = urlparse(url).path
    return any(path.startswith(prefix) for prefix in path_prefixes)


def looks_crawlable(url: str) -> bool:
    path = urlparse(url).path.lower()
    if not path or path.endswith("/"):
        return True
    return path.endswith((".html", ".htm", ".shtml", ".shtm"))


def looks_like_article(url: str, article_pattern: re.Pattern[str]) -> bool:
    return bool(article_pattern.search(urlparse(url).path))


def make_list_pages(seed_url: str, max_page: int) -> list[str]:
    if max_page < 2:
        return []
    parsed = urlparse(seed_url)
    path = parsed.path
    if path.endswith("/index.html"):
        base = path[: -len("index.html")]
        return [parsed._replace(path=f"{base}index_{i}.html").geturl() for i in range(2, max_page + 1)]
    if path.endswith("/index.shtml"):
        base = path[: -len("index.shtml")]
        return [parsed._replace(path=f"{base}index_{i}.shtml").geturl() for i in range(2, max_page + 1)]
    return []


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
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def pick_title(parser: PageParser) -> str:
    page_title = clean_text("".join(parser.title_parts))
    candidates = [
        parser.meta.get("og:title", ""),
        parser.meta.get("twitter:title", ""),
        parser.meta.get("title", ""),
        page_title,
        *parser.heading_parts[:5],
    ]
    bad_parts = ("中国军网", "国防部", "军事", "人民网", "央视网", "新华网", "新华社", "中国新闻网")
    generic_titles = {
        "人民日报报系",
        "无标题文档",
        "要闻推荐\nWe Recommend",
        "要闻推荐 We Recommend",
    }
    for candidate in candidates:
        title = clean_text(candidate)
        if not title:
            continue
        title = re.sub(r"\s*--.*$", "", title)
        title = re.sub(r"\s*-\s*(?:中国军网|国防部|人民网|央视网|新华网|新华社).*$", "", title)
        for part in bad_parts:
            title = re.sub(rf"\s*[-_|—_]\s*{re.escape(part)}.*$", "", title)
        title = title.strip(" -_|—_")
        if title in generic_titles:
            continue
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
        "publish-time",
    ):
        value = parser.meta.get(key, "")
        if value:
            return clean_text(value)
    match = DATE_RE.search(markup)
    return match.group(0) if match else ""


def pick_source(parser: PageParser, markup: str, default_source: str) -> str:
    for key in ("source", "mediaid", "author", "og:site_name"):
        value = parser.meta.get(key, "")
        if value:
            return clean_text(value)
    match = SOURCE_RE.search(markup)
    if match:
        return clean_text(match.group(1))
    return default_source


def extract_article(markup: str, url: str, site_label: str, min_chars: int) -> Article | None:
    parser = parse_page(markup)
    title = pick_title(parser)
    blocks: list[str] = []
    seen_blocks: set[str] = set()
    skip_markers = (
        "责任编辑",
        "编辑：",
        "分享到",
        "扫一扫",
        "上一篇",
        "下一篇",
        "版权声明",
        "违法和不良信息",
        "Copyright",
        "All Rights Reserved",
        "客户端",
        "微信公众号",
    )
    for block in parser.blocks:
        block = clean_text(block)
        if not block or block == title:
            continue
        if any(marker in block for marker in skip_markers):
            continue
        if text_len(block) < 8:
            continue
        if block in seen_blocks:
            continue
        seen_blocks.add(block)
        blocks.append(block)
    text = clean_text("\n\n".join(blocks))
    if text_len(text) < min_chars:
        return None
    if not title:
        title = text.splitlines()[0][:50]
    return Article(
        url=url,
        title=title,
        publish_date=pick_publish_date(parser, markup),
        source=pick_source(parser, markup, site_label),
        site=site_label,
        text=text,
    )


def safe_filename(text: str, max_length: int = 90) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:max_length] or "untitled"


def article_filename(article: Article) -> str:
    digest = hashlib.sha1(article.url.encode("utf-8")).hexdigest()[:10]
    date_match = re.search(r"20\d{2}[-年/]\d{1,2}[-月/]\d{1,2}", article.publish_date)
    date_part = ""
    if date_match:
        date_part = re.sub(r"\D+", "", date_match.group(0)) + "_"
    return f"{date_part}{safe_filename(article.title)}_{digest}.txt"


def format_article(article: Article) -> str:
    header = [
        article.title,
        f"来源：{article.source}" if article.source else "",
        f"发布日期：{article.publish_date}" if article.publish_date else "",
        f"站点：{article.site}" if article.site else "",
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


def iter_initial_seeds(preset: dict, extra_seeds: list[str]) -> Iterable[str]:
    for seed in preset["seeds"]:
        normalized = normalize_url(seed)
        if normalized:
            yield normalized
        for page in make_list_pages(seed, int(preset.get("list_pages", 0))):
            yield page
    for seed in extra_seeds:
        normalized = normalize_url(seed)
        if normalized:
            yield normalized


def crawl_preset(args: argparse.Namespace, preset_name: str) -> tuple[int, int]:
    preset = SITE_PRESETS[preset_name]
    site_label = str(preset["label"])
    output_dir = Path(args.output_root, str(preset["output"])).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / args.index_name

    host_suffixes = tuple(preset["host_suffixes"])
    path_prefixes = tuple(preset["path_prefixes"])
    article_pattern = re.compile(str(preset["article_regex"]), re.I)
    session = make_session(args.user_agent)

    queue = deque((url, 0) for url in iter_initial_seeds(preset, args.seed))
    seen_pages = load_seen_urls(index_path)
    queued_urls = {url for url, _depth in queue}
    saved_hashes: set[str] = set()
    fetched_count = 0
    saved_count = 0

    while queue and fetched_count < args.max_pages:
        url, depth = queue.popleft()
        queued_urls.discard(url)
        if url in seen_pages:
            continue
        if not is_allowed_host(url, host_suffixes):
            continue
        if not is_allowed_path(url, path_prefixes):
            continue
        if not looks_crawlable(url):
            continue

        try:
            markup = fetch_html(session, url, args.timeout)
        except Exception as exc:
            print(f"[{preset_name}][error] {url} -> {exc}")
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
                if not next_url or next_url in seen_pages or next_url in queued_urls:
                    continue
                if not is_allowed_host(next_url, host_suffixes):
                    continue
                if not is_allowed_path(next_url, path_prefixes):
                    continue
                if not looks_crawlable(next_url):
                    continue
                if looks_like_article(next_url, article_pattern):
                    article_urls.append(next_url)
                else:
                    page_urls.append(next_url)
            for next_url in page_urls[: args.max_links_per_page]:
                queue.append((next_url, depth + 1))
                queued_urls.add(next_url)
            for next_url in reversed(article_urls[: args.max_links_per_page]):
                queue.appendleft((next_url, depth + 1))
                queued_urls.add(next_url)

        if not looks_like_article(url, article_pattern):
            if args.verbose:
                print(f"[{preset_name}][page] {fetched_count}/{args.max_pages} {url}")
            time.sleep(args.delay)
            continue

        article = extract_article(markup, url, site_label, args.min_chars)
        if article is None:
            print(f"[{preset_name}][skip] {url}")
            time.sleep(args.delay)
            continue

        content = format_article(article)
        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
        if content_hash in saved_hashes:
            time.sleep(args.delay)
            continue
        saved_hashes.add(content_hash)

        file_path = output_dir / article_filename(article)
        if file_path.exists() and not args.overwrite:
            time.sleep(args.delay)
            continue

        file_path.write_text(content + "\n", encoding="utf-8")
        append_index(index_path, article, file_path)
        saved_count += 1
        print(f"[{preset_name}][saved] {saved_count} {article.title}")
        time.sleep(args.delay)

    print(f"[{preset_name}] Fetched pages: {fetched_count}")
    print(f"[{preset_name}] Saved articles: {saved_count}")
    print(f"[{preset_name}] Output directory: {output_dir}")
    return fetched_count, saved_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl Chinese official/pro-official military news sites and save article text as TXT files."
    )
    parser.add_argument(
        "--preset",
        action="append",
        choices=["all", *sorted(SITE_PRESETS)],
        default=[],
        help="Site preset to crawl. Use all for every preset. Can be passed multiple times.",
    )
    parser.add_argument("--seed", action="append", default=[], help="Extra seed URL for the selected preset(s).")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Root directory for per-site outputs.")
    parser.add_argument("--max-pages", type=int, default=2000, help="Maximum pages to fetch per preset.")
    parser.add_argument("--max-depth", type=int, default=3, help="Maximum crawl depth from seeds.")
    parser.add_argument("--max-links-per-page", type=int, default=300, help="Maximum links queued from one page.")
    parser.add_argument("--min-chars", type=int, default=120, help="Minimum article body length.")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between requests in seconds.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent sent with HTTP requests.")
    parser.add_argument("--index-name", default="_crawl_index.jsonl", help="Index file name under each output dir.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing TXT files.")
    parser.add_argument("--verbose", action="store_true", help="Print list-page fetches.")
    args = parser.parse_args()

    if not args.preset:
        args.preset = ["all"]
    if "all" in args.preset:
        args.preset = list(SITE_PRESETS)
    else:
        args.preset = list(dict.fromkeys(args.preset))
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
    args = parse_args()
    total_fetched = 0
    total_saved = 0
    for preset_name in args.preset:
        fetched, saved = crawl_preset(args, preset_name)
        total_fetched += fetched
        total_saved += saved
    print(f"Total fetched pages: {total_fetched}")
    print(f"Total saved articles: {total_saved}")


if __name__ == "__main__":
    main()
