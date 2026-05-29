import hashlib
import json
import math
import re
import asyncio
from datetime import datetime
from time import perf_counter
from typing import Any
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException

from backend.services.model_client import build_messages, call_task_model
from backend.services.storage import read_config


DEFAULT_THUMBNAILS = [
    "linear-gradient(135deg, #e9f2ff, #fff3d4)",
    "linear-gradient(135deg, #e8fff6, #f5ead7)",
    "linear-gradient(135deg, #f2ecff, #e7f7f8)",
    "linear-gradient(135deg, #fff2e6, #e9f3ff)",
]

# ── 商品搜索域权重表 ───────────────────────────────────────────────────────────
# 思路来自 newsfilter 的 DOMAIN_AUTHORITY_MAP，但针对商品/产品博客参考搜索重新设计：
# newsfilter 偏向新闻媒体和政府机构；这里偏向产品评测平台、电商、科技媒体。
# 同一域名下的子域也通过后缀匹配继承权重（如 zhuanlan.zhihu.com → zhihu.com）。
PRODUCT_DOMAIN_AUTHORITY: dict[str, float] = {
    # CN 产品评测 / 数码媒体 —— 对商品博客参考价值最高
    "zhihu.com": 0.72,          # 知乎：深度用户评价、行业分析
    "zhuanlan.zhihu.com": 0.72,
    "sspai.com": 0.70,          # 少数派：高质量数码/生活好物评测
    "smzdm.com": 0.68,          # 什么值得买：真实消费者评测
    "36kr.com": 0.65,           # 36氪：科技/消费品深度报道
    "ithome.com": 0.63,         # IT之家：数码资讯
    "ifanr.com": 0.62,          # 爱范儿：消费电子评测
    "pconline.com.cn": 0.60,    # 太平洋：产品参数/评测
    "zol.com.cn": 0.60,         # 中关村：电子产品测评
    "dgtle.com": 0.57,          # 数字尾巴：科技生活方式
    "bilibili.com": 0.55,       # B站：开箱/评测视频（有文字稿）
    # CN 电商平台 —— 产品详情页有价值，但购物车/结算页无用
    "jd.com": 0.55,
    "tmall.com": 0.52,
    "taobao.com": 0.44,
    # CN 财经/商业媒体 —— 适合品牌、市场、行业背景
    "yicai.com": 0.60,          # 第一财经
    "caixin.com": 0.60,         # 财新
    "21jingji.com": 0.57,       # 21世纪经济报道
    "jiemian.com": 0.55,        # 界面新闻
    "thepaper.cn": 0.54,        # 澎湃新闻
    "nbd.com.cn": 0.52,         # 每日经济新闻
    "stcn.com": 0.50,           # 证券时报网
    # CN 综合门户 —— 聚合内容，权重较低
    "ifeng.com": 0.44,
    "163.com": 0.40,
    "sina.com.cn": 0.40,
    "sohu.com": 0.38,
    "qq.com": 0.38,
    # EN 产品评测媒体
    "rtings.com": 0.74,         # 客观测量数据，极高可信度
    "cnet.com": 0.72,
    "techradar.com": 0.71,
    "pcmag.com": 0.70,
    "theverge.com": 0.70,
    "wired.com": 0.68,
    "tomsguide.com": 0.66,
    "engadget.com": 0.65,
    "tomshardware.com": 0.65,
    "notebookcheck.net": 0.63,
    "gsmarena.com": 0.62,
    # EN 电商
    "amazon.com": 0.55,
    # 百科（产品背景有参考价值，但非权威规格来源）
    "wikipedia.org": 0.42,
    "baike.baidu.com": 0.40,
    # 默认：未收录域名赋予中等权重，不惩罚未知来源
    "default": 0.25,
}

# 时间衰减系数 —— 借鉴 newsfilter 的 exp(-λ×天数) 公式，但λ更小：
# 商品信息不像新闻那样快速过时，半衰期约 17 天（vs newsfilter 的 7 天）
PRODUCT_TIME_DECAY_LAMBDA = 0.04

# 低价值 URL 路径模式：购物车/结算/登录页面没有有用的商品内容
_LOW_QUALITY_URL_RE = re.compile(
    r"/(?:cart|checkout|payment|login|register|signup|sign[\-_]up"
    r"|account|orders?|basket|wishlist|404|error|sitemap"
    r"|privacy[\-_]policy|terms[\-_]of|contact[\-_]us|about[\-_]us)(?:/|$|\?)",
    re.IGNORECASE,
)


def build_blog_search_query(input_data: dict[str, Any]) -> str:
    # 主 query 只用 productName + productType，确保聚焦商品本体。
    # 不再拼接 market（如「中国」会把搜索词稀释成"产品 + 区域"双意图，引来无关结果），
    # 也不再拼接「评测/选购/推荐/指南」「review/buying guide/best」之类后缀——
    # 这些"意图前缀"由 build_search_variants 在 variants 列表里单独产出，
    # 让 SearXNG 先用宽召回的纯品类 query 去抓，再用意图变体补充。
    flat_input = flatten_requirement_input(input_data)
    parts: list[str] = []
    seen: set[str] = set()
    for key in ("productName", "productType"):
        value = compact_query(str(flat_input.get(key) or ""), max_words=6)
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        parts.append(value)
    if not parts:
        # 兜底：用户没填 product 信息时才用 keywords / brief 做拼接
        for key in ("keywords", "brief"):
            value = flat_input.get(key)
            if isinstance(value, list):
                value = " ".join(str(v) for v in value if v)
            value = compact_query(str(value or ""), max_words=8)
            if value:
                parts.append(value)
                break
    return " ".join(str(part).strip() for part in parts if str(part or "").strip())


def clean_json_text(text: str) -> str:
    cleaned = str(text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    return re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE).strip()


def parse_query_plan(text: str) -> dict[str, Any]:
    try:
        data = json.loads(clean_json_text(text))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def flatten_requirement_input(input_data: dict[str, Any]) -> dict[str, Any]:
    flat = dict(input_data or {})
    requirement = flat.get("requirement")
    if isinstance(requirement, dict):
        for key, value in requirement.items():
            if key not in flat or flat.get(key) in (None, "", [], {}):
                flat[key] = value
    return flat


