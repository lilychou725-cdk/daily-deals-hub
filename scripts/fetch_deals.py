#!/usr/bin/env python3
"""每日羊毛新闻聚合抓取与清洗脚本（仅依赖 Python 3 标准库）。"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

# 项目路径定义
ROOT_DIR = Path(__file__).resolve().parent.parent
MANUAL_DEALS_PATH = ROOT_DIR / "data" / "manual_deals.json"
OUTPUT_DEALS_PATH = ROOT_DIR / "data" / "deals.json"

HTTP_TIMEOUT_SEC = 12
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, application/xml, text/xml, */*;q=0.8",
}

# 过滤非优惠码的大写常见词与年份
COUPON_STOPWORDS = {
    "HTTP",
    "HTTPS",
    "HTML",
    "JSON",
    "XML",
    "NONE",
    "NULL",
    "TRUE",
    "FALSE",
    "UTF8",
    "UTF-8",
    "CODE",
    "PROMO",
    "COUPON",
    "FREE",
}

TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "fbclid",
    "gclid",
    "spm",
    "from",
}

COUPON_PATTERN = re.compile(
    r"(?i:优惠码|兑换码|折扣码|promo\s*code|coupon\s*code|coupon|code)"
    r"\s*(?i:is)?\s*[:：#是为]?\s*['\"`「【\[]?"
    r"([A-Z0-9][A-Z0-9\-]{3,23})(?![A-Za-z0-9\-])"
)

TAG_STRIP_PATTERN = re.compile(r"<[^>]+>")
BLOCK_BREAK_PATTERN = re.compile(r"(?i)<\s*(?:br\s*/?|/p|/div|/li|/tr|/h[1-6])\s*>")
SCRIPT_STYLE_PATTERN = re.compile(r"(?is)<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>")
WHITESPACE_PATTERN = re.compile(r"\s+")

# 分类关键词配置（ASCII 词走词边界匹配，中文词走子串匹配）
CATEGORY_RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "AI会员与额度",
        (
            "ai",
            "gpt",
            "chatgpt",
            "openai",
            "claude",
            "anthropic",
            "gemini",
            "token",
            "tokens",
            "api",
            "llm",
            "caffeine",
            "cursor",
            "copilot",
            "deepseek",
            "perplexity",
            "midjourney",
            "grok",
        ),
        ("额度", "模型", "大模型", "算力", "人工智能"),
    ),
    (
        "软件与云服务",
        (
            "vpn",
            "vps",
            "cloud",
            "domain",
            "app",
            "apps",
            "steam",
            "epic",
            "gog",
            "giveaway",
            "github",
            "license",
            "coupon",
            "compare",
            "software",
            "saas",
            "dlc",
            "xbox",
            "playstation",
            "switch",
        ),
        ("域名", "软件", "云服务", "服务器", "激活码", "限免", "小众软件", "正版", "会员"),
    ),
    (
        "黑五与促销",
        (
            "black friday",
            "cyber monday",
            "deal",
            "deals",
            "off",
            "discount",
            "sale",
            "slickdeals",
            "promo",
        ),
        ("黑五", "折扣", "神价", "促销", "满减", "特价", "优惠券", "立减"),
    ),
    (
        "生活与工具",
        ("cashback", "rebate"),
        ("话费", "红包", "支付宝", "立减金", "黄金", "银行", "京东", "淘宝", "外卖", "打车"),
    ),
]

# 排除“免运费/试用/无某物”等不代表免费白嫖的 free 词组
NON_FREEBIE_FREE_PATTERN = re.compile(
    r"(?i)(?:\bfree\s+(?:s\s*&\s*h|shipping|delivery|pickup|returns?|trial)\b|"
    r"\b(?:tax|hands|sugar|ad|gluten|caffeine)-free\b)"
)

# 门槛标签关键词配置
TAG_RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "需绑卡记得取消",
        ("credit card", "free trial", "trial", "auto-renew"),
        ("绑卡", "信用卡", "自动续费", "自动续订"),
    ),
    (
        "免费白嫖",
        ("free", "giveaway", "0.00"),
        ("免费", "白嫖", "无门槛", "限免", "零元"),
    ),
    (
        "限量",
        ("limited", "while supplies last"),
        ("限量", "手慢无", "先到先得"),
    ),
    (
        "仅新用户",
        ("new user", "new users", "first-time"),
        ("新用户", "新号", "首月"),
    ),
    (
        "黑五特惠",
        ("black friday", "cyber monday"),
        ("黑五",),
    ),
]


def _compile_word_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    escaped = "|".join(re.escape(w) for w in words)
    return re.compile(rf"(?i)\b(?:{escaped})\b")


CATEGORY_ASCII_PATTERNS = {
    cat: _compile_word_pattern(ascii_words)
    for cat, ascii_words, _ in CATEGORY_RULES
}
TAG_ASCII_PATTERNS = {
    tag: _compile_word_pattern(ascii_words)
    for tag, ascii_words, _ in TAG_RULES
}


def fetch_text(url: str, timeout: int = HTTP_TIMEOUT_SEC) -> str:
    """发起 HTTP GET 请求并返回 UTF-8 文本。"""
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = HTTP_TIMEOUT_SEC) -> Any:
    """抓取并解析 JSON 数据。"""
    return json.loads(fetch_text(url, timeout=timeout))


def clean_html(raw: str | None) -> str:
    """去除 HTML 标签并解码实体，规整空白字符。"""
    if not raw:
        return ""
    text = html.unescape(str(raw))
    text = SCRIPT_STYLE_PATTERN.sub(" ", text)
    text = BLOCK_BREAK_PATTERN.sub(" ", text)
    text = TAG_STRIP_PATTERN.sub(" ", text)
    text = html.unescape(text)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def truncate_summary(text: str, limit: int = 160) -> str:
    """裁剪摘要至指定长度内。"""
    cleaned = text.strip()
    if not cleaned:
        return "点击直达原帖查看具体领取步骤。"
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def parse_datetime(value: Any) -> datetime | None:
    """将时间戳、ISO-8601、常见日期或 RFC2822 字符串转为 UTC aware datetime。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    raw = str(value).strip()
    if not raw or raw.upper() in {"N/A", "NA", "NULL", "NONE"}:
        return None

    # 尝试 ISO-8601
    iso_candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    # 尝试常见无时区格式
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # 尝试 RSS RFC 2822
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def to_iso_utc(dt: datetime | None) -> str | None:
    """格式化为标准 ISO-8601 UTC 字符串。"""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _match_category(text: str) -> str | None:
    """在给定文本中按优先级匹配分类规则。"""
    for cat, _, zh_words in CATEGORY_RULES:
        if CATEGORY_ASCII_PATTERNS[cat].search(text) or any(zw in text for zw in zh_words):
            return cat
    return None


