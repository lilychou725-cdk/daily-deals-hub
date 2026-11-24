#!/usr/bin/env python3
"""每日羊毛新闻聚合抓取与清洗脚本（高纯度 AI/黑五/云服务/羊毛版，仅依赖 Python 3 标准库）。"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

# 项目路径定义
ROOT_DIR = Path(__file__).resolve().parent.parent
MANUAL_DEALS_PATH = ROOT_DIR / "data" / "manual_deals.json"
OUTPUT_DEALS_PATH = ROOT_DIR / "data" / "deals.json"

AIHOT_FREE_TOKENS_URL = "https://aihot.news/free-tokens.md"
BF_README_URL = "https://raw.githubusercontent.com/trungdq88/Awesome-Black-Friday-Cyber-Monday/master/README.md"
NODESEEK_RSS_URL = "https://rss.nodeseek.com/"

TZ_CN = timezone(timedelta(hours=8))
HTTP_TIMEOUT_SEC = 15
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, application/xml, text/xml, text/markdown, text/plain, */*;q=0.8",
}

# 单次运行内复用的远端文本缓存（避免重复拉取 Awesome Black Friday README）
_FETCH_CACHE: dict[str, str] = {}

# 过滤非优惠码的大写常见词与营销词
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
    "OFF",
    "PRO",
    "MAC",
    "MACS",
    "USD",
    "DEAL",
    "DEALS",
    "SALE",
    "SAVE",
    "LIFETIME",
    "ANNUAL",
    "YEARLY",
    "MONTHLY",
    "BLACK",
    "FRIDAY",
    "CYBER",
    "MONDAY",
    "NEW",
    "USERS",
    "ONLY",
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
    r"\s*(?i:is)?\s*[:：#是为]?\s*[*'\"`「【\[]?"
    r"([A-Z0-9][A-Z0-9\-]{3,23})(?![A-Za-z0-9\-])"
)
BOLD_COUPON_PATTERN = re.compile(r"\*\*([A-Z0-9][A-Z0-9\-]{3,23})\*\*")
BF_WORTH_PATTERN = re.compile(
    r"(?i)(?:up\s+to\s+)?\d+%\s*OFF(?:\s+Lifetime)?|Lifetime\s+deal"
)
MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
STRIKETHROUGH_PATTERN = re.compile(r"~~[^~]+~~\s*")

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
            "glm",
            "kimi",
            "qwen",
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
            "macos",
            "windows",
            "ios",
        ),
        ("域名", "软件", "云服务", "服务器", "激活码", "限免", "正版", "会员"),
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

# 门槛标签关键词配置
TAG_RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "需绑卡记得取消",
        ("credit card", "free trial", "trial", "auto-renew"),
        ("绑卡", "信用卡", "自动续费", "自动续订"),
    ),
    (
        "免绑卡",
        ("no credit card",),
        ("免绑卡", "无需绑卡"),
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
        ("black friday", "cyber monday", "bfcm"),
        ("黑五",),
    ),
]

# 排除“免运费/试用/无某物”等不代表免费白嫖的 free 词组
NON_FREEBIE_FREE_PATTERN = re.compile(
    r"(?i)(?:\bfree\s+(?:s\s*&\s*h|shipping|delivery|pickup|returns?|trial)\b|"
    r"\b(?:tax|hands|sugar|ad|gluten|caffeine)-free\b)"
)

# NodeSeek 去水过滤词
NODESEEK_BLACKLIST = (
    "[出]",
    "【出】",
    "[收]",
    "【收】",
    "想收",
    "收个",
    "收台",
    "出个",
    "出两",
    "低价出",
    "溢价出",
    "【求助】",
    "求助",
    "求推荐",
    "怎么买",
    "怎么办",
    "请问",
    "收不到",
)
NODESEEK_WHITELIST_ZH = (
    "免费",
    "白嫖",
    "羊毛",
    "黑五",
    "抽奖",
    "优惠码",
    "折扣",
    "额度",
    "免费鸡",
    "限免",
    "福利",
    "体验月",
    "赠金",
    "会员",
)
NODESEEK_WHITELIST_ASCII = re.compile(
    r"(?i)\b(?:black\s+friday|coupon|promo|credit|credits|off|free|giveaway)\b"
)

V2EX_QUESTION_PREFIXES = ("请问", "求助", "求问")


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


def fetch_text(url: str, timeout: int = HTTP_TIMEOUT_SEC, *, use_cache: bool = False) -> str:
    """发起 HTTP GET 请求并返回 UTF-8 文本，可选在单次执行内缓存。"""
    if use_cache and url in _FETCH_CACHE:
        return _FETCH_CACHE[url]
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    if use_cache:
        _FETCH_CACHE[url] = text
    return text


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


def clean_markdown(raw: str | None) -> str:
    """将常见 Markdown 标记规整为干净纯文本。"""
    if not raw:
        return ""
    text = clean_html(raw)
    text = STRIKETHROUGH_PATTERN.sub("", text)
    text = MD_LINK_PATTERN.sub(r"\1", text)
    text = re.sub(r"[*_`]+", "", text)
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

    iso_candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_cn_datetime(raw: str | None) -> datetime | None:
    """从包含中文描述的时间文本提取北京时间并转为 UTC aware datetime。"""
    if not raw:
        return None
    match = re.search(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2})(?::(\d{2}))?)?", raw)
    if not match:
        return None
    date_part, hm_part, sec_part = match.groups()
    try:
        if hm_part:
            sec = sec_part or "00"
            dt = datetime.strptime(f"{date_part} {hm_part}:{sec}", "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(date_part, "%Y-%m-%d")
        return dt.replace(tzinfo=TZ_CN).astimezone(timezone.utc)
    except ValueError:
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

    if source_id in {"bf_dev_tools", "nodeseek_deals"}:
        return "软件与云服务"
    return "生活与工具"


def _is_valid_coupon(code: str) -> bool:
    clean = code.strip("-")
    if len(clean) < 4 or clean in COUPON_STOPWORDS:
        return False
    if clean.isdigit() and len(clean) == 4 and clean.startswith(("19", "20")):
        return False
    return any(ch.isalnum() for ch in clean)


def extract_coupon_code(text: str, *, allow_bold_fallback: bool = False) -> str | None:
    """保守提取明确的优惠码/兑换码，避免误匹配常规英文单词。"""
    for match in COUPON_PATTERN.finditer(text):
        code = match.group(1).strip("-")
        if _is_valid_coupon(code):
            return code

    if allow_bold_fallback and "no code" not in text.lower():
        for match in BOLD_COUPON_PATTERN.finditer(text):
            code = match.group(1).strip("-")
            if _is_valid_coupon(code):
                return code
    return None


def extract_tags(text: str, source_id: str, worth: str | None) -> list[str]:
    """提取门槛与福利标签。"""
    tags: list[str] = []
    freebie_text = NON_FREEBIE_FREE_PATTERN.sub(" ", text)
    for tag, _, zh_words in TAG_RULES:
        target = freebie_text if tag == "免费白嫖" else text
        if TAG_ASCII_PATTERNS[tag].search(target) or any(zw in target for zw in zh_words):
            tags.append(tag)

    if source_id in {"v2ex_free", "aihot_free_tokens"} and "免费白嫖" not in tags:
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
    clean_title = clean_markdown(title) or "未命名优惠"
    clean_desc = clean_markdown(summary_raw)
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


def _extract_aihot_worth(raw: str) -> str | None:
    """精简 aihot 的『能领多少』字段（去掉过长括号说明，<=36字）。"""
    if not raw:
        return None
    stripped = re.sub(r"[（(][^）)]*[）)]", "", raw).strip(" ，,；;·")
    candidate = stripped if stripped else raw.strip()
    if len(candidate) > 36:
        candidate = candidate[:33].rstrip() + "..."
    return candidate or None


def _extract_aihot_url(raw: str) -> str:
    """从『去领』字段提取 URL，异常时回退到聚合页。"""
    if raw:
        md_match = MD_LINK_PATTERN.search(raw)
        if md_match:
            return md_match.group(2).strip()
        url_match = re.search(r"https?://[^\s)>]+", raw)
        if url_match:
            return url_match.group(0).strip()
    return "https://aihot.news/free-tokens"


def _parse_aihot_entry(
    title: str,
    fields: dict[str, str],
    group_tag: str,
    now_utc: datetime,
) -> dict[str, Any]:
    """将单条 aihot Markdown 块规范化为 Deal。"""
    target_url = _extract_aihot_url(fields.get("去领", ""))
    worth = _extract_aihot_worth(fields.get("能领多少", ""))
    how = fields.get("怎么领", "").strip()
    usable = fields.get("能用在", "").strip()
    threshold = fields.get("门槛", "").strip()
    validity = fields.get("有效期", "").strip()

    summary_parts = []
    if how:
        summary_parts.append(how)
    if usable:
        summary_parts.append(f"适用：{usable}")
    elif validity:
        summary_parts.append(f"有效期：{validity}")

    published_dt = parse_cn_datetime(fields.get("核实")) or now_utc
    expires_dt = parse_cn_datetime(fields.get("截止"))

    tag_seed = f"{title} {threshold} {how}"
    tags = [group_tag, "免费白嫖"] + extract_tags(tag_seed, "aihot_free_tokens", worth)

    return build_deal(
        deal_id=make_deal_id("aihot", None, f"{target_url}#{title}"),
        title=title,
        summary_raw=" ".join(summary_parts),
        url=target_url,
        source_id="aihot_free_tokens",
        source_name="AI 免费额度 (aihot)",
        published_dt=published_dt,
        expires_dt=expires_dt,
        now_utc=now_utc,
        worth=worth,
        category="AI会员与额度",
        tags=list(dict.fromkeys(tags)),
    )


def fetch_aihot_free_tokens(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取并解析 aihot.news/free-tokens.md 分组免费 AI 额度。"""
    md_text = fetch_text(AIHOT_FREE_TOKENS_URL)
    section_buckets: dict[str, list[tuple[str, dict[str, str]]]] = {
        "每日可领": [],
        "每月可领": [],
        "AI福利": [],
    }

    current_group: str | None = None
    current_title: str | None = None
    current_fields: dict[str, str] = {}

    def flush_entry() -> None:
        if current_group and current_title:
            section_buckets[current_group].append((current_title, dict(current_fields)))

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            flush_entry()
            current_title = None
            current_fields = {}
            heading = line[3:].strip()
            if "每天都能领" in heading:
                current_group = "每日可领"
            elif "每月都能领" in heading:
                current_group = "每月可领"
            elif "其他福利" in heading:
                current_group = "AI福利"
            else:
                current_group = None
            continue

        if current_group is None:
            continue

        if line.startswith("### "):
            flush_entry()
            current_title = line[4:].strip()
            current_fields = {}
            continue

        if current_title and line.startswith("- "):
            kv_match = re.match(r"^-\s*([^：:]+)[：:]\s*(.+)$", line)
            if kv_match:
                key, val = kv_match.groups()
                current_fields[key.strip()] = val.strip()

    flush_entry()

    daily_deals = [
        _parse_aihot_entry(t, f, "每日可领", now_utc)
        for t, f in section_buckets["每日可领"][:12]
    ]
    monthly_deals = [
        _parse_aihot_entry(t, f, "每月可领", now_utc)
        for t, f in section_buckets["每月可领"][:10]
    ]
    other_deals = [
        _parse_aihot_entry(t, f, "AI福利", now_utc)
        for t, f in section_buckets["AI福利"]
    ]
    # 其他福利按核实时间倒序取最新 13 条
    other_deals.sort(
        key=lambda d: (parse_datetime(d["publishedAt"]) or now_utc).timestamp(),
        reverse=True,
    )

    return daily_deals + monthly_deals + other_deals[:13]