def product_query_text(input_data: dict[str, Any], fallback: str) -> str:
    input_data = flatten_requirement_input(input_data)
    parts: list[str] = []
    seen: set[str] = set()
    for key in ("productName", "productType"):
        value = compact_query(str(input_data.get(key) or ""), max_words=6)
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        parts.append(value)
    value = " ".join(parts)
    return value or fallback


def search_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_]*|[\u4e00-\u9fff]{2,}", str(text or "").lower())
    tokens: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        pieces = [token]
        if re.fullmatch(r"[\u4e00-\u9fff]{4,}", token):
            pieces.extend(token[index : index + 2] for index in range(0, len(token) - 1))
            pieces.extend(token[index : index + 3] for index in range(0, len(token) - 2))
        for piece in pieces:
            if piece and piece not in seen:
                seen.add(piece)
                tokens.append(piece)
    return tokens


def is_generic_search_term(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    compacted = re.sub(r"[\s\-_]+", "", normalized)
    return normalized in GENERIC_SEARCH_TERMS or compacted in GENERIC_SEARCH_TERMS


def compact_query(value: str, max_words: int = 8) -> str:
    cleaned = re.sub(r"[\"“”'‘’]+", "", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words])
    return cleaned


def product_seed_text(value: str) -> str:
    cleaned = compact_query(value, max_words=8)
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) <= 3:
        return cleaned
    if re.search(r"[\u4e00-\u9fff]", words[0]):
        return words[0]
    return " ".join(words[:3])


def product_query_variants(input_data: dict[str, Any], query: str) -> list[str]:
    input_data = flatten_requirement_input(input_data)
    product_name = product_seed_text(str(input_data.get("productName") or ""))
    product_type = product_seed_text(str(input_data.get("productType") or ""))
    product = compact_query(product_query_text(input_data, query))
    variants = [product_name, product_type, product, compact_query(query)]
    for phrase in (product_name, product_type, product):
        tokens = [
            token
            for token in search_tokens(phrase)
            if not is_generic_search_term(token) and len(token) > 2
        ]
        if len(tokens) >= 2:
            variants.append(" ".join(tokens[-2:]))
        if len(tokens) >= 3:
            variants.append(" ".join(tokens[-3:]))
    return [item for item in variants if item]


def build_search_variants(input_data: dict[str, Any], query: str) -> list[str]:
    product = product_seed_text(product_query_text(input_data, query))
    market = str(input_data.get("market") or "").strip()
    language = str(input_data.get("language") or "").lower()
    product_variants = product_query_variants(input_data, query)
    has_ascii_product = bool(re.search(r"[A-Za-z]", product))
    if language.startswith("zh"):
        templates = [
            "{product}",
            "{product} 评测 推荐",
            "{product} 选购 指南",
            "{product} 测评 对比",
            "{product} 品牌 定制",
        ]
        if has_ascii_product:
            templates.extend([
                "{product} review",
                "best {product}",
                "{product} supplier",
                "{product} wholesale",
            ])
    else:
        templates = [
            "{product}",
            "{product} review",
            "best {product}",
            "{product} buying guide",
            "custom {product}",
        ]
        templates.extend([
            "{product} supplier",
            "{product} wholesale",
            "{product} specifications",
        ])
    variants = []
    variants.extend(product_variants)
    variants.append(compact_query(query, max_words=8))
    variants.extend(template.format(product=product) for template in templates if product)
    if market and product:
        variants.append(compact_query(f"{product} {market}", max_words=8))
        if has_ascii_product:
            variants.append(compact_query(f"{product} {market} supplier", max_words=8))
    clean: list[str] = []
    seen: set[str] = set()
    for item in variants:
        normalized = compact_query(item, max_words=8)
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            clean.append(normalized)
    return clean[:8]


def fallback_search_plan(input_data: dict[str, Any], max_results: int) -> dict[str, Any]:
    input_data = flatten_requirement_input(input_data)
    manual = str(input_data.get("manualQuery") or "").strip()
    base_query = manual or build_blog_search_query(input_data)
    variants = build_search_variants(input_data, base_query)
    core_terms = extract_core_terms(input_data, base_query)
    return {
        "primaryQuery": base_query,
        "queries": variants,
        "coreTerms": core_terms,
        "maxResults": max_results,
        "source": "fallback",
    }


def compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def protected_core_term(term: str, input_data: dict[str, Any]) -> bool:
    key = compact_key(term)
    tokens = search_tokens(term)
    product_name = compact_key(str(input_data.get("productName") or ""))
    if product_name and (key == product_name or product_name in key):
        return True
    if product_name and key in product_name and len(tokens) >= 2:
        return True
    product_seed = compact_key(product_seed_text(str(input_data.get("productType") or "")))
    return bool(product_seed and (key == product_seed or (key in product_seed and len(tokens) >= 2)))


def normalize_core_terms(raw_terms: Any, fallback_terms: list[str], input_data: dict[str, Any]) -> list[str]:
    source_terms = raw_terms if isinstance(raw_terms, list) else []
    terms: list[str] = []
    seen: set[str] = set()
    for term in [*source_terms, *fallback_terms]:
        normalized = str(term or "").strip().lower()
        protected = protected_core_term(normalized, input_data)
        if not normalized or len(normalized) < 2 or (is_generic_search_term(normalized) and not protected):
            continue
        tokens = search_tokens(normalized)
        if len(tokens) == 1 and is_generic_search_term(tokens[0]) and not protected:
            continue
        if len(tokens) > 1 and all(is_generic_search_term(token) for token in tokens) and not protected:
            continue
        key = re.sub(r"[\s\-_]+", "", normalized)
        if key in seen:
            continue
        seen.add(key)
        terms.append(normalized)
        if len(terms) >= 6:
            break
    return terms


