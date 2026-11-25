#!/usr/bin/env python3
"""AI 前沿一手源头情报抓取与规范化脚本（仅依赖 Python 3 标准库）。

聚合推文提及的 7 个一手 AI 源头：
- 日报与周报（briefings）：AI News (news.smol.ai -> latent.space)、The Batch (DeepLearning.AI)
- 热门与最新论文（papers）：Hugging Face Daily Papers、arXiv cs.AI（每篇附带 alphaXiv 讨论区直达）
- 常驻评测与源头工具卡（benchmarks）：LMArena、Artificial Analysis、alphaXiv、arXiv cs.AI
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_RADAR_PATH = ROOT_DIR / "data" / "ai_radar.json"

AI_NEWS_HOME_URL = "https://news.smol.ai/"
THE_BATCH_HOME_URL = "https://www.deeplearning.ai/the-batch/"
HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"
ARXIV_API_URL = (
    "https://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=18"
)

HTTP_TIMEOUT_SEC = 15
DETAIL_TIMEOUT_SEC = 10
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, application/xml, text/xml, text/html, */*;q=0.8",
}

TAG_STRIP_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
POST_CARD_RE = re.compile(r'<article\s+class="post-card[^"]*"[^>]*>(.*?)</article>', re.S)
EYEBROW_RE = re.compile(r'<span[^>]*class="eyebrow[^"]*"[^>]*>(.*?)</span>', re.S)
TITLE_LINK_RE = re.compile(r'<h3>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>\s*</h3>', re.S)
TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.S)
READ_TIME_RE = re.compile(r"(\d+\s*min\s*read)", re.I)
ISSUE_NUM_RE = re.compile(r"/the-batch/issue-(\d+)/?")

BENCHMARKS: list[dict[str, Any]] = [
    {
        "id": "tool-lmarena",
        "name": "LMArena（大模型真人盲测）",
        "category": "真人盲测",
        "description": "大模型真人盲测 Elo 排名，不同模型硬碰硬直接看真实体感，把厂商自吹跑分放一边。",
        "url": "https://arena.ai",
        "mirrorUrl": "https://huggingface.co/spaces/lmarena-ai/arena-leaderboard",
        "mirrorLabel": "HF 榜单入口",
        "tags": ["真人盲测", "Elo榜单", "选模型必备"],
    },
    {
        "id": "tool-artificial-analysis",
        "name": "Artificial Analysis（质量/速度/价格横评）",
        "category": "性价比横评",
        "description": "将主流大模型与 API 供应商的质量、吞吐速度、延迟和价格并排横向对比，领免费额度或选付费 API 一眼见分晓。",
        "url": "https://artificialanalysis.ai",
        "mirrorUrl": "https://artificialanalysis.ai/leaderboards/models",
        "mirrorLabel": "模型总榜",
        "tags": ["价格对比", "速度评测", "API选型"],
    },
    {
        "id": "tool-alphaxiv",
        "name": "alphaXiv（论文评论区）",
        "category": "同行评议",
        "description": "把 arXiv 论文变成同行评论区，看研究者怎么拆解、挑刺与复现；下方每篇论文卡片均已内置直达对应 alphaXiv 讨论页的按钮。",
        "url": "https://www.alphaxiv.org",
        "mirrorUrl": None,
        "mirrorLabel": None,
        "tags": ["同行讨论", "论文解读", "卡片直达"],
    },
    {
        "id": "tool-arxiv-csai",
        "name": "arXiv cs.AI（一手论文源头）",
        "category": "预印本源头",
        "description": "最原始的一手 AI 论文发布列表，新研究常先在这里冒头，比二三手转述更快一步。",
        "url": "https://arxiv.org/list/cs.AI/recent",
        "mirrorUrl": None,
        "mirrorLabel": None,
        "tags": ["一手论文", "每日更新"],
    },
]


def clean_text(raw: str | None) -> str:
    """去除 HTML 标签、反转义实体并折叠空白字符。"""
    if not raw:
        return ""
    no_tags = TAG_STRIP_RE.sub(" ", raw)
    unescaped = html.unescape(no_tags)
    return WHITESPACE_RE.sub(" ", unescaped).strip()


def truncate(text: str, limit: int = 280) -> str:
    """按上限截断摘要并保留省略号。"""
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def to_iso_utc(dt: datetime) -> str:
    """将 datetime 格式化为以 Z 结尾的 UTC ISO-8601 字符串。"""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(raw: str | None, fallback: datetime) -> str:
    """解析常见 ISO 日期时间字符串并标准化为 UTC ISO-8601。"""
    if not raw:
        return to_iso_utc(fallback)
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return to_iso_utc(dt)
    except ValueError:
        return to_iso_utc(fallback)


def make_id(prefix: str, unique_key: str) -> str:
    """生成稳定、无碰撞的条目 ID。"""
    digest = hashlib.sha1(unique_key.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def fetch_url(url: str, timeout: int = HTTP_TIMEOUT_SEC) -> tuple[str, str]:
    """拉取网页或接口文本，返回 (最终重定向后 URL, UTF-8 文本)。"""
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        raw = resp.read()
        return final_url, raw.decode("utf-8", errors="replace")


def extract_meta_content(page_html: str, keys: tuple[str, ...]) -> str:
    """提取 HTML meta 标签（property 或 name）对应的 content 属性。"""
    for meta_tag in re.findall(r"<meta\b[^>]*>", page_html, re.I):
        attr_match = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', meta_tag, re.I)
        if not attr_match or attr_match.group(1).lower() not in keys:
            continue
        content_match = re.search(r'content\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', meta_tag, re.I)
        if content_match:
            val = content_match.group(1) if content_match.group(1) is not None else content_match.group(2)
            cleaned = clean_text(val)
            if cleaned:
                return cleaned
    return ""


def fetch_ai_news(now_utc: datetime, limit: int = 8) -> list[dict[str, Any]]:
    """抓取 AI News（news.smol.ai 跳转至 latent.space/news/ 的最新文章卡片与摘要）。"""
    final_url, page_html = fetch_url(AI_NEWS_HOME_URL)
    cards = POST_CARD_RE.findall(page_html)
    if not cards:
        raise ValueError("AI News 页面未解析到 post-card 文章卡片")

    candidates: list[dict[str, Any]] = []
    fallback_candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for block in cards:
        link_match = TITLE_LINK_RE.search(block)
        if not link_match:
            continue
        href, raw_title = link_match.group(1), link_match.group(2)
        title = clean_text(raw_title)
        if not title:
            continue
        full_url = urllib.parse.urljoin(final_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        eyebrow_match = EYEBROW_RE.search(block)
        eyebrow = clean_text(eyebrow_match.group(1)) if eyebrow_match else ""
        time_match = TIME_RE.search(block)
        pub_iso = parse_iso_utc(time_match.group(1) if time_match else None, now_utc)
        rt_match = READ_TIME_RE.search(block)
        read_time = clean_text(rt_match.group(1)) if rt_match else None

        entry = {
            "title": title,
            "url": full_url,
            "eyebrow": eyebrow,
            "readTime": read_time,
            "publishedAt": pub_iso,
        }
        is_ainews = "ai news" in eyebrow.lower() or "/p/ainews-" in href.lower()
        if is_ainews:
            candidates.append(entry)
        else:
            fallback_candidates.append(entry)

    selected = candidates[:limit] if len(candidates) >= 3 else (candidates + fallback_candidates)[:limit]
    if not selected:
        raise ValueError("AI News 未匹配到有效文章条目")

    def _fetch_desc(item: dict[str, Any]) -> str:
        try:
            _, art_html = fetch_url(item["url"], timeout=DETAIL_TIMEOUT_SEC)
            desc = extract_meta_content(art_html, ("description", "og:description", "twitter:description"))
            if desc:
                return truncate(desc, 280)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        suffix = f"（{item['readTime']}）" if item["readTime"] else ""
        return f"AI News 每日 AI 社区、模型与论文一手动态汇总{suffix}。"

    with ThreadPoolExecutor(max_workers=6) as pool:
        summaries = list(pool.map(_fetch_desc, selected))

    items: list[dict[str, Any]] = []
    for entry, summary in zip(selected, summaries):
        tags = ["AI日报", "社区一手动态"]
        if entry["readTime"]:
            tags.append(entry["readTime"])
        items.append(
            {
                "id": make_id("ainews", entry["url"]),
                "section": "briefings",
                "sourceId": "ai_news",
                "sourceName": "AI News",
                "title": entry["title"],
                "summary": summary,
                "url": entry["url"],
                "arxivId": None,
                "arxivUrl": None,
                "alphaXivUrl": None,
                "githubUrl": None,
                "upvotes": None,
                "readTime": entry["readTime"],
                "tags": tags[:4],
                "publishedAt": entry["publishedAt"],
            }
        )

    items.sort(key=lambda x: x["publishedAt"], reverse=True)
    return items


def fetch_the_batch(now_utc: datetime, limit: int = 4) -> list[dict[str, Any]]:
    """抓取 DeepLearning.AI The Batch 最新若干期周报。"""
    _, home_html = fetch_url(THE_BATCH_HOME_URL)
    issue_nums = sorted({int(n) for n in ISSUE_NUM_RE.findall(home_html)}, reverse=True)[:limit]
    if not issue_nums:
        raise ValueError("The Batch 首页未匹配到 issue 期号")

    def _fetch_issue(num: int) -> dict[str, Any] | None:
        issue_url = f"https://www.deeplearning.ai/the-batch/issue-{num}/"
        try:
            _, issue_html = fetch_url(issue_url, timeout=DETAIL_TIMEOUT_SEC)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

        title = extract_meta_content(issue_html, ("og:title", "twitter:title"))
        if not title:
            t_match = re.search(r"<title[^>]*>(.*?)</title>", issue_html, re.S | re.I)
            title = clean_text(t_match.group(1)) if t_match else f"The Batch Issue #{num}"

        desc = extract_meta_content(issue_html, ("og:description", "description", "twitter:description"))
        desc = re.sub(r"^The Batch News\s*&\s*Insights:\s*", "", desc, flags=re.I).strip()
        summary = truncate(desc, 280) if desc else f"吴恩达团队 The Batch 第 {num} 期 AI 周报与行业趋势解读。"

        pub_raw = extract_meta_content(issue_html, ("article:published_time",))
        pub_iso = parse_iso_utc(pub_raw, now_utc)

        return {
            "id": f"thebatch-issue-{num}",
            "section": "briefings",
            "sourceId": "the_batch",
            "sourceName": "The Batch",
            "title": f"Issue #{num}｜{title}",
            "summary": summary,
            "url": issue_url,
            "arxivId": None,
            "arxivUrl": None,
            "alphaXivUrl": None,
            "githubUrl": None,
            "upvotes": None,
            "readTime": None,
            "tags": ["AI周报", f"Issue #{num}", "吴恩达团队"],
            "publishedAt": pub_iso,
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [item for item in pool.map(_fetch_issue, issue_nums) if item is not None]

    if not results:
        raise ValueError("The Batch 各期详情页均拉取失败")
    results.sort(key=lambda x: x["publishedAt"], reverse=True)
    return results


def fetch_hf_papers(now_utc: datetime, limit: int = 12) -> tuple[list[dict[str, Any]], set[str]]:
    """抓取 Hugging Face Daily Papers 社区投票热门论文。"""
    _, raw_json = fetch_url(HF_DAILY_PAPERS_URL)
    rows = json.loads(raw_json)
    if not isinstance(rows, list) or not rows:
        raise ValueError("HF Daily Papers API 返回空列表")

    def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
        paper = row.get("paper") or {}
        upvotes = int(paper.get("upvotes") or 0)
        pub = str(row.get("publishedAt") or paper.get("publishedAt") or "")
        return (upvotes, pub)

    sorted_rows = sorted(rows, key=_sort_key, reverse=True)
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for row in sorted_rows:
        paper = row.get("paper") or {}
        raw_id = str(paper.get("id") or "").strip()
        arxiv_id = re.sub(r"v\d+$", "", raw_id)
        if not arxiv_id or arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)

        title = clean_text(row.get("title") or paper.get("title"))
        if not title:
            continue

        raw_summary = paper.get("ai_summary") or row.get("summary") or paper.get("summary") or ""
        summary = truncate(raw_summary, 280) or "Hugging Face 社区热门投票论文。"
        github_url = paper.get("githubRepo") or None
        upvotes = int(paper.get("upvotes") or 0)

        keywords = [clean_text(k) for k in (paper.get("ai_keywords") or []) if clean_text(k)]
        tags = keywords[:3]
        if github_url and "开源代码" not in tags:
            tags.append("开源代码")
        if not tags:
            tags = ["热门论文"]

        pub_iso = parse_iso_utc(row.get("publishedAt") or paper.get("publishedAt"), now_utc)
        items.append(
            {
                "id": f"hf-{arxiv_id}",
                "section": "papers",
                "sourceId": "hf_papers",
                "sourceName": "HF Papers",
                "title": title,
                "summary": summary,
                "url": f"https://huggingface.co/papers/{arxiv_id}",
                "arxivId": arxiv_id,
                "arxivUrl": f"https://arxiv.org/abs/{arxiv_id}",
                "alphaXivUrl": f"https://www.alphaxiv.org/abs/{arxiv_id}",
                "githubUrl": github_url,
                "upvotes": upvotes,
                "readTime": None,
                "tags": tags[:4],
                "publishedAt": pub_iso,
            }
        )
        if len(items) >= limit:
            break

    if not items:
        raise ValueError("HF Daily Papers 未解析到有效论文")
    return items, seen_ids


def fetch_arxiv_ai(now_utc: datetime, exclude_ids: set[str], limit: int = 8) -> list[dict[str, Any]]:
    """抓取 arXiv cs.AI 最新一手预印本（自动过滤与 HF Papers 重复的论文）。"""
    _, atom_xml = fetch_url(ARXIV_API_URL)
    root = ET.fromstring(atom_xml)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall("a:entry", ns)
    if not entries:
        raise ValueError("arXiv API 未返回 cs.AI 论文条目")

    items: list[dict[str, Any]] = []
    seen_ids = set(exclude_ids)

    for entry in entries:
        raw_id_url = (entry.findtext("a:id", "", ns) or "").strip()
        tail = raw_id_url.rstrip("/").split("/")[-1]
        arxiv_id = re.sub(r"v\d+$", "", tail)
        if not arxiv_id or arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)

        title = clean_text(entry.findtext("a:title", "", ns))
        summary = truncate(entry.findtext("a:summary", "", ns), 280)
        if not title:
            continue

        pub_iso = parse_iso_utc(entry.findtext("a:published", "", ns), now_utc)
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
        items.append(
            {
                "id": f"arxiv-{arxiv_id}",
                "section": "papers",
                "sourceId": "arxiv_ai",
                "sourceName": "arXiv cs.AI",
                "title": title,
                "summary": summary,
                "url": arxiv_url,
                "arxivId": arxiv_id,
                "arxivUrl": arxiv_url,
                "alphaXivUrl": f"https://www.alphaxiv.org/abs/{arxiv_id}",
                "githubUrl": None,
                "upvotes": None,
                "readTime": None,
                "tags": ["cs.AI", "一手预印本"],
                "publishedAt": pub_iso,
            }
        )
        if len(items) >= limit:
            break

    if not items:
        raise ValueError("arXiv cs.AI 去重后无可用条目")
    return items


def main() -> int:
    """执行 AI 前沿源头全量抓取并写入 data/ai_radar.json。"""
    now_utc = datetime.now(timezone.utc)
    sources_status: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    hf_ids: set[str] = set()

    def _run_source(source_id: str, source_name: str, fn: Any) -> list[dict[str, Any]]:
        try:
            result = fn()
            sources_status.append(
                {
                    "id": source_id,
                    "name": source_name,
                    "ok": True,
                    "count": len(result),
                    "error": None,
                }
            )
            return result
        except (urllib.error.URLError, ET.ParseError, json.JSONDecodeError, TimeoutError, OSError, ValueError) as exc:
            sources_status.append(
                {
                    "id": source_id,
                    "name": source_name,
                    "ok": False,
                    "count": 0,
                    "error": str(exc)[:200],
                }
            )
            return []

    collected.extend(_run_source("ai_news", "AI News (smol.ai)", lambda: fetch_ai_news(now_utc)))
    collected.extend(_run_source("the_batch", "The Batch (DeepLearning.AI)", lambda: fetch_the_batch(now_utc)))

    def _run_hf() -> list[dict[str, Any]]:
        nonlocal hf_ids
        items, hf_ids = fetch_hf_papers(now_utc)
        return items

    collected.extend(_run_source("hf_papers", "Hugging Face Papers", _run_hf))
    collected.extend(_run_source("arxiv_ai", "arXiv cs.AI 最新", lambda: fetch_arxiv_ai(now_utc, hf_ids)))

    payload = {
        "schemaVersion": "1.0",
        "updatedAt": to_iso_utc(now_utc),
        "total": len(collected),
        "sources": sources_status,
        "benchmarks": BENCHMARKS,
        "items": collected,
    }

    OUTPUT_RADAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_RADAR_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    ok_count = sum(1 for s in sources_status if s["ok"])
    print(f"已更新 {OUTPUT_RADAR_PATH}：共 {len(collected)} 条前沿情报，成功数据源 {ok_count}/{len(sources_status)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