def _parse_bf_sections(
    section_keywords: tuple[str, ...],
    *,
    source_id: str,
    source_name: str,
    category: str,
    limit: int,
    prioritize_star: bool,
    now_utc: datetime,
) -> list[dict[str, Any]]:
    """解析 Awesome Black Friday / Cyber Monday 2026 表格指定分节。"""
    md_text = fetch_text(BF_README_URL, use_cache=True)
    rows: list[tuple[bool, str, str, str, str]] = []
    in_section = False

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            in_section = any(kw in line for kw in section_keywords)
            continue
        if not in_section or not line.startswith("|"):
            continue

        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 4:
            continue
        icon_col = cols[0]
        name_col = cols[1]
        desc_col = cols[2]
        terms_col = " | ".join(cols[3:])

        if name_col.lower() == "name" or set(name_col) <= set("-: "):
            continue
        link_match = MD_LINK_PATTERN.search(name_col)
        if not link_match:
            continue

        name, url = link_match.group(1).strip(), link_match.group(2).strip()
        is_star = "⭐" in icon_col
        rows.append((is_star, name, url, desc_col, terms_col))

    if prioritize_star:
        rows.sort(key=lambda r: 0 if r[0] else 1)

    results: list[dict[str, Any]] = []
    for _, name, url, desc_col, terms_col in rows[:limit]:
        worth_match = BF_WORTH_PATTERN.search(terms_col)
        worth = worth_match.group(0).strip() if worth_match else None
        coupon = extract_coupon_code(terms_col, allow_bold_fallback=True)

        clean_desc = clean_markdown(desc_col)
        clean_terms = clean_markdown(terms_col)
        summary_raw = f"{clean_terms}。{clean_desc}" if clean_terms else clean_desc
        title = f"{name} — {worth}" if worth else name

        tags = ["黑五特惠"] + extract_tags(f"{title} {clean_terms}", source_id, worth)
        results.append(
            build_deal(
                deal_id=make_deal_id(source_id, None, url),
                title=title,
                summary_raw=summary_raw,
                url=url,
                source_id=source_id,
                source_name=source_name,
                published_dt=now_utc,
                expires_dt=None,
                now_utc=now_utc,
                worth=worth,
                coupon_code=coupon,
                category=category,
                tags=list(dict.fromkeys(tags)),
            )
        )
    return results