def normalize_query_plan(plan: dict[str, Any], input_data: dict[str, Any], max_results: int) -> dict[str, Any]:
    input_data = flatten_requirement_input(input_data)
    fallback = fallback_search_plan(input_data, max_results)
    raw_queries = plan.get("queries") if isinstance(plan.get("queries"), list) else []
    queries: list[str] = []
    seen: set[str] = set()
    for item in raw_queries:
        value = compact_query(str(item or "").strip(), max_words=8)
        if not value:
            continue
        value = re.sub(r"\s+", " ", value)
        lower = value.lower()
        if lower in seen:
            continue
        seen.add(lower)
        queries.append(value)
    if not queries:
        queries = fallback["queries"]
    else:
        broad_variants = build_search_variants(input_data, fallback["primaryQuery"])
        merged: list[str] = []
        merged_seen: set[str] = set()
        first_query = queries[0]
        first_query_tokens = search_tokens(first_query)
        first_query_zh_len = len(re.sub(r"[^\u4e00-\u9fff]", "", first_query))
        ordered_values = (
            [*broad_variants[:3], first_query, *queries[1:], *broad_variants[3:]]
            if len(first_query_tokens) > 4 or first_query_zh_len >= 10
            else
            [first_query, *broad_variants[:3], *queries[1:], *broad_variants[3:]]
        )
        for value in ordered_values:
            normalized = compact_query(value, max_words=8)
            lower = normalized.lower()
            if not normalized or lower in merged_seen:
                continue
            merged_seen.add(lower)
            merged.append(normalized)
            if len(merged) >= 8:
                break
        queries = merged
    core_terms = normalize_core_terms(plan.get("coreTerms"), fallback["coreTerms"], input_data)
    primary = str(plan.get("primaryQuery") or (queries[0] if queries else fallback["primaryQuery"])).strip()
    return {
        "primaryQuery": primary or fallback["primaryQuery"],
        "queries": queries[:8],
        "coreTerms": core_terms,
        "source": plan.get("source") or "model",
        "raw": plan,
    }


def search_planner_prompt(config: dict[str, Any], language: str) -> str:
    prompts = config.get("prompts") or {}
    active = prompts.get(language) or prompts.get("zh") or {}
    fallback = (
        "你是电商搜索意图规划器。先根据用户完整需求 JSON 判断真实业务意图，再拆出适合 SearXNG 全网搜索的短查询词。\n"
        "你必须先理解：商品/服务实体、目标用户、使用场景、购买/推广/科普/对比/本地门店等意图、以及应该避免的跑偏角度。\n"
        "primaryQuery 规则：必须聚焦商品本体（productName 优先，其次 productType），不要包含 market、blog 写作角度、AI 曝光、SEO 等修饰词；"
        "若需要把意图引入，请放在 queries 数组里的「长尾 query」，不要污染 primaryQuery。\n"
        "queries 规则：每个 query 只放 1 个核心商品/服务实体 + 0-1 个关键意图或属性；不要把所有属性塞进一个 query。"
        "先给宽泛高召回词（≥2 条仅含商品实体），再给细分长尾词（含规格/使用场景/对比/采购）。"
        "如果用户是咖啡店、门店、商家或品牌推广场景，优先搜索经营、采购、菜单、设备、推广、用户场景，不要默认搜索化学原理或学术知识，除非用户明确要求。\n"
        "禁止把以下泛词作为 primaryQuery、queries、coreTerms 的「独立」成分："
        "blog、博客、guide、review、comparison、SEO、AI检索曝光、AI 检索、怎么写文章、最佳、推荐、选购、指南、评测、测评、对比；"
        "也不要把市场名（中国 / 美国 / EMEA 等地理词）作为 primaryQuery 或 coreTerms 的主语，市场可以作为长尾 query 的修饰。"
        "coreTerms 中严禁出现：① 纯材质词（不锈钢、铝合金、铝、铜、塑料、玻璃、硅胶）；"
        "② 纯属性词（大容量、便携、轻便、耐用、高品质、优质）；"
        "③ 会引起行业混淆的词，例如「个性化定制」「礼品定制」这类词属于礼品行业，不属于器具/餐饮行业，不应出现在器具或食品器皿类搜索的 coreTerms 中。"
        "coreTerms 只保留能清晰区分「商品品类或功能」的核心名词。"
        "保留明确商品名，如 Custom Milk Pitcher、Niche Zero。\n"
        "中英文按用户输入和目标市场选择。\n"
        "只返回 JSON：searchIntent, primaryQuery, queries, coreTerms, avoidAngles。"
        "primaryQuery 必须是单一短语（≤6 个词）只含商品/服务实体；queries 为 4-8 个短字符串；coreTerms 只放 3-6 个最核心实体词，不放所有属性，也不放泛词。"
        if language.startswith("zh")
        else
        "You are an ecommerce search-intent planner. First infer the real business intent from the full user JSON, then produce short SearXNG web-search queries.\n"
        "Identify the product/service entity, target audience, use case, intent type such as buying, promotion, education, comparison, local store, and angles to avoid.\n"
        "primaryQuery rule: must focus on the product entity (productName first, then productType). Do NOT include market names, blog/SEO/AI exposure modifiers, or generic intent suffixes; "
        "put intent into the queries array as long-tail entries instead.\n"
        "queries rule: each query must contain 1 core product/service entity plus at most 1 intent or attribute. Do not pack every attribute into one query. "
        "Include at least 2 broad queries containing only the product entity, then add long-tail queries with specs / use cases / comparisons / sourcing.\n"
        "If the user is a cafe, store, merchant, or brand-promotion scenario, prioritize business operation, sourcing, menu, equipment, promotion, and customer-use scenarios; do not default to chemistry or academic topics unless explicitly requested.\n"
        "Forbidden as standalone components in primaryQuery / queries / coreTerms: blog, guide, review, comparison, SEO, AI visibility, how-to-write, best, top, buying, ultimate, recommendation. "
        "Geographic terms (China, US, EMEA, ...) must NOT be the subject of primaryQuery or coreTerms; geography can only appear as a modifier in long-tail queries. "
        "coreTerms must NOT include: ① material-only terms (stainless steel, stainless, aluminum, plastic, glass, silicone, ceramic); "
        "② pure attribute terms (large, portable, durable, heavy-duty, high-quality, professional used as standalone without a product noun); "
        "③ cross-industry synonyms that would match the wrong domain — for example 'personalized' and 'personalised' belong to the gift/crafts industry and must NOT appear in coreTerms for beverage equipment, kitchenware, or cafe product searches. "
        "coreTerms must only contain nouns or noun phrases that clearly identify a product category or function."
        "Preserve explicit product names such as Custom Milk Pitcher or Niche Zero.\n"
        "Choose Chinese/English based on user input and target market.\n"
        "Return strict JSON only: searchIntent, primaryQuery, queries, coreTerms, avoidAngles. "
        "primaryQuery must be a single short phrase (<=6 words) containing only the product/service entity; queries must be 4-8 short strings; coreTerms must contain only 3-6 core entity terms, no attributes and no generic words."
    )
    return str(active.get("search_planner") or fallback)