def classify_deal(title: str, summary: str, source_id: str) -> str:
    """优先依据标题分类，其次结合摘要与平台属性兜底。"""
    by_title = _match_category(title)
    if by_title is not None:
        return by_title

    by_combined = _match_category(f"{title} {summary}")
    if by_combined is not None:
        return by_combined

    if source_id in {"gamerpower", "appinn"}:
        return "软件与云服务"
    if source_id == "slickdeals":
        return "黑五与促销"
    return "生活与工具"


def extract_coupon_code(text: str) -> str | None:
    """保守提取明确的优惠码/兑换码，避免误匹配常规英文单词。"""
    for match in COUPON_PATTERN.finditer(text):
        code = match.group(1).strip("-")
        if len(code) < 4 or code in COUPON_STOPWORDS:
            continue
        if code.isdigit() and len(code) == 4 and code.startswith(("19", "20")):
            continue
        if not any(ch.isalnum() for ch in code):
            continue
        return code
    return None


def extract_tags(text: str, source_id: str, worth: str | None) -> list[str]:
    """提取门槛与福利标签。"""
    tags: list[str] = []
    # 剥离免运费/试用等干扰词后再判断“免费白嫖”
    freebie_text = NON_FREEBIE_FREE_PATTERN.sub(" ", text)
    for tag, _, zh_words in TAG_RULES:
        target = freebie_text if tag == "免费白嫖" else text
        if TAG_ASCII_PATTERNS[tag].search(target) or any(zw in target for zw in zh_words):
            tags.append(tag)

    if source_id in {"v2ex_free", "gamerpower"} and "免费白嫖" not in tags:
        tags.append("免费白嫖")
    elif worth and ("免费" in worth or worth.strip().lower() == "free") and "免费白嫖" not in tags:
        tags.append("免费白嫖")

    return tags