def fetch_bf_ai_tools(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 2026 黑五 AI Tools 专区（前 15 条）。"""
    return _parse_bf_sections(
        ("AI Tools",),
        source_id="bf_ai_tools",
        source_name="黑五 AI 工具 2026",
        category="AI会员与额度",
        limit=15,
        prioritize_star=False,
        now_utc=now_utc,
    )


def fetch_bf_dev_tools(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 2026 黑五 Developer Tools & Productivity 专区（优先 ⭐ 条目，前 12 条）。"""
    return _parse_bf_sections(
        ("Developer Tools", "Productivity"),
        source_id="bf_dev_tools",
        source_name="黑五开发与效率 2026",
        category="软件与云服务",
        limit=12,
        prioritize_star=True,
        now_utc=now_utc,
    )


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


def fetch_nodeseek_deals(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 NodeSeek RSS 并用严格黑白名单过滤二手交易与水贴。"""
    xml_text = fetch_text(NODESEEK_RSS_URL)
    root = ET.fromstring(xml_text)
    results: list[dict[str, Any]] = []

    for item in root.findall("./channel/item"):
        title = clean_html(_rss_child_text(item, "title"))
        link = _rss_child_text(item, "link", "guid").strip()
        if not title or not link:
            continue

        # 排除明显二手交易与纯求助贴
        if any(bad in title for bad in NODESEEK_BLACKLIST):
            continue

        desc = clean_html(_rss_child_text(item, "description", "encoded"))
        combined = f"{title} {desc}"
        if not (
            any(good in combined for good in NODESEEK_WHITELIST_ZH)
            or NODESEEK_WHITELIST_ASCII.search(combined)
        ):
            continue

        pub_raw = _rss_child_text(item, "pubDate", "published", "updated")
        guid = _rss_child_text(item, "guid")
        results.append(
            build_deal(
                deal_id=make_deal_id("nodeseek", guid or None, link),
                title=title,
                summary_raw=desc or title,
                url=link,
                source_id="nodeseek_deals",
                source_name="NodeSeek 精选福利",
                published_dt=parse_datetime(pub_raw),
                expires_dt=None,
                now_utc=now_utc,
            )
        )
        if len(results) >= 10:
            break

    return results


def _fetch_v2ex_node(
    source_id: str,
    source_name: str,
    node_name: str,
    limit: int,
    now_utc: datetime,
) -> list[dict[str, Any]]:
    url = f"https://www.v2ex.com/api/topics/show.json?node_name={node_name}"
    items = fetch_json(url)
    results: list[dict[str, Any]] = []
    for item in items:
        title = clean_html(item.get("title", ""))
        if not title or title.startswith(V2EX_QUESTION_PREFIXES):
            continue

        topic_url = item.get("url") or f"https://www.v2ex.com/t/{item.get('id')}"
        content = item.get("content") or item.get("content_rendered") or ""
        replies = item.get("replies")
        summary_src = content if content.strip() else f"V2EX /{node_name} 讨论帖（当前回复数：{replies or 0}）"
        results.append(
            build_deal(
                deal_id=make_deal_id(source_id, item.get("id"), topic_url),
                title=title,
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
        if len(results) >= limit:
            break
    return results


def fetch_v2ex_deals(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 V2EX 优惠信息节点（过滤纯提问水贴，最多 10 条）。"""
    return _fetch_v2ex_node("v2ex_deals", "V2EX 优惠信息", "deals", 10, now_utc)


def fetch_v2ex_free(now_utc: datetime) -> list[dict[str, Any]]:
    """抓取 V2EX 免费赠送节点（过滤纯提问水贴，最多 10 条）。"""
    return _fetch_v2ex_node("v2ex_free", "V2EX 免费赠送", "free", 10, now_utc)


SOURCE_FETCHERS: list[tuple[str, str, Callable[[datetime], list[dict[str, Any]]]]] = [
    ("aihot_free_tokens", "AI 免费额度 (aihot)", fetch_aihot_free_tokens),
    ("bf_ai_tools", "黑五 AI 工具 2026", fetch_bf_ai_tools),
    ("bf_dev_tools", "黑五开发与效率 2026", fetch_bf_dev_tools),
    ("nodeseek_deals", "NodeSeek 精选福利", fetch_nodeseek_deals),
    ("v2ex_deals", "V2EX 优惠信息", fetch_v2ex_deals),
    ("v2ex_free", "V2EX 免费赠送", fetch_v2ex_free),
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
    _FETCH_CACHE.clear()
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