async def build_model_search_plan(config: dict[str, Any], input_data: dict[str, Any], max_results: int) -> dict[str, Any]:
    input_data = flatten_requirement_input(input_data)
    manual = str(input_data.get("manualQuery") or "").strip()
    if manual:
        return fallback_search_plan({**input_data, "manualQuery": manual}, max_results)
    language = str(input_data.get("language") or config.get("language") or "zh").lower()
    system = search_planner_prompt(config, language)
    payload = {
        "input": input_data,
        "constraints": {
            "maxQueries": 8,
            "maxResults": max_results,
            "avoidFormatKeywords": ["blog", "博客", "guide", "review", "comparison", "SEO", "AI检索曝光", "how to write"],
        },
    }
    try:
        text = await call_task_model(config, "search_planner", build_messages(system, payload))
        plan = normalize_query_plan(parse_query_plan(text), input_data, max_results)
        plan["source"] = "model"
        return plan
    except Exception as exc:
        plan = fallback_search_plan(input_data, max_results)
        plan["source"] = "fallback"
        plan["error"] = str(exc)
        return plan


def item_id(url: str, title: str = "") -> str:
    return hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def normalize_url(url: str, base_url: str = "") -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    if value.startswith("/moseeker/") and base_url:
        return urljoin(base_url.rstrip("/") + "/", value.lstrip("/"))
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("/"):
        return urljoin(base_url.rstrip("/") + "/", value.lstrip("/")) if base_url else value
    return value


def weighted_score(item: dict[str, Any], index: int, query: str) -> float:
    title = str(item.get("title") or "").lower()
    snippet = str(item.get("snippet") or item.get("content") or "").lower()
    query_terms = [term.lower() for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_]*|[\u4e00-\u9fff]{2,}", query or "")[:12]]
    match_score = sum(1.5 for term in query_terms if term in title) + sum(0.45 for term in query_terms if term in snippet)
    authority = float(item.get("authority_weight") or item.get("authority") or 0.35)
    independent = 0.35 if item.get("is_independent", True) else 0
    model_rank = max(0, 4.5 - index * 0.28)
    richness = min(1.2, len(snippet) / 260)
    image_bonus = 0.25 if item.get("thumbnail") else 0
    repeat_penalty = float(item.get("repeat_probability") or 0) * 0.8
    return round(model_rank + match_score + authority * 2 + independent + richness + image_bonus - repeat_penalty, 4)


GENERIC_SEARCH_TERMS = {
    "ai", "search", "visibility", "blog", "guide", "review", "comparison", "ecommerce", "buying", "best",
    "china", "chinese", "united", "states", "market", "product", "products", "custom", "branded", "brand",
    "logo", "printing", "supplier", "suppliers", "wholesale", "coffee", "cafe", "shop", "store", "milk",
    "pitcher", "serverware", "drinkware", "ceramic", "commercial", "for", "with", "and", "or", "best",
    "buy", "bulk", "order", "equipment", "branding", "options", "moq", "pricing",
    # Material terms — too generic to distinguish product categories
    "stainless", "steel", "aluminum", "aluminium", "plastic", "glass", "silicone", "copper", "titanium",
    # Cross-domain synonyms — cause false industry matches (e.g., gift/apparel sites)
    "personalized", "personalised", "customized", "customised", "engraved", "monogrammed",
    # Generic attribute terms — attributes, not product identifiers
    "durable", "portable", "professional", "heavy", "duty",
    # Chinese material terms (材质)
    "不锈钢", "铝合金", "铝", "铜", "塑料", "玻璃", "硅胶", "钛",
    # Chinese attribute terms (属性/泛词)
    "大容量", "便携", "耐用", "高品质", "优质", "轻便", "专业",
    # Chinese search/intent terms
    "检索", "曝光", "中国", "指南", "评测", "测评", "对比", "博客", "电商", "选购", "商品", "推广",
    "推荐", "品牌", "定制", "哪款好", "怎么选", "采购", "渠道", "咖啡", "咖啡店", "器具", "门店",
}

LOW_VALUE_DOMAINS = {
    "google.com", "translate.google.com", "timeanddate.com", "merriam-webster.com", "dictionary.cambridge.org",
    "wikipedia.org", "manualslib.com", "manuals.plus", "sourceforge.net", "github.com", "aspell.net",
    "time.now", "time.is", "thetimenow.com", "24timezones.com", "worldtimebuddy.com", "worldometers.info",
    "usamap.net",
}


def get_domain_authority(domain: str) -> float:
    """查询商品搜索场景下的域权重。
    逻辑来自 newsfilter 的 DOMAIN_AUTHORITY_MAP 查找机制，
    参数针对产品评测/电商平台重新标定（而非新闻机构）。
    支持子域后缀继承：zhuanlan.zhihu.com → zhihu.com 的权重。
    """
    d = str(domain or "").lower().replace("www.", "").split(":")[0]
    if d in PRODUCT_DOMAIN_AUTHORITY:
        return PRODUCT_DOMAIN_AUTHORITY[d]
    for key, weight in PRODUCT_DOMAIN_AUTHORITY.items():
        if key != "default" and d.endswith("." + key):
            return weight
    return PRODUCT_DOMAIN_AUTHORITY["default"]