def normalize_url_key(url: str) -> str:
    """规范化 URL 用于跨来源去重。"""
    parsed = urllib.parse.urlsplit(url.strip())
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")
    query_pairs = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_QUERY_KEYS
    ]
    clean_query = urllib.parse.urlencode(sorted(query_pairs))
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, path, clean_query, ""))


def make_deal_id(source_id: str, raw_id: Any, url: str) -> str:
    """生成稳定短 ID。"""
    if raw_id is not None and str(raw_id).strip():
        safe_id = re.sub(r"[^A-Za-z0-9_\-]", "", str(raw_id).strip())
        if safe_id:
            return f"{source_id}-{safe_id[:24]}"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{source_id}-{digest}"


def build_deal(
    *,
    deal_id: str,
    title: str,
    summary_raw: str,
    url: str,
    source_id: str,
    source_name: str,
    published_dt: datetime | None,
    expires_dt: datetime | None,
    now_utc: datetime,
    worth: str | None = None,
    coupon_code: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    pinned: bool = False,
) -> dict[str, Any]:
    """构造统一规范的羊毛条目对象。"""
    clean_title = clean_html(title) or "未命名优惠"
    clean_desc = clean_html(summary_raw)
    summary = truncate_summary(clean_desc)
    combined_text = f"{clean_title} {clean_desc}"

    resolved_category = category or classify_deal(clean_title, clean_desc, source_id)
    resolved_coupon = coupon_code if coupon_code is not None else extract_coupon_code(combined_text)
    resolved_tags = list(dict.fromkeys(tags if tags is not None else extract_tags(combined_text, source_id, worth)))

    is_expired = expires_dt is not None and expires_dt <= now_utc
    status = "expired" if is_expired else "active"

    return {
        "id": deal_id,
        "title": clean_title,
        "category": resolved_category,
        "summary": summary,
        "couponCode": resolved_coupon,
        "url": url.strip(),
        "source": source_name,
        "tags": resolved_tags,
        "worth": worth.strip() if isinstance(worth, str) and worth.strip() else None,
        "status": status,
        "pinned": bool(pinned),
        "publishedAt": to_iso_utc(published_dt or now_utc),
        "expiresAt": to_iso_utc(expires_dt),
    }


def _rss_child_text(item: ET.Element, *candidates: str) -> str:
    """兼容命名空间读取 RSS item 子节点文本。"""
    for name in candidates:
        found = item.findtext(name)
        if found:
            return found
    for child in item:
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in candidates and child.text:
            return child.text
    return ""


def _fetch_v2ex_node(source_id: str, source_name: str, node_name: str, limit: int, now_utc: datetime) -> list[dict[str, Any]]:
    url = f"https://www.v2ex.com/api/topics/show.json?node_name={node_name}"
    items = fetch_json(url)
    results: list[dict[str, Any]] = []
    for item in items[:limit]:
        topic_url = item.get("url") or f"https://www.v2ex.com/t/{item.get('id')}"
        content = item.get("content") or item.get("content_rendered") or ""
        replies = item.get("replies")
        summary_src = content if content.strip() else f"V2EX /{node_name} 讨论帖（当前回复数：{replies or 0}）"
        results.append(
            build_deal(
                deal_id=make_deal_id(source_id, item.get("id"), topic_url),
                title=item.get("title", ""),
                summary_raw=summary_src,
                url=topic_url,
                source_id=source_id,
                source_name=source_name,
                published_dt=parse_datetime(item.get("created")),
                expires_dt=None,
                now_utc=now_utc,
                worth="免费" if node_name == "free" else None,
            )
        )
    return results