def freshness_score(publish_time: str) -> float:
    """时间衰减得分 exp(-λ × 天数)。
    算法来自 newsfilter 的时间衰减逻辑，λ 调整为 0.04（商品内容半衰期比新闻长）。
    日期无法解析时返回 0.0（不加分也不扣分）。
    """
    if not publish_time:
        return 0.0
    text = str(publish_time).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(text[: len(fmt)], fmt)
            delta = max(0, (datetime.now() - dt).days)
            return round(math.exp(-PRODUCT_TIME_DECAY_LAMBDA * delta), 4)
        except ValueError:
            continue
    return 0.0


def url_quality_penalty(url: str) -> float:
    """检测购物车/结算/登录等低价值页面，返回扣分值。
    这类 URL 在搜索结果中出现频率高，但对商品博客参考无实际内容价值。
    """
    return 22.0 if _LOW_QUALITY_URL_RE.search(str(url or "")) else 0.0


def split_domains(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = raw
    else:
        values = re.split(r"[,，;\n\s]+", str(raw or ""))
    clean: list[str] = []
    seen: set[str] = set()
    for value in values:
        domain = str(value or "").strip().lower().replace("www.", "")
        if not domain or domain in seen:
            continue
        seen.add(domain)
        clean.append(domain)
    return clean


def parse_customer_urls_text(raw: str) -> list[dict[str, str]]:
    urls: list[dict[str, str]] = []
    for line in str(raw or "").splitlines():
        value = line.strip()
        if not value:
            continue
        parts = [part.strip() for part in re.split(r"\s*[,\t|]\s*", value) if part.strip()]
        url = next((part for part in parts if part.startswith(("http://", "https://"))), "")
        if not url:
            match = re.search(r"https?://[^\s,|]+", value)
            url = match.group(0) if match else ""
        if not url:
            continue
        title = ""
        note = ""
        for part in parts:
            if part == url:
                continue
            if not title:
                title = part
            elif not note:
                note = part
        urls.append({"url": url, "title": title, "note": note})
    return urls


def domain_matches(domain: str, patterns: list[str] | set[str]) -> bool:
    normalized = str(domain or "").replace("www.", "").lower()
    return any(normalized == pattern or normalized.endswith("." + pattern) for pattern in patterns)


def source_tuning(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "domainWeights": settings.get("domainWeights") if isinstance(settings.get("domainWeights"), dict) else {},
        "customerSources": normalize_customer_sources(settings.get("customerSources") or []),
        "rankerEnabled": settings.get("rankerEnabled", True) is not False,
        "rankerEndpoint": str(settings.get("rankerEndpoint") or "").strip(),
        "searxngEnabled": settings.get("searxngEnabled", True) is not False,
    }


def normalize_customer_sources(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    sources: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"客户源 {index + 1}").strip()
        enabled = item.get("enabled", True) is not False
        try:
            weight = float(item.get("weight", 3))
        except Exception:
            weight = 3.0
        urls = []
        seen: set[str] = set()
        for url_item in item.get("urls") or []:
            if isinstance(url_item, dict):
                url = str(url_item.get("url") or "").strip()
                title = str(url_item.get("title") or "").strip()
                note = str(url_item.get("note") or "").strip()
            else:
                url = str(url_item or "").strip()
                title = ""
                note = ""
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            urls.append({"url": url, "title": title, "note": note})
        sources.append(
            {
                "id": str(item.get("id") or f"customer_source_{index + 1}"),
                "name": name,
                "enabled": enabled,
                "weight": weight,
                "urls": urls[:300],
            }
        )
    return sources


def customer_source_candidates(settings: dict[str, Any], tuning: dict[str, Any], core_terms: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    active_sources = [source for source in tuning.get("customerSources") or [] if source.get("enabled")]
    for source_index, source in enumerate(active_sources):
        weight = float(source.get("weight") or 0)
        for item_index, url_item in enumerate(source.get("urls") or []):
            url = str(url_item.get("url") or "").strip()
            title = str(url_item.get("title") or "").strip() or title_from_url(url)
            note = str(url_item.get("note") or "").strip()
            domain = domain_of(url)
            text = " ".join([title, note, domain, url]).lower()
            relevance = relevance_score({"title": title, "snippet": note, "domain": domain, "url": url}, core_terms)
            if core_terms and relevance < 0.08:
                continue
            candidates.append(
                {
                    "id": item_id(url, title),
                    "rank": item_index + 1,
                    "weightedRank": item_index + 1,
                    "score": round(10 + weight + relevance * 10, 4),
                    "title": title[:180],
                    "url": url,
                    "domain": domain,
                    "snippet": note[:520] or f"{source.get('name')} 客户源链接",
                    "thumbnail": "",
                    "thumbnailFallback": DEFAULT_THUMBNAILS[(source_index + item_index) % len(DEFAULT_THUMBNAILS)],
                    "reason": f"客户源：{source.get('name')}，权重 {weight:g}",
                    "publishTime": "",
                    "isIndependent": True,
                    "authorityWeight": min(1.0, max(0.1, 0.35 + weight / 20)),
                    "sourceMode": "customer_source",
                    "sourceName": source.get("name"),
                    "sourceRelevance": round(relevance, 3),
                }
            )
    return candidates, {
        "mode": "customer_source",
        "sourceCount": len(active_sources),
        "inputUrlCount": sum(len(source.get("urls") or []) for source in active_sources),
        "outputCount": len(candidates),
    }


def title_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    path = unescape(parsed.path.strip("/").replace("-", " ").replace("_", " "))
    title = path.split("/")[-1] if path else parsed.netloc
    return title.strip().title() or url


def extract_core_terms(input_data: dict[str, Any], query: str) -> list[str]:
    input_data = flatten_requirement_input(input_data)
    source = " ".join(
        str(input_data.get(key) or "").strip()
        for key in ("productType", "productName")
        if str(input_data.get(key) or "").strip()
    ) or query
    candidates = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_]*|[\u4e00-\u9fff]{2,}", source.lower())
    terms: list[str] = []
    seen: set[str] = set()
    for term in candidates:
        normalized = term.strip().lower()
        if not normalized or is_generic_search_term(normalized) or len(normalized) < 2:
            continue
        if normalized not in seen:
            seen.add(normalized)
            terms.append(normalized)
    return terms[:8]


def relevance_score(item: dict[str, Any], core_terms: list[str]) -> float:
    if not core_terms:
        return 1.0
    text = " ".join(
        str(item.get(key) or "")
        for key in ("title", "snippet", "domain", "url")
    ).lower()
    phrases = [str(term or "").strip().lower() for term in core_terms if str(term or "").strip()]
    tokens: list[str] = []
    seen: set[str] = set()
    for term in core_terms:
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_]*|[\u4e00-\u9fff]{2,}", str(term or "").lower()):
            if is_generic_search_term(token) or len(token) < 2 or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    phrase_hits = sum(1 for phrase in phrases if phrase and phrase in text)
    token_hits = sum(1 for token in tokens if token in text)
    phrase_score = phrase_hits / max(1, len(phrases))
    token_denominator = max(1, min(4, len(tokens)))
    token_score = token_hits / token_denominator
    if tokens and token_hits == 1 and phrase_hits == 0:
        token_score *= 0.15  # stricter: single-token-only match is weak signal
    return min(1.0, max(phrase_score, token_score))


def positive_relevance_items(items: list[dict[str, Any]], min_score: float = 0.06) -> list[dict[str, Any]]:
    return [item for item in items if float(item.get("sourceRelevance") or 0) >= min_score]


def public_reference_score(item: dict[str, Any]) -> int:
    """Return 0-100 display score.  Monotonically consistent with ranking because
    dedupe_and_rank sorts by this value before assigning weightedRank."""
    relevance = float(item.get("sourceRelevance") or 0)
    if relevance <= 0:
        return 0
    language_score = float(item.get("resultLanguageScore") if item.get("resultLanguageScore") is not None else 1)
    raw = float(item.get("score") or 0)
    # Normalize algorithm_score to 0-35 range (typical range -70..+80)
    normalized_raw = max(0.0, min(35.0, (raw + 30) * 0.35))
    value = relevance * 45 + language_score * 20 + normalized_raw
    return max(0, min(100, round(value)))


def language_code_for_search(language: str) -> str:
    return "zh-CN" if str(language or "").lower().startswith("zh") else "en-US"


def result_language_score(item: dict[str, Any], language: str) -> float:
    text = " ".join(str(item.get(key) or "") for key in ("title", "snippet", "domain", "url"))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    kana = len(re.findall(r"[\u3040-\u30ff]", text))
    hangul = len(re.findall(r"[\uac00-\ud7af]", text))
    latin_words = len(re.findall(r"\b[A-Za-z]{3,}\b", text))
    if str(language or "").lower().startswith("zh"):
        if kana or hangul:
            return 0.0
        if cjk >= 2:
            return 1.0
        return 0.45 if latin_words else 0.25
    if cjk or kana or hangul:
        return 0.0
    return 1.0 if latin_words >= 2 else 0.35


def keep_relevant_items(items: list[dict[str, Any]], core_terms: list[str], source: str, tuning: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], int]:
    if not items:
        return items, 0
    if not core_terms:
        for item in items:
            item["sourceRelevance"] = 1.0
        return items, 0
    for item in items:
        score = relevance_score(item, core_terms)
        item["sourceRelevance"] = round(score, 3)
    return items, 0


def normalize_result(item: dict[str, Any], index: int, query: str, base_url: str = "") -> dict[str, Any]:
    url = normalize_url(str(item.get("url") or item.get("link") or ""), base_url)
    title = str(item.get("title") or item.get("name") or url or "Untitled reference").strip()
    snippet = str(item.get("snippet") or item.get("content") or item.get("description") or "").strip()
    thumbnail = normalize_url(str(item.get("thumbnail") or item.get("image") or item.get("img_src") or ""), base_url)
    domain = str(item.get("source_domain") or item.get("domain") or domain_of(url))
    score_source = {**item, "thumbnail": thumbnail}
    score = weighted_score(score_source, index, query)
    # 上游（如 newsfilter）可能已提供 authority_weight；若缺失则从商品域权重表补全，
    # 而非像原来那样默认为 0，导致 algorithm_rerank 中 authority 项形同虚设。
    upstream_authority = float(item.get("authority_weight") or item.get("authority") or 0)
    authority_weight = upstream_authority if upstream_authority > 0 else get_domain_authority(domain)
    return {
        "id": item.get("id") or item_id(url, title),
        "rank": index + 1,
        "weightedRank": index + 1,
        "score": score,
        "title": title[:180],
        "url": url,
        "domain": domain,
        "snippet": snippet[:520],
        "thumbnail": thumbnail,
        "thumbnailFallback": DEFAULT_THUMBNAILS[index % len(DEFAULT_THUMBNAILS)],
        "reason": str(item.get("reason") or "").strip(),
        "publishTime": item.get("publish_time") or item.get("publishedDate") or "",
        "isIndependent": bool(item.get("is_independent", True)),
        "authorityWeight": round(authority_weight, 4),
    }