def fetch_v2ex_deals(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 V2EX 优惠信息节点最新 15 条。"""
    return _fetch_v2ex_node("v2ex_deals", "V2EX 优惠信息", "deals", 15, now_utc)


def fetch_v2ex_free(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 V2EX 免费赠送节点最新 10 条。"""
    return _fetch_v2ex_node("v2ex_free", "V2EX 免费赠送", "free", 10, now_utc)


def fetch_gamerpower(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 GamerPower 限免赠送最新 12 条。"""
    items = fetch_json("https://www.gamerpower.com/api/giveaways?sort-by=date")
    results: list[dict[str, Any]] = []
    for item in items[:12]:
        target_url = item.get("open_giveaway_url") or item.get("gamerpower_url") or ""
        if not target_url:
            continue
        raw_worth = item.get("worth")
        worth = None if not raw_worth or str(raw_worth).upper() == "N/A" else str(raw_worth)
        platforms = item.get("platforms") or ""
        g_type = item.get("type") or ""
        desc = item.get("description") or item.get("instructions") or ""
        prefix = f"[{platforms} / {g_type}] " if platforms or g_type else ""
        results.append(
            build_deal(
                deal_id=make_deal_id("gamerpower", item.get("id"), target_url),
                title=item.get("title", ""),
                summary_raw=f"{prefix}{desc}",
                url=target_url,
                source_id="gamerpower",
                source_name="GamerPower 限免",
                published_dt=parse_datetime(item.get("published_date")),
                expires_dt=parse_datetime(item.get("end_date")),
                now_utc=now_utc,
                worth=worth or "免费",
            )
        )
    return results


def _fetch_rss(source_id: str, source_name: str, feed_url: str, limit: int, now_utc: datetime) -> list[dict[str, Any]]:
    xml_text = fetch_text(feed_url)
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")
    results: list[dict[str, Any]] = []
    for item in items[:limit]:
        title = _rss_child_text(item, "title")
        link = _rss_child_text(item, "link", "guid")
        if not link:
            continue
        desc = _rss_child_text(item, "description", "encoded")
        pub_raw = _rss_child_text(item, "pubDate", "published", "updated")
        guid = _rss_child_text(item, "guid")
        results.append(
            build_deal(
                deal_id=make_deal_id(source_id, guid or None, link),
                title=title,
                summary_raw=desc,
                url=link,
                source_id=source_id,
                source_name=source_name,
                published_dt=parse_datetime(pub_raw),
                expires_dt=None,
                now_utc=now_utc,
            )
        )
    return results


def fetch_slickdeals(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 Slickdeals 首页精选最新 12 条。"""
    return _fetch_rss(
        "slickdeals",
        "Slickdeals 精选",
        "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
        12,
        now_utc,
    )


def fetch_appinn(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取小众软件最新 8 条。"""
    return _fetch_rss("appinn", "小众软件", "https://www.appinn.com/feed/", 8, now_utc)


def fetch_hn_deals(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 Hacker News 近期免费额度与促销讨论（合并检索避免 Algolia 字面 OR 匹配为空）。"""
    queries = [
        "https://hn.algolia.com/api/v1/search_by_date?query=black+friday&tags=story&hitsPerPage=6",
        "https://hn.algolia.com/api/v1/search_by_date?query=free+credits&tags=story&hitsPerPage=6",
        "https://hn.algolia.com/api/v1/search_by_date?query=giveaway&tags=story&hitsPerPage=6",
    ]
    seen_ids: set[str] = set()
    merged_hits: list[dict[str, Any]] = []
    for query_url in queries:
        data = fetch_json(query_url)
        for hit in data.get("hits", []):
            oid = str(hit.get("objectID") or "")
            if oid and oid not in seen_ids:
                seen_ids.add(oid)
                merged_hits.append(hit)

    # 按时间倒序截取前 10 条
    merged_hits.sort(
        key=lambda h: (parse_datetime(h.get("created_at")) or now_utc).timestamp(),
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for hit in merged_hits[:10]:
        oid = str(hit.get("objectID") or "")
        target_url = (hit.get("url") or "").strip() or f"https://news.ycombinator.com/item?id={oid}"
        points = hit.get("points") or 0
        comments = hit.get("num_comments") or 0
        summary_raw = f"Hacker News 讨论（热度 {points} 赞 / {comments} 评论）：{hit.get('title', '')}"
        results.append(
            build_deal(
                deal_id=make_deal_id("hn_deals", oid, target_url),
                title=hit.get("title", ""),
                summary_raw=summary_raw,
                url=target_url,
                source_id="hn_deals",
                source_name="Hacker News 福利",
                published_dt=parse_datetime(hit.get("created_at")),
                expires_dt=None,
                now_utc=now_utc,
            )
        )
    return results


SOURCE_FETCHERS: list[tuple[str, str, Callable[[datetime], list[dict[str, Any]]]]] = [
    ("v2ex_deals", "V2EX 优惠信息", fetch_v2ex_deals),
    ("v2ex_free", "V2EX 免费赠送", fetch_v2ex_free),
    ("gamerpower", "GamerPower 限免", fetch_gamerpower),
    ("slickdeals", "Slickdeals 精选", fetch_slickdeals),
    ("appinn", "小众软件", fetch_appinn),
    ("hn_deals", "Hacker News 福利", fetch_hn_deals),
]


def load_manual_deals(now_utc: datetime) -> list[dict[str, Any]]:
    """读取并规范化人工维护的置顶精选列表，永不覆盖原文件。"""
    if not MANUAL_DEALS_PATH.exists():
        return []
    raw_items = json.loads(MANUAL_DEALS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_items, list):
        return []

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict) or not item.get("url"):
            continue
        published_dt = parse_datetime(item.get("publishedAt"))
        expires_dt = parse_datetime(item.get("expiresAt"))
        normalized.append(
            build_deal(
                deal_id=str(item.get("id") or make_deal_id("manual", idx + 1, str(item["url"]))),
                title=str(item.get("title") or "人工精选优惠"),
                summary_raw=str(item.get("summary") or ""),
                url=str(item["url"]),
                source_id="manual",
                source_name=str(item.get("source") or "人工精选置顶"),
                published_dt=published_dt,
                expires_dt=expires_dt,
                now_utc=now_utc,
                worth=item.get("worth"),
                coupon_code=item.get("couponCode"),
                category=item.get("category"),
                tags=item.get("tags"),
                pinned=bool(item.get("pinned", True)),
            )
        )
    return normalized


def main() -> int:
    """执行全量抓取、清洗、去重并写入 data/deals.json。"""
    now_utc = datetime.now(timezone.utc)
    sources_status: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = load_manual_deals(now_utc)

    for source_id, source_name, fetcher in SOURCE_FETCHERS:
        try:
            items = fetcher(now_utc)
            collected.extend(items)
            sources_status.append(
                {
                    "id": source_id,
                    "name": source_name,
                    "ok": True,
                    "count": len(items),
                    "error": None,
                }
            )
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

    # 按规范化 URL 去重，置顶与人工条目优先保留
    deduped: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for deal in collected:
        key = normalize_url_key(deal["url"])
        if key in seen_urls:
            continue
        seen_urls.add(key)
        deduped.append(deal)

    # 排序：置顶优先 -> 有效优先 -> 发布时间倒序
    deduped.sort(
        key=lambda d: (
            0 if d["pinned"] else 1,
            0 if d["status"] == "active" else 1,
            -(parse_datetime(d["publishedAt"]) or now_utc).timestamp(),
        )
    )

    payload = {
        "schemaVersion": "1.0",
        "updatedAt": to_iso_utc(now_utc),
        "total": len(deduped),
        "sources": sources_status,
        "deals": deduped,
    }

    OUTPUT_DEALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DEALS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    ok_count = sum(1 for s in sources_status if s["ok"])
    print(f"已更新 {OUTPUT_DEALS_PATH}：共 {len(deduped)} 条，成功数据源 {ok_count}/{len(SOURCE_FETCHERS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