async def search_searxng(settings: dict[str, Any], queries: list[str], max_results: int, language: str = "zh") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = str(settings.get("searxngEndpoint") or "").rstrip("/")
    if not base:
        return [], {"mode": "searxng", "skipped": "missing endpoint"}
    started = perf_counter()
    normalized_queries = [q for q in queries if q][:8]
    # Fetch multiple pages per query so we get more raw candidates before filtering.
    # SearXNG typically returns ~10 results per page; 3 pages → ~30 per query.
    pages_per_query: int = max(1, int(settings.get("pagesPerQuery") or 3))
    raw_items: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=float(settings.get("timeoutSeconds") or 25)) as client:
        for search_query in normalized_queries:
            for page in range(1, pages_per_query + 1):
                try:
                    response = await client.get(
                        f"{base}/search",
                        params={
                            "q": search_query,
                            "format": "json",
                            "categories": "general",
                            "language": language_code_for_search(language),
                            "pageno": page,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    page_items = (data.get("results") or [])
                    if not page_items:
                        break  # no more results for this query, skip remaining pages
                    for item in page_items[: max_results]:
                        if isinstance(item, dict):
                            item = dict(item)
                            item["_sourceQuery"] = search_query
                        raw_items.append(item)
                except Exception:
                    break  # skip remaining pages on error
    query_for_score = normalized_queries[0] if normalized_queries else ""
    normalized = []
    for index, item in enumerate(raw_items):
        result = normalize_result(item, index, query_for_score, base)
        result["sourceQuery"] = item.get("_sourceQuery") if isinstance(item, dict) else ""
        result["resultLanguageScore"] = round(result_language_score(result, language), 3)
        normalized.append(result)
    return normalized, {
        "mode": "searxng",
        "seconds": round(perf_counter() - started, 3),
        "searchQueries": normalized_queries,
        "pagesPerQuery": pages_per_query,
    }


async def search_searxng_with_seed_retry(
    settings: dict[str, Any],
    input_data: dict[str, Any],
    queries: list[str],
    max_results: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    language = str(input_data.get("language") or settings.get("language") or "zh").lower()
    found, source_meta = await search_searxng(settings, queries, max_results, language)
    if found:
        return found, source_meta
    seed_queries = build_search_variants(input_data, product_query_text(input_data, queries[0] if queries else ""))
    retry_queries = [query for query in seed_queries if query not in set(queries)]
    if not retry_queries:
        return found, source_meta
    retry_found, retry_meta = await search_searxng(settings, retry_queries, max_results, language)
    source_meta["retry"] = {
        "reason": "empty_result_seed_queries",
        "searchQueries": retry_meta.get("searchQueries") or [],
        "seconds": retry_meta.get("seconds"),
        "count": len(retry_found),
    }
    source_meta["seconds"] = round(float(source_meta.get("seconds") or 0) + float(retry_meta.get("seconds") or 0), 3)
    return retry_found, source_meta


async def filter_rank_candidates_with_endpoint(
    settings: dict[str, Any],
    tuning: dict[str, Any],
    input_data: dict[str, Any],
    candidates: list[dict[str, Any]],
    max_results: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoint = str(tuning.get("rankerEndpoint") or "").strip()
    if not tuning.get("rankerEnabled"):
        return candidates, {"mode": "ranker", "skipped": "disabled"}
    if not endpoint:
        return candidates, {"mode": "ranker", "skipped": "missing endpoint"}
    payload = {
        "input": compact_input_for_ranker(input_data),
        "candidates": candidates[: max(1, min(120, len(candidates)))],
        "maxResults": max_results,
    }
    started = perf_counter()
    async with httpx.AsyncClient(timeout=float(settings.get("timeoutSeconds") or 25)) as client:
        response = await client.post(endpoint, json=payload)
    response.raise_for_status()
    data = response.json()
    raw_items = data.get("items") or data.get("ranked") or data.get("results") or data.get("model_ranked_evidence") or []
    if not isinstance(raw_items, list):
        return candidates, {"mode": "ranker", "seconds": round(perf_counter() - started, 3), "skipped": "invalid response shape"}
    normalized = [normalize_result(item, index, "", "") for index, item in enumerate(raw_items) if isinstance(item, dict)]
    return normalized or candidates, {
        "mode": "ranker",
        "seconds": round(perf_counter() - started, 3),
        "inputCount": len(candidates),
        "outputCount": len(normalized),
    }


def compact_input_for_ranker(input_data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: input_data.get(key)
        for key in ("language", "productType", "productName", "market", "targetAudience", "promotionGoal", "keywords", "brief")
        if input_data.get(key)
    }


def dedupe_and_rank(items: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for item in items:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append(item)
    # Compute displayScore for every candidate first so we can sort by it.
    # This guarantees the list the user sees has monotonically non-increasing
    # displayScore — no more "score jumps up" in the middle of the results.
    for item in clean:
        item["displayScore"] = public_reference_score(item)
    # Primary sort: displayScore desc; tie-break: algorithm score desc
    clean.sort(key=lambda item: (
        -float(item.get("displayScore") or 0),
        -float(item.get("score") or 0),
        item.get("domain") or "",
        item.get("title") or "",
    ))
    # Only keep items that pass the minimum relevance threshold.
    # No fallback to irrelevant results: if nothing passes, return empty so the
    # caller / UI can show a "no relevant results" message instead of garbage.
    positive = positive_relevance_items(clean)
    for index, item in enumerate(positive[:max_results], start=1):
        item["weightedRank"] = index
    return positive[:max_results]


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for item in items:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append(item)
    return clean


def algorithm_rerank_references(items: list[dict[str, Any]], max_results: int, tuning: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = perf_counter()
    tuning = tuning or {}
    domain_weights = tuning.get("domainWeights") or {}
    clean = dedupe_items(items)

    # ── 来源独立性标记 ────────────────────────────────────────────────────────
    # 复用 newsfilter 的 _independence_judge 思路：同一域名只有第一条结果标记为
    # 独立来源，鼓励搜索结果覆盖多元平台，避免同一网站刷屏。
    # 注：此处在去重后重新计算，而非依赖上游字段（SearXNG 不提供该字段）。
    seen_domains_for_independence: set[str] = set()
    for item in clean:
        d = str(item.get("domain") or "").replace("www.", "").lower()
        if d:
            item["isIndependent"] = d not in seen_domains_for_independence
            seen_domains_for_independence.add(d)

    for item in clean:
        source_rank = max(1, int(item.get("rank") or item.get("weightedRank") or 99))
        authority = float(item.get("authorityWeight") or 0)
        independent = 1.0 if item.get("isIndependent", True) else 0.0
        repeat_probability = float(item.get("repeat_probability") or item.get("repeatProbability") or 0)
        relevance = float(item.get("sourceRelevance") or 0)
        language_score = float(item.get("resultLanguageScore") if item.get("resultLanguageScore") is not None else 1)
        base_score = float(item.get("score") or 0)
        domain = str(item.get("domain") or "").replace("www.", "").lower()
        domain_boost = float(domain_weights.get(domain) or 0)
        # 时间新鲜度：复用 newsfilter 的时间衰减公式 exp(-λ×天数)，
        # λ=0.04 适合商品内容（半衰期 ~17 天，新闻用 0.1 即 7 天）
        freshness = freshness_score(str(item.get("publishTime") or ""))
        # URL 质量过滤：购物车/登录/结算页无实质内容，直接重罚
        url_pen = url_quality_penalty(str(item.get("url") or ""))
        low_relevance_penalty = 72 if relevance <= 0 else max(0.0, 0.25 - relevance) * 52
        language_penalty = (1 - max(0.0, min(1.0, language_score))) * 90
        low_value_penalty = 36 if domain in LOW_VALUE_DOMAINS else 0
        algorithm_score = (
            max(0, 20 - source_rank) * 1.8
            + authority * 12          # 商品域权重表填充，确保评测站/电商权重有效
            + independent * 2.5       # 来源多元性奖励
            + relevance * 34
            + min(base_score, 18)
            + domain_boost
            + freshness * 4           # 时间衰减加分，最高 +4（当天内容）
            - repeat_probability * 6
            - low_relevance_penalty
            - language_penalty
            - low_value_penalty
            - url_pen                 # 购物车/登录页扣分
        )
        item["score"] = round(algorithm_score, 4)
        item["reason"] = item.get("reason") or "按商品相关性、来源权威度、独立来源多样性、内容时效综合排序。"
    positive_count = len(positive_relevance_items(clean))
    zero_relevance_count = sum(1 for item in clean if float(item.get("sourceRelevance") or 0) <= 0)
    ranked = dedupe_and_rank(clean, max_results)
    return ranked, {
        "mode": "algorithm_rerank",
        "seconds": round(perf_counter() - started, 3),
        "inputCount": len(clean),
        "outputCount": len(ranked),
        "positiveCount": positive_count,
        "zeroRelevanceCount": zero_relevance_count,
        "displayPolicy": "positive_relevance_only",
    }


async def search_references(input_data: dict[str, Any]) -> dict[str, Any]:
    config = read_config(mask_key=False)
    settings = config.get("searchSettings") or {}
    tuning = source_tuning(settings)
    max_results = max(3, min(30, int(input_data.get("maxResults") or settings.get("maxResults") or 20)))
    analysis_max_results = max(max_results, min(120, int(input_data.get("analysisMaxResults") or settings.get("analysisMaxResults") or 80)))
    plan = await build_model_search_plan(config, input_data, analysis_max_results)
    queries = [str(item).strip() for item in (plan.get("queries") or []) if str(item or "").strip()]
    if not queries:
        queries = fallback_search_plan(input_data, max_results)["queries"]
    query = str(plan.get("primaryQuery") or (queries[0] if queries else "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="请先填写商品类型、商品名称、用户需求或搜索词。")

    errors: list[str] = []
    items: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "query": query,
        "sources": [],
        "sourceTuning": tuning,
        "coreTerms": plan.get("coreTerms") or [],
        "searchVariants": queries,
        "searchPlan": {
            "source": plan.get("source"),
            "primaryQuery": query,
            "queries": queries,
            "coreTerms": plan.get("coreTerms") or [],
            "error": plan.get("error"),
        },
    }
    core_terms = [str(term).strip().lower() for term in (plan.get("coreTerms") or []) if str(term or "").strip()]
    if not tuning.get("searxngEnabled"):
        meta["sources"].append({"mode": "searxng", "skipped": "disabled by searchSettings.searxngEnabled"})
    else:
        try:
            found, source_meta = await search_searxng_with_seed_retry(settings, input_data, queries, analysis_max_results)
            for item in found:
                item["sourceMode"] = "searxng"
            found, dropped = keep_relevant_items(found, core_terms, "searxng", tuning)
            source_meta["droppedIrrelevant"] = dropped
            source_meta["relevanceMode"] = "score_only_no_drop"
            items.extend(found)
            meta["sources"].append(source_meta)
        except Exception as exc:
            errors.append(f"searxng: {exc}")

    customer_items, customer_meta = customer_source_candidates(settings, tuning, core_terms)
    if customer_items:
        items.extend(customer_items)
    meta["sources"].append(customer_meta)

    try:
        items, ranker_meta = await filter_rank_candidates_with_endpoint(settings, tuning, input_data, items, analysis_max_results)
        meta["sources"].append(ranker_meta)
    except Exception as exc:
        errors.append(f"ranker: {exc}")
        meta["sources"].append({"mode": "ranker", "error": str(exc)})
    ranked, rerank_meta = algorithm_rerank_references(items, analysis_max_results, tuning)
    meta["finalRerank"] = rerank_meta
    display_items = ranked[:max_results]
    return {
        "query": query,
        "items": display_items,
        "analysisItems": ranked,
        "errors": errors,
        "meta": meta,
    }


async def generate_image_placeholder(input_data):
    from typing import Any
    prompt = str(input_data.get("prompt") or "").strip()
    if not prompt:
        article = str(input_data.get("article") or input_data.get("brief") or "")
        prompt = f"Product editorial blog image based on: {article[:600]}"
    return {
        "status": "pending_provider",
        "message": "图片生成模型尚未配置，已保留接口和前端入口。",
        "prompt": prompt,
        "image": None,
    }


def parse_customer_source_payload(payload):
    import hashlib
    urls = payload.get("urls")
    if isinstance(urls, str):
        parsed_urls = parse_customer_urls_text(urls)
    elif isinstance(urls, list):
        parsed_urls = normalize_customer_sources([{"name": "tmp", "urls": urls}])[0]["urls"] if urls else []
    else:
        parsed_urls = parse_customer_urls_text(str(payload.get("text") or ""))
    return {
        "id": str(payload.get("id") or f"customer_source_{hashlib.sha1(str(payload).encode('utf-8')).hexdigest()[:10]}"),
        "name": str(payload.get("name") or "客户搜索源").strip(),
        "enabled": payload.get("enabled", True) is not False,
        "weight": float(payload.get("weight") or 3),
        "urls": parsed_urls,
    }
