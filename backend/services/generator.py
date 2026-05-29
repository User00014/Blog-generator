import json
import re
import uuid
import difflib
import asyncio
import hashlib
from html import unescape
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException
from bs4 import BeautifulSoup
from simhash import Simhash

from backend.services.model_client import build_messages, call_task_model
from backend.settings import EEAT_RULES_PATH, REFERENCE_CACHE_DIR
from backend.services.storage import read_config, save_blog


AI_EXPOSURE_NOTES = {
    "zh": (
        "内部 AI 检索曝光策略：首段给出可引用答案；明确商品实体、品牌、目标用户、场景、规格和替代品；"
        "用自然语言问题做标题；增加证据密度、表格、清单、FAQ、适用/不适用人群；"
        "保持真人编辑口吻，写具体场景、取舍和限制，减少模板化营销词。"
    ),
    "en": (
        "Internal AI-search visibility strategy: answer directly in the opening; clarify product entities, brand, "
        "audience, use cases, specs, and alternatives; use natural-language questions as headings; add evidence, "
        "tables, lists, FAQ, fit/not-fit guidance; keep a human editorial voice with concrete scenarios, tradeoffs, "
        "and limitations instead of generic marketing phrasing."
    ),
}

REVISION_SYSTEM_PROMPTS = {
    "zh": (
        "你是内容改写 AI，只能根据评价建议和人工反馈直接优化当前 Blog 正文。"
        "禁止修改、输出或讨论 prompt。禁止返回 updatedPrompt、promptPatch、systemPrompt 等字段。"
        "只返回严格 JSON，不要 markdown 代码块，不要 JSON 外文字。"
        "JSON 字段必须是：revisedArticle, changeSummary, added, removed, changedFocus。"
        "revisedArticle 的内容由任务要求决定：若 segmentInstruction 要求只改写当前片段，"
        "则 revisedArticle 只放该片段的 Markdown，严禁把整篇文章塞入；"
        "若未指定片段模式，则 revisedArticle 放完整文章 Markdown。"
        "added 和 removed 必须是字符串数组。"
    ),
    "en": (
        "You are a content revision AI. Directly improve the current Blog article using evaluator advice and human feedback. "
        "Do not modify, output, or discuss prompts. Never return updatedPrompt, promptPatch, or systemPrompt. "
        "Return strict JSON only, with no markdown fence and no prose outside JSON. "
        "Required keys: revisedArticle, changeSummary, added, removed, changedFocus. "
        "The scope of revisedArticle is determined by the task: if segmentInstruction asks for only the current segment, "
        "revisedArticle must contain ONLY that segment's Markdown — never the full article; "
        "if no segment mode is specified, revisedArticle should be the full Markdown article. "
        "added and removed must be arrays of strings."
    ),
}


def active_language(input_data: dict[str, Any], config: dict[str, Any]) -> str:
    language = input_data.get("language") or config.get("language") or "zh"
    return "en" if language == "en" else "zh"


def prompts_for(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, str]:
    language = active_language(input_data, config)
    prompts = dict((config.get("prompts") or {}).get(language) or {})
    overrides = (input_data.get("promptOverrides") or {}).get(language) or input_data.get("promptOverrides") or {}
    prompts.update(overrides)
    return prompts


def config_prompts_for_language(config: dict[str, Any], language: str) -> dict[str, str]:
    all_prompts = config.get("prompts") or {}
    return dict(all_prompts.get(language) or all_prompts.get("zh") or {})


def extract_json(text: str, label: str) -> dict[str, Any]:
    if not text:
        raise HTTPException(status_code=502, detail=f"{label} 模型没有返回内容。")
    cleaned = clean_json_text(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = extract_embedded_json_object(cleaned)
        if parsed is None:
            raise HTTPException(status_code=502, detail=f"{label} 模型必须返回有效 JSON。请调整对应 prompt。")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail=f"{label} 模型返回的 JSON 必须是对象。")
    return parsed


def clean_json_text(text: str) -> str:
    cleaned = str(text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    cleaned = re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def extract_embedded_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


async def repair_json_response(
    config: dict[str, Any],
    task: str,
    language: str,
    raw_text: str,
    label: str,
    expected_fields: list[str],
) -> dict[str, Any]:
    if language == "zh":
        system = (
            "你是 JSON 修复器。把模型输出转换成严格 JSON 对象。"
            "不要添加解释，不要 markdown 代码块，不要 JSON 外文字。"
            f"必须尽量保留字段：{', '.join(expected_fields)}。"
        )
    else:
        system = (
            "You repair model output into a strict JSON object. "
            "Do not add explanations, markdown fences, or text outside JSON. "
            f"Preserve these fields when possible: {', '.join(expected_fields)}."
        )
    repaired_text = await call_task_model(
        config,
        task,
        build_messages(
            system,
            {
                "invalidOutput": str(raw_text or "")[:12000],
                "expectedFields": expected_fields,
                "instruction": "Return one valid JSON object only.",
            },
        ),
    )
    return extract_json(repaired_text, f"{label} repair")


def extract_revision_json(text: str, label: str) -> dict[str, Any]:
    try:
        parsed = extract_json(text, label)
        if parsed.get("updatedPrompt") and not any(parsed.get(key) for key in ("revisedArticle", "article", "updatedArticle")):
            raise HTTPException(status_code=502, detail=f"{label} 模型返回了旧的 prompt 修改格式。")
        return parsed
    except HTTPException:
        raw = str(text or "").strip()
        if "updatedPrompt" in raw and "revisedArticle" not in raw:
            return {
                "revisedArticle": "",
                "changeSummary": "模型返回了旧的 prompt 修改格式，本轮未采用该结果。",
                "added": [],
                "removed": [],
                "changedFocus": "格式错误：返回了 updatedPrompt，而不是 revisedArticle。",
                "formatError": True,
            }
        article = re.sub(r"^```(?:markdown|md)?\s*", "", raw, flags=re.IGNORECASE)
        article = re.sub(r"\s*```$", "", article).strip()
        article = re.sub(r"^json\s*", "", article, flags=re.IGNORECASE).strip()
        # 二次兜底：若原始文本本身是合法 JSON 对象，尝试再解析一次提取 revisedArticle。
        # 这能防止"模型返回了合法 JSON 但第一次 extract_json 因为字符问题失败"时整个 JSON 字符串被存入正文。
        if article.startswith("{"):
            try:
                inner = json.loads(article)
                if isinstance(inner, dict):
                    inner_article = inner.get("revisedArticle") or inner.get("article") or inner.get("updatedArticle")
                    if inner_article and isinstance(inner_article, str) and inner_article.strip():
                        return {
                            "revisedArticle": inner_article.strip(),
                            "changeSummary": inner.get("changeSummary") or "二次解析成功，已提取 revisedArticle。",
                            "added": inner.get("added") or [],
                            "removed": inner.get("removed") or [],
                            "changedFocus": inner.get("changedFocus") or "",
                        }
            except (json.JSONDecodeError, ValueError):
                pass
        if article:
            return {
                "revisedArticle": article,
                "changeSummary": "模型未返回严格 JSON，系统已将返回正文作为修订文章保存。",
                "added": [],
                "removed": [],
                "changedFocus": "格式兜底：保留模型返回的文章内容。",
            }
        raise


def append_images(article: str, images: list[dict[str, Any]], language: str) -> str:
    usable = [item for item in images if item.get("dataUrl")]
    if not usable:
        return article
    heading = "## 附图" if language == "zh" else "## Images"
    lines = [article.rstrip(), "", heading, ""]
    for index, image in enumerate(usable, start=1):
        name = image.get("name") or f"image-{index}"
        lines.append(f"![{name}]({image['dataUrl']})")
    return "\n".join(lines).strip() + "\n"


def insert_images_contextually(article: str, images: list[dict[str, Any]], language: str) -> str:
    usable = [item for item in images if item.get("dataUrl")]
    if not usable:
        return article
    lines = article.rstrip().splitlines()
    if not lines:
        return append_images(article, usable, language)
    insert_positions = [index for index, line in enumerate(lines) if re.match(r"^##\s+", line)]
    if not insert_positions:
        return append_images(article, usable, language)
    offset = 0
    for index, image in enumerate(usable):
        name = image.get("name") or f"image-{index + 1}"
        position = insert_positions[min(index, len(insert_positions) - 1)] + 2 + offset
        block = ["", f"![{name}]({image['dataUrl']})", ""]
        lines[position:position] = block
        offset += len(block)
    return "\n".join(lines).strip() + "\n"


def reference_context(input_data: dict[str, Any]) -> dict[str, Any]:
    selected_citations = input_data.get("selectedCitationReferences") or input_data.get("citationReferences") or []
    search_results = input_data.get("searchResults") or []
    return {
        "citationReferences": selected_citations,
        "availableSearchResults": search_results[:15] if isinstance(search_results, list) else [],
        "citationInstruction": (
            "引用链接需要在正文相关段落中以 Markdown 超链接自然插入，并在文章结尾添加“参考来源”小节列出标题和链接。不要复制来源原文或大段引用。"
            if input_data.get("language") != "en"
            else "Insert selected citation links naturally as Markdown hyperlinks in relevant paragraphs and add a final 'Sources' section with source titles and links. Do not copy source text or quote long passages."
        ),
    }


def as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items() if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def load_eeat_rules() -> dict[str, Any]:
    try:
        return json.loads(EEAT_RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"items": [], "defaultWeights": {"Experience": 0.2, "Expertise": 0.2, "Authoritativeness": 0.2, "Trustworthiness": 0.4}, "blockerIds": []}


def eeat_rules_for_prompt(rules: dict[str, Any], rule_evaluation: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """构造给模型的 60 项 checklist。
    优化：如果某项已被规则锁死（locked=True），就不再把 check/score0/0.5/1 描述送给模型，
    只送 id/quadrant/name/blocker + lockedScore。模型只需对未锁项做完整描述匹配，能显著降 token。
    """
    locked_ids: dict[str, float] = {}
    if isinstance(rule_evaluation, dict):
        # evaluate_eeat_rules() 实际返回 itemScores 列表（每项含 id/score/locked），
        # 同时还提供 lockedIds 作为有序 id 列表；这里两个都兜底处理。
        for entry in (rule_evaluation.get("itemScores") or rule_evaluation.get("items") or []):
            if isinstance(entry, dict) and entry.get("locked") and entry.get("id"):
                locked_ids[str(entry["id"])] = entry.get("score")
        # 兼容只提供 lockedIds 的旧形态
        if not locked_ids:
            for item_id in (rule_evaluation.get("lockedIds") or []):
                locked_ids[str(item_id)] = None
    rows: list[dict[str, Any]] = []
    for item in rules.get("items", []):
        item_id = item.get("id")
        if item_id in locked_ids:
            # 已被规则锁定：模型不需要 check/score 描述，sysprompt 里有"locked=True 优先沿用"的硬规则
            row = {"id": item_id, "name": item.get("name"), "locked": True}
            score_val = locked_ids[item_id]
            if score_val is not None:
                row["score"] = score_val
            if item.get("blocker"):
                row["blocker"] = True
            rows.append(row)
        else:
            rows.append(
                {
                    "id": item_id,
                    "quadrant": item.get("quadrant"),
                    "name": item.get("name"),
                    "check": item.get("check"),
                    "score0": item.get("score0"),
                    "score0.5": item.get("score05"),
                    "score1": item.get("score1"),
                    "blocker": item.get("blocker"),
                }
            )
    return rows


def normalize_item_score(value: Any) -> float:
    number = numeric_score(value, 0)
    if number not in {0, 0.5, 1}:
        if number <= 0.25:
            return 0
        if number < 0.75:
            return 0.5
        return 1
    return number


def text_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[。！？.!?])\s+|[\n\r]+", str(text or "")) if item.strip()]


def plain_article_text(article: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", str(article or ""))
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_>`~-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_html(html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", str(html or ""))
    cleaned = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", unescape(cleaned)).strip()


def markdown_links(text: str) -> list[dict[str, str]]:
    links = []
    for match in re.finditer(r"\[([^\]]+)]\((https?://[^)\s]+)\)", str(text or ""), flags=re.IGNORECASE):
        links.append({"text": match.group(1).strip(), "url": match.group(2).strip()})
    for match in re.finditer(r"(?<!\()https?://[^\s)>\"]+", str(text or ""), flags=re.IGNORECASE):
        url = match.group(0).rstrip(".,;，。；")
        if not any(item["url"] == url for item in links):
            links.append({"text": "", "url": url})
    return links


def link_domains(links: list[dict[str, str]]) -> list[str]:
    domains = []
    for link in links:
        domain = urlparse(link.get("url") or "").netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            domains.append(domain)
    return domains


def extract_json_ld(html: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for match in re.finditer(r"(?is)<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", str(html or "")):
        raw = unescape(match.group(1)).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        values = parsed if isinstance(parsed, list) else [parsed]
        for value in values:
            if isinstance(value, dict):
                graph = value.get("@graph")
                if isinstance(graph, list):
                    blocks.extend([item for item in graph if isinstance(item, dict)])
                blocks.append(value)
    return blocks


def html_attr_values(html: str, attr: str) -> list[str]:
    return [
        unescape(match.group(1)).strip()
        for match in re.finditer(rf"(?is)\b{re.escape(attr)}=[\"']([^\"']+)[\"']", str(html or ""))
        if match.group(1).strip()
    ]


def html_links(html: str) -> list[dict[str, str]]:
    links = []
    for match in re.finditer(r"(?is)<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", str(html or "")):
        text = strip_html(match.group(2))
        links.append({"text": text, "url": unescape(match.group(1)).strip()})
    return links


def score_row(item_id: str, score: float, evidence: str, suggestion: str = "", method: str = "rule") -> dict[str, Any]:
    return {
        "id": item_id,
        "score": normalize_item_score(score),
        "evidence": evidence[:500],
        "suggestion": suggestion[:500],
        "source": "rule",
        "method": method,
        "locked": True,
    }


def score_by_count(count: int, half_at: int, full_at: int) -> float:
    if count >= full_at:
        return 1
    if count >= half_at:
        return 0.5
    return 0


def has_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def evaluate_eeat_rules(article: str, input_data: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic scores for checklist items that can be judged safely from available artifacts."""
    html = str(input_data.get("html") or input_data.get("pageHtml") or input_data.get("renderedHtml") or "")
    page_url = str(input_data.get("pageUrl") or input_data.get("url") or input_data.get("canonicalUrl") or "").strip()
    title = str(input_data.get("selectedTitle") or input_data.get("title") or markdown_title(article, "") or "")
    product_terms = [
        str(input_data.get(key) or "").strip()
        for key in ("productName", "productType", "brand", "primaryKeyword", "keyword")
        if str(input_data.get(key) or "").strip()
    ]
    plain = plain_article_text(article)
    combined_text = f"{plain}\n{strip_html(html)}".strip()
    links = markdown_links(article) + html_links(html)
    domains = link_domains(links)
    json_ld = extract_json_ld(html)
    has_html = bool(html.strip())
    scores: dict[str, dict[str, Any]] = {}

    first_person_sentences = [
        sentence for sentence in text_sentences(combined_text)
        if re.search(r"\b(I|we|our|my)\b|我|我们|笔者|本人", sentence, flags=re.IGNORECASE)
    ]
    concrete_first_person = [
        sentence for sentence in first_person_sentences
        if re.search(r"\d|年|月|日|小时|分钟|克|毫升|℃|bar|psi|mm|cm|kg|oz|店|家|office|studio|kitchen|cafe", sentence, flags=re.IGNORECASE)
    ]
    if first_person_sentences:
        scores["E1"] = score_row(
            "E1",
            1 if concrete_first_person else 0.5,
            f"检测到 {len(first_person_sentences)} 个第一人称句子，其中 {len(concrete_first_person)} 个含具体场景/数值。",
            "补充具体时间、地点、设备或数值场景。" if not concrete_first_person else "",
            "regex + concrete-context",
        )
    else:
        scores["E1"] = score_row("E1", 0, "未检测到第一人称体验段落。", "增加真实第一人称使用经历。", "regex")

    unit_matches = re.findall(r"\b\d+(?:\.\d+)?\s?(?:g|kg|mg|ml|l|oz|mm|cm|m|inch|inches|℃|°C|°F|bar|psi|rpm|w|v|min|minutes?|hours?|秒|分钟|小时|克|千克|毫升|升|厘米|毫米|度)\b", combined_text, flags=re.IGNORECASE)
    scores["E2"] = score_row("E2", score_by_count(len(unit_matches), 3, 6), f"检测到 {len(unit_matches)} 个带单位的具体数值。", "增加可验证的规格、参数或测试数值。", "regex units")

    model_patterns = re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}(?:\s+[A-Z0-9][A-Za-z0-9-]{1,}){0,3}\b", combined_text)
    mentioned_terms = [term for term in product_terms if term and re.search(re.escape(term), combined_text, flags=re.IGNORECASE)]
    model_count = len(set(model_patterns + mentioned_terms))
    scores["E3"] = score_row("E3", score_by_count(model_count, 1, 3), f"检测到 {model_count} 个品牌/型号/商品实体候选。", "增加具体品牌、型号或商品名，减少泛称。", "regex entity")

    if re.search(r"!\[[^\]]*]\([^)]+\)|<img\b", f"{article}\n{html}", flags=re.IGNORECASE):
        scores["E4"] = score_row("E4", 0.5, "检测到图片，但未接入 stock pHash 库，无法确认原创性。", "上传原创图片或接入图片指纹库后复核。", "image presence fallback")

    time_anchors = re.findall(r"\b(?:19|20)\d{2}\b|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{1,2}\s*(?:月|日|号)|today|yesterday|last\s+(?:week|month|year)", combined_text, flags=re.IGNORECASE)
    scores["E5"] = score_row("E5", score_by_count(len(time_anchors), 1, 3), f"检测到 {len(time_anchors)} 个时间锚点。", "增加具体时间与事件描述。", "regex date")

    scores["E10"] = score_row(
        "E10",
        1 if has_any([r"相比.*(之前|以前)", r"compared with my previous", r"versus what I used", r"我之前用"], combined_text) else 0,
        "检测个人化对比表达。",
        "增加“相比我之前使用的 X”的个人基准对比。",
        "regex comparison",
    )

    if has_html:
        author_meta = re.search(r"(?is)<meta[^>]+name=[\"']author[\"'][^>]+content=[\"']([^\"']+)", html)
        byline = re.search(r"(?is)(class|rel)=[\"'][^\"']*(author|byline)[^\"']*[\"'][^>]*>(.*?)<", html)
        scores["X1"] = score_row("X1", 1 if author_meta and byline else (0.5 if author_meta or byline else 0), "检测 meta author 与 byline。", "补齐作者署名和 meta author。", "html meta/byline")
        bio_match = re.search(r"(?is)(author-bio|bio|作者简介)[\s\S]{0,800}", html)
        bio_text = strip_html(bio_match.group(0)) if bio_match else ""
        scores["X2"] = score_row("X2", 1 if len(bio_text) >= 160 else (0.5 if len(bio_text) >= 50 else 0), f"作者 Bio 长度 {len(bio_text)}。", "增加具体作者简介、领域经验和资质。", "html bio length")

    person_blocks = [item for item in json_ld if str(item.get("@type", "")).lower() == "person"]
    if has_html:
        person_complete = any(item.get("name") and (item.get("url") or item.get("sameAs")) for item in person_blocks)
        scores["X3"] = score_row("X3", 1 if person_complete else (0.5 if person_blocks else 0), f"检测到 {len(person_blocks)} 个 Person JSON-LD。", "补齐 Person schema 的 name/url/sameAs。", "json-ld")
        same_as = " ".join(str(url) for item in person_blocks for url in (item.get("sameAs") if isinstance(item.get("sameAs"), list) else [item.get("sameAs")]))
        scores["X4"] = score_row("X4", 1 if "linkedin.com" in same_as.lower() else 0, "检测 Person sameAs LinkedIn。", "在 Person.sameAs 中添加可验证 LinkedIn 页面。", "json-ld url")
        scores["X5"] = score_row("X5", 1 if re.search(r"orcid|scholar\.google|researchgate|pubmed", same_as, flags=re.IGNORECASE) else 0, "检测专业/学术 sameAs。", "添加 ORCID、Scholar、ResearchGate 等专业页面。", "json-ld url")

    credential_patterns = [r"\b(PhD|M\.D\.|MD|CFA|CPA|RD|DDS|DVM)\b", r"博士|医生|医师|注册会计师|分析师|营养师|律师|工程师|认证"]
    scores["X6"] = score_row("X6", 1 if has_any(credential_patterns, combined_text) else 0, "检测作者资质关键词。", "在作者简介或文末明确专业资质。", "credential regex")

    if has_html:
        author_links = [link for link in html_links(html) if re.search(r"author|作者|about", link.get("url", "") + " " + link.get("text", ""), flags=re.IGNORECASE)]
        scores["X7"] = score_row("X7", 1 if author_links else 0, f"检测到 {len(author_links)} 个作者相关链接。", "让作者署名链接到个人主页。", "html links")

    domain_terms = set(re.findall(r"\b[A-Za-z][A-Za-z-]{5,}\b", combined_text))
    supplied_terms = set()
    for key in ("terms", "industryTerms", "coreTerms"):
        value = input_data.get(key) or []
        if isinstance(value, str):
            value = re.split(r"[,，\n]", value)
        supplied_terms.update(str(item).strip() for item in value if str(item).strip())
    term_hits = [term for term in supplied_terms if re.search(re.escape(term), combined_text, flags=re.IGNORECASE)]
    technical_count = len(term_hits) if supplied_terms else len([term for term in domain_terms if len(term) > 8])
    scores["X8"] = score_row("X8", score_by_count(technical_count, 5, 12), f"检测到 {technical_count} 个领域术语候选。", "增加并解释领域术语。", "term matching")

    citation_count = len(links) + len(re.findall(r"根据|来源|研究|报告|数据显示|according to|source:|study|report", combined_text, flags=re.IGNORECASE))
    scores["X10"] = score_row("X10", score_by_count(citation_count, 2, 5), f"检测到 {citation_count} 个来源/引用信号。", "为事实陈述添加具名来源或链接。", "citation regex")

    external_links = [link for link in links if urlparse(link.get("url") or "").scheme in {"http", "https"}]
    scores["X11"] = score_row("X11", score_by_count(len(external_links), 1, 3), f"检测到 {len(external_links)} 个外部链接。", "补充权威外部引用。", "external links")

    edu_domains = [d for d in domains if d.endswith(".edu")]
    gov_domains = [d for d in domains if ".gov" in d or d.endswith(".gov.cn")]
    wiki_domains = [d for d in domains if "wikipedia.org" in d or "wikidata.org" in d]
    industry_domains = [d for d in domains if re.search(r"org$|association|institute|standard|iso|sca|specialtycoffee", d)]
    authority_groups = sum(1 for group in (edu_domains, gov_domains, wiki_domains, industry_domains) if group)
    scores["X12"] = score_row("X12", score_by_count(authority_groups, 2, 3), f"权威引用类型覆盖 {authority_groups} 类。", "覆盖学术、政府、百科、行业组织等多类来源。", "domain groups")
    scores["A5"] = score_row("A5", score_by_count(len(edu_domains), 1, 2), f".edu 外链 {len(edu_domains)} 个。", "需要时引用教育/研究机构页面。", "domain suffix")
    scores["A6"] = score_row("A6", score_by_count(len(gov_domains), 1, 2), f".gov 外链 {len(gov_domains)} 个。", "需要时引用政府或监管机构页面。", "domain suffix")
    scores["A7"] = score_row("A7", score_by_count(len(wiki_domains), 1, 2), f"Wikipedia/Wikidata 外链 {len(wiki_domains)} 个。", "补充百科实体链接。", "domain match")
    scores["A8"] = score_row("A8", score_by_count(len(industry_domains), 1, 2), f"行业头部/组织域名外链 {len(industry_domains)} 个。", "引用行业组织、标准或头部媒体。", "domain whitelist fallback")
    authority_domain_count = len(set(edu_domains + gov_domains + wiki_domains + industry_domains))
    scores["A9"] = score_row("A9", score_by_count(authority_domain_count, 2, 4), f"权威外链不同域 {authority_domain_count} 个。", "提高权威来源域名多样性。", "domain diversity")

    methodology_heading = re.search(r"^#{2,4}\s+.*(方法|测试|评测|Methodology|How we tested|Testing|Process)", article, flags=re.IGNORECASE | re.MULTILINE)
    scores["X13"] = score_row("X13", 1 if methodology_heading else 0, "检测方法论/测试小节标题。", "为评测或研究类内容增加方法论小节。", "heading regex")

    precise_numbers = len(re.findall(r"\b\d+(?:\.\d+)?\s?(?:g|kg|mg|ml|mm|cm|℃|bar|psi|%|分钟|小时|min|hours?)\b", combined_text, flags=re.IGNORECASE))
    vague_numbers = len(re.findall(r"大约|约|差不多|很多|不少|some|many|roughly|about", combined_text, flags=re.IGNORECASE))
    scores["X14"] = score_row("X14", 1 if precise_numbers >= vague_numbers + 2 else (0.5 if precise_numbers else 0), f"精确数值 {precise_numbers} 个，模糊量词 {vague_numbers} 个。", "用精确参数替换模糊表达。", "numeric precision")

    if has_html:
        dates = " ".join(str(item.get("datePublished") or "") for item in json_ld)
        scores["A1"] = score_row("A1", 1 if re.search(r"\d{4}-\d{1,2}-\d{1,2}", dates) else 0, "检测 JSON-LD datePublished。", "补充 schema datePublished。", "json-ld date")
        modified = " ".join(str(item.get("dateModified") or "") for item in json_ld)
        scores["A2"] = score_row("A2", 1 if re.search(r"\d{4}-\d{1,2}-\d{1,2}", modified) else 0, "检测 JSON-LD dateModified。", "补充 schema dateModified。", "json-ld date")
        visible_date = re.search(r"(?is)<time\b|class=[\"'][^\"']*(date|published|modified)[^\"']*[\"']", html)
        scores["A3"] = score_row("A3", 1 if visible_date else 0, "检测可见日期节点。", "在页面显示发布时间/更新时间。", "html date")

    title_years = set(re.findall(r"\b(20\d{2})\b", title))
    body_years = set(re.findall(r"\b(20\d{2})\b", combined_text))
    if title_years:
        scores["A4"] = score_row("A4", 1 if title_years & body_years else 0.5, f"标题年份 {sorted(title_years)}，正文年份 {sorted(body_years)[:5]}。", "确保标题年份和正文/发布日期一致。", "year compare")

    if has_html:
        logo_signal = re.search(r"(?is)(logo|brand)[^>]*(alt|class|src)|alt=[\"'][^\"']*(logo|品牌)", html)
        scores["A10"] = score_row("A10", 1 if logo_signal else 0, "检测 Logo class/alt/src 信号。", "在 Header/Footer 添加品牌 Logo。", "html logo")
        org_blocks = [item for item in json_ld if str(item.get("@type", "")).lower() == "organization"]
        org_complete = any(item.get("name") and (item.get("url") or item.get("sameAs")) for item in org_blocks)
        scores["A11"] = score_row("A11", 1 if org_complete else (0.5 if org_blocks else 0), f"检测到 {len(org_blocks)} 个 Organization JSON-LD。", "补齐 Organization schema。", "json-ld organization")
        org_same_as = " ".join(str(url) for item in org_blocks for url in (item.get("sameAs") if isinstance(item.get("sameAs"), list) else [item.get("sameAs")]))
        scores["A12"] = score_row("A12", 1 if re.search(r"linkedin|facebook|instagram|crunchbase|trustpilot|bbb", org_same_as, flags=re.IGNORECASE) else 0, "检测组织认证/社媒 sameAs。", "添加企业认证或官方社媒页面。", "json-ld url")
        org_names = [str(item.get("name") or "") for item in org_blocks if item.get("name")]
        brand = str(input_data.get("brand") or input_data.get("siteName") or "").strip()
        consistency = bool(brand and any(brand.lower() in name.lower() or name.lower() in title.lower() for name in org_names))
        scores["A13"] = score_row("A13", 1 if consistency else (0.5 if org_names else 0), f"组织名候选：{', '.join(org_names[:3])}", "确保 Logo、Organization.name、标题品牌一致。", "string compare")
        about_links = [link for link in html_links(html) if re.search(r"about|关于|公司|brand", link.get("text", "") + " " + link.get("url", ""), flags=re.IGNORECASE)]
        scores["A14"] = score_row("A14", 1 if about_links else 0, f"检测到 {len(about_links)} 个 About 入口。", "在导航或页脚添加 About 页面入口。", "html nav")

    if page_url:
        parsed_url = urlparse(page_url)
        scores["T1"] = score_row("T1", 1 if parsed_url.scheme == "https" else 0, f"页面 URL 协议：{parsed_url.scheme or 'missing'}。", "使用 HTTPS 页面并避免混合内容。", "url protocol")
        query = parse_qs(parsed_url.query)
        unstable = any(key.lower() in {"sid", "session", "sessionid", "token"} for key in query)
        scores["T14"] = score_row("T14", 0 if unstable else (0.5 if query else 1), "检测 URL 查询参数与 session 信号。", "使用稳定、无 session 参数的 permalink。", "url structure")

    if has_html:
        nav_text = " ".join(f"{link.get('text')} {link.get('url')}" for link in html_links(html))
        scores["T3"] = score_row("T3", 1 if re.search(r"contact|联系", nav_text, flags=re.IGNORECASE) else 0, "检测 Contact 页面入口。", "添加 Contact/联系我们页面。", "html nav")
        scores["T4"] = score_row("T4", 1 if re.search(r"[\w.+-]+@[\w.-]+\.\w+|\+?\d[\d\s().-]{7,}|地址|address", strip_html(html), flags=re.IGNORECASE) else 0, "检测邮箱/电话/地址。", "在 Contact 页或页脚提供联系方式。", "contact regex")
        scores["T5"] = score_row("T5", 1 if re.search(r"privacy|隐私", nav_text, flags=re.IGNORECASE) else 0, "检测 Privacy 页面入口。", "添加隐私政策页面。", "html nav")
        scores["T6"] = score_row("T6", 1 if re.search(r"terms|service|条款|服务协议", nav_text, flags=re.IGNORECASE) else 0, "检测 Terms 页面入口。", "添加服务条款页面。", "html nav")
        scores["T7"] = score_row("T7", 1 if re.search(r"cookie|consent|gdpr|同意", html, flags=re.IGNORECASE) else 0, "检测 Cookie/同意通知信号。", "按地区要求添加 Cookie 同意通知。", "html class")
        footer = re.search(r"(?is)<footer\b.*?</footer>", html)
        footer_text = strip_html(footer.group(0)) if footer else ""
        scores["T8"] = score_row("T8", 1 if re.search(r"公司|地址|注册|copyright|inc\.|ltd\.|llc|address", footer_text, flags=re.IGNORECASE) else 0, "检测页脚组织信息。", "在 Footer 添加组织信息。", "footer parse")
        hidden = len(re.findall(r"display\s*:\s*none|font-size\s*:\s*[0-5]px|opacity\s*:\s*0", html, flags=re.IGNORECASE))
        scores["T10"] = score_row("T10", 0 if hidden else 1, f"检测到 {hidden} 个隐藏/极小文本 CSS 信号。", "移除隐藏文本和异常极小字号。", "css regex")
        author_click = [link for link in html_links(html) if re.search(r"author|作者", link.get("text", "") + " " + link.get("url", ""), flags=re.IGNORECASE)]
        scores["T13"] = score_row("T13", 1 if author_click else 0, f"检测到 {len(author_click)} 个作者署名链接。", "让作者署名可点击。", "html author link")
        ad_count = len(re.findall(r"class=[\"'][^\"']*(ad-| ads |advert|sponsor)[^\"']*[\"']", html, flags=re.IGNORECASE))
        scores["T19"] = score_row("T19", 0 if ad_count >= 6 else (0.5 if ad_count >= 3 else 1), f"广告元素候选 {ad_count} 个。", "降低首屏广告比例。", "ad element regex")

    paragraphs = [para.strip() for para in re.split(r"\n{2,}|[。.!?！？]", plain) if len(para.strip()) >= 30]
    keyword_candidates = [term for term in product_terms if len(term) >= 3]
    stuffed = 0
    for para in paragraphs:
        words = max(1, len(re.findall(r"[\w\u4e00-\u9fff]+", para)))
        hits = sum(len(re.findall(re.escape(term), para, flags=re.IGNORECASE)) for term in keyword_candidates)
        if keyword_candidates and hits / words > 0.04:
            stuffed += 1
    scores["T11"] = score_row("T11", 0 if stuffed >= 3 else (0.5 if stuffed else 1), f"关键词密度异常段落 {stuffed} 个。", "减少重复堆砌，改用自然同义表达。", "density")

    spam_domains = [d for d in domains if re.search(r"casino|bet|porn|loan|payday|viagra|adult", d)]
    scores["T12"] = score_row("T12", 0 if spam_domains else 1, f"垃圾/高风险外链候选 {len(spam_domains)} 个。", "移除垃圾、博彩、色情、恶意外链。", "domain regex")

    ymyl = has_any([r"医疗|金融|法律|投资|贷款|保险|medicine|medical|finance|legal|investment|loan"], combined_text)
    disclaimer = has_any([r"不构成.*建议|免责声明|consult.*professional|not.*advice|for informational purposes"], combined_text)
    if ymyl:
        scores["T15"] = score_row("T15", 1 if disclaimer else 0, "检测 YMYL 主题与免责声明。", "医疗/金融/法律内容必须加入清晰免责声明。", "ymyl disclaimer")

    affiliate_links = [link for link in links if re.search(r"aff|affiliate|ref=|tag=|utm_", link.get("url", ""), flags=re.IGNORECASE)]
    if affiliate_links:
        disclosure = has_any([r"联盟|佣金|赞助|affiliate|commission|sponsored"], combined_text)
        scores["T16"] = score_row("T16", 1 if disclosure else 0, f"检测到 {len(affiliate_links)} 个联盟/追踪链接。", "含联盟链接时明确披露利益关系。", "affiliate regex")

    ai_signal = has_any([r"AI 辅助|人工智能辅助|AI-assisted|generated with AI"], combined_text)
    if input_data.get("requiresAiDisclosure"):
        scores["T17"] = score_row("T17", 1 if ai_signal else 0, "按配置要求检测 AI 辅助披露。", "按地区法律要求添加 AI 辅助披露。", "metadata + keyword")

    return {
        "itemScores": list(scores.values()),
        "lockedIds": sorted(scores.keys()),
        "count": len(scores),
        "availableArtifacts": {
            "article": bool(article.strip()),
            "html": has_html,
            "pageUrl": bool(page_url),
            "links": len(links),
            "jsonLdBlocks": len(json_ld),
        },
    }


def apply_rule_scores(model_eval: dict[str, Any], rule_eval: dict[str, Any]) -> dict[str, Any]:
    raw_scores = model_eval.get("itemScores") or model_eval.get("items") or []
    if isinstance(raw_scores, dict):
        raw_scores = [{"id": key, **(value if isinstance(value, dict) else {"score": value})} for key, value in raw_scores.items()]
    model_by_id = {
        str(row.get("id")): {**row, "source": row.get("source") or "llm", "locked": bool(row.get("locked"))}
        for row in raw_scores
        if isinstance(row, dict) and row.get("id")
    }
    rule_by_id = {
        str(row.get("id")): row
        for row in (rule_eval.get("itemScores") or [])
        if isinstance(row, dict) and row.get("id")
    }
    merged = dict(model_eval)
    for item_id, row in rule_by_id.items():
        model_by_id[item_id] = {
            **model_by_id.get(item_id, {}),
            **row,
            "source": "rule",
            "locked": True,
        }
    merged["itemScores"] = list(model_by_id.values())
    merged["ruleEvaluation"] = rule_eval
    merged["scoringSources"] = {
        "ruleLocked": len(rule_by_id),
        "llm": max(0, 60 - len(rule_by_id)),
        "ruleLockedIds": sorted(rule_by_id.keys()),
    }
    return merged


EEAT_ADVICE_DETAILS = {
    "E1": {
        "meaning": "检查文章里有没有真实的第一人称使用经验，而不是只写泛泛的产品介绍。",
        "fix": "补一段“我/我们在什么时间、什么地点、用什么设备测试/使用”的经历，最好带时间、地点、设备名或参数。",
        "example": "例如：2026 年 5 月，我们在上海办公室用 350ml 拉花缸测试 180ml 全脂牛奶，连续打发 6 次后记录了奶泡稳定性。",
    },
    "E4": {
        "meaning": "检查配图是否像原创实拍或自有图片，而不是通用图库图、供应商图或无关装饰图。",
        "fix": "如果有商品图，说明图片来源、拍摄场景或插入实际商品/使用场景图；没有图时可以补充“实拍图/使用步骤图/对比图”。",
        "example": "例如：加入一张商品在咖啡机旁使用的实拍图，并在图注里说明拍摄场景和关键细节。",
    },
    "E6": {
        "meaning": "检查文章是否有可感知的真人故事片段，让读者相信作者确实接触过这个商品或场景。",
        "fix": "加入一个短故事：用户为什么需要这个商品、使用前遇到什么问题、使用后有什么具体变化。",
        "example": "例如：店员原来用普通拉花缸时倒流不稳，换成尖嘴设计后，在高峰期连续出杯时图案更一致。",
    },
    "E7": {
        "meaning": "检查文章有没有“踩坑、修正认知、学到经验”的过程，这能让内容更像真人编辑，而不是一次性生成的营销文。",
        "fix": "补一段“最初以为 X，实际发现 Y，所以建议 Z”的反转或学习经历。",
        "example": "例如：最初以为容量越大越好，实际测试后发现 350ml 更适合单杯拿铁，因为控流更稳、余奶更少。",
    },
    "E8": {
        "meaning": "检查文章是否说明评测或判断依据，比如用了什么工具、什么对比方法、怎么得出结论。",
        "fix": "补一个方法说明小节，写清楚比较维度、设备、测试步骤或资料来源。",
        "example": "例如：从容量、嘴型、握持手感、刻度清晰度、清洁难度 5 个维度对比，并记录每次打发时间和奶泡状态。",
    },
    "E9": {
        "meaning": "检查文章有没有视觉、触感、声音、味道等可观察细节，避免只剩抽象形容词。",
        "fix": "补充读者能想象出来的细节，例如手感、重量、倒奶速度、边缘处理、清洁时的残留情况。",
        "example": "例如：壶嘴边缘更薄，倒细线时不容易突然断流；手柄内侧圆润，连续使用时手指压力更小。",
    },
    "X9": {
        "meaning": "检查专业术语是否解释清楚，避免只堆名词。",
        "fix": "第一次出现专业词时，用一句话解释它和购买/使用决策有什么关系。",
        "example": "例如：控流指倒奶时液体流速是否稳定，它会影响拉花线条的粗细和连续性。",
    },
    "X13": {
        "meaning": "检查文章是否交代评测方法，尤其是评测、对比、推荐类内容。",
        "fix": "增加“我们如何判断/测试”小节，列出对比维度和样本限制。",
        "example": "例如：本次只比较 350-600ml 不锈钢拉花缸，重点看壶嘴、手柄、刻度和清洁便利性。",
    },
    "X15": {
        "meaning": "检查文章是否承认反方观点或不适用场景，避免一味夸产品。",
        "fix": "增加“不适合谁/什么时候不建议买”的段落。",
        "example": "例如：如果主要做大杯饮品，350ml 可能偏小；如果只家用偶尔打奶，不一定需要专业尖嘴款。",
    },
}


def detailed_eeat_advice(item: dict[str, Any]) -> str:
    item_id = str(item.get("id") or "")
    name = str(item.get("name") or "")
    score = item.get("score")
    suggestion = str(item.get("suggestion") or "").strip()
    detail = EEAT_ADVICE_DETAILS.get(item_id)
    prefix = f"{item_id} {name}（当前 {score} 分）："
    if detail:
        parts = [
            prefix,
            f"含义：{detail['meaning']}",
            f"怎么改：{suggestion or detail['fix']}",
            f"参考写法：{detail['example']}",
        ]
        return "\n".join(parts)
    if suggestion:
        return f"{prefix}\n含义：这个指标检查“{name}”是否达到表格满分标准。\n怎么改：{suggestion}"
    return (
        f"{prefix}\n"
        f"含义：这个指标检查“{name}”是否达到表格满分标准。\n"
        "怎么改：补充更具体、可验证、能被读者直接感知的证据或说明，避免只写泛泛结论。"
    )


def calculate_eeat_report(model_eval: dict[str, Any], rules: dict[str, Any], content_type: str = "") -> dict[str, Any]:
    items = rules.get("items") or []
    raw_scores = model_eval.get("itemScores") or model_eval.get("items") or []
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw_scores, dict):
        raw_scores = [{"id": key, **(value if isinstance(value, dict) else {"score": value})} for key, value in raw_scores.items()]
    if isinstance(raw_scores, list):
        for row in raw_scores:
            if isinstance(row, dict) and row.get("id"):
                by_id[str(row.get("id"))] = row
    item_scores: list[dict[str, Any]] = []
    quadrant_sums: dict[str, float] = {}
    quadrant_counts: dict[str, int] = {}
    for item in items:
        item_id = str(item.get("id"))
        quadrant = str(item.get("quadrant") or "")
        scored = by_id.get(item_id, {})
        score = normalize_item_score(scored.get("score"))
        item_scores.append(
            {
                "id": item_id,
                "quadrant": quadrant,
                "name": item.get("name"),
                "score": score,
                "evidence": str(scored.get("evidence") or scored.get("reason") or "").strip(),
                "suggestion": str(scored.get("suggestion") or scored.get("fix") or "").strip(),
                "source": scored.get("source") or "llm",
                "method": scored.get("method") or "",
                "locked": bool(scored.get("locked")),
                "blocker": bool(item.get("blocker")) or item_id in set(rules.get("blockerIds") or []),
            }
        )
        quadrant_sums[quadrant] = quadrant_sums.get(quadrant, 0) + score
        quadrant_counts[quadrant] = quadrant_counts.get(quadrant, 0) + 1
    quadrant_scores = {
        key: round((quadrant_sums.get(key, 0) / max(1, quadrant_counts.get(key, 0))) * 100, 1)
        for key in ["Experience", "Expertise", "Authoritativeness", "Trustworthiness"]
    }
    weights = (rules.get("contentTypeWeights") or {}).get(content_type) or rules.get("defaultWeights") or {}
    total = round(sum(quadrant_scores.get(key, 0) * float(weights.get(key, 0)) for key in quadrant_scores), 1)
    blockers = [item for item in item_scores if item.get("blocker") and float(item.get("score") or 0) == 0]
    threshold = float(rules.get("publishThreshold") or 75)
    repair_threshold = float(rules.get("repairThreshold") or 60)
    if blockers:
        status = "manual_review"
    elif total >= threshold:
        status = "publishable"
    elif total >= repair_threshold:
        status = "repair"
    else:
        status = "regenerate"
    failed = [item for item in item_scores if float(item.get("score") or 0) < 1]
    advice = [detailed_eeat_advice(item) for item in failed[:12]]
    return {
        "score": total,
        "combinedScore": total,
        "quadrantScores": quadrant_scores,
        "weights": weights,
        "contentType": content_type or "通用 Article（默认）",
        "itemScores": item_scores,
        "failedItems": failed[:20],
        "blockers": blockers,
        "publishStatus": status,
        "revisionAdvice": [item for item in advice if item],
        "scoringSources": model_eval.get("scoringSources") or {},
        "ruleEvaluation": model_eval.get("ruleEvaluation") or {},
    }


def markdown_title(article: str, fallback: str = "Untitled Blog") -> str:
    title_match = re.search(r"^#\s+(.+)$", str(article or ""), flags=re.MULTILINE)
    return title_match.group(1).strip() if title_match else fallback


def first_topic_title(outline: dict[str, Any]) -> str:
    topics = outline.get("topics") or []
    if not isinstance(topics, list) or not topics:
        return ""
    first = topics[0]
    if isinstance(first, dict):
        return str(first.get("title") or first.get("name") or "").strip()
    return str(first or "").strip()


def parse_percent(value: Any, fallback: int) -> int:
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
        number = float(match.group(0)) if match else float(fallback)
    if 0 < number <= 1:
        number *= 100
    return max(1, min(99, int(round(number))))


def compact_reference(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": item.get("id") or f"ref-{index + 1}",
        "rank": item.get("weightedRank") or item.get("rank") or index + 1,
        "title": item.get("title") or "",
        "url": item.get("url") or "",
        "domain": item.get("domain") or "",
        "snippet": item.get("snippet") or "",
        "score": item.get("score") or "",
    }


def compact_reference_title_only(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": item.get("id") or f"ref-{index + 1}",
        "rank": item.get("weightedRank") or item.get("rank") or index + 1,
        "title": str(item.get("title") or "").strip()[:180],
        "url": str(item.get("url") or "").strip()[:260],
        "domain": str(item.get("domain") or "").strip()[:120],
    }


def compact_input_brief(input_data: dict[str, Any]) -> dict[str, Any]:
    allowed = [
        "language",
        "outputLanguage",
        "brief",
        "productType",
        "productName",
        "targetAudience",
        "promotionGoal",
        "market",
        "keywords",
        "manualQuery",
        "selectedTitle",
    ]
    return {key: input_data.get(key) for key in allowed if input_data.get(key) not in (None, "", [])}


TITLE_SEO_HOOKS = {
    "zh": ["最佳", "推荐", "完整", "终极", "全面", "实测", "对比", "排名", "指南", "选购", "评测", "测评", "综合", "深度"],
    "en": ["best", "top", "ultimate", "complete", "definitive", "comprehensive", "review", "vs", "comparison", "guide", "tested"],
}

TITLE_GEO_BLACKLIST_STARTS = {
    "zh": ["为什么", "怎么", "如何", "上面", "前面", "上文", "这一篇", "本文", "接下来"],
    "en": ["why", "how", "the above", "in this", "continuing from", "following up"],
}

CONTENT_BLACKLIST = {
    "zh": [
        "总之",
        "综上所述",
        "值得注意的是",
        "深入探讨",
        "深入剖析",
        "在当今快速发展的",
        "让我们一起来",
        "毫无疑问",
        "全面而深入",
        "独一无二",
        "改变游戏规则",
        "在本文中",
        "希望本文对你有帮助",
        "接下来我们来看",
        "从某种意义上说",
        "不可否认",
    ],
    "en": [
        "in conclusion",
        "to sum up",
        "it's important to note",
        "delve into",
        "dive deep into",
        "in today's fast-paced",
        "let's explore",
        "let's take a look at",
        "undoubtedly",
        "without a doubt",
        "firstly",
        "secondly",
        "lastly",
        "comprehensive and in-depth",
        "unique and unparalleled",
        "game-changer",
        "in this article",
        "i hope this helps",
        "let's move on to",
        "in a sense",
        "it cannot be denied",
    ],
}


def cache_key(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:32]


def cache_path_for_url(url: str) -> Any:
    REFERENCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return REFERENCE_CACHE_DIR / f"{cache_key(url)}.json"


def plain_text_from_html(html: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    meta_desc = ""
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta and meta.get("content"):
        meta_desc = str(meta.get("content")).strip()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    blocks: list[str] = []
    for node in main.find_all(["h1", "h2", "h3", "p", "li", "td", "th"], recursive=True):
        text = " ".join(node.get_text(" ", strip=True).split())
        if len(text) >= 24 and not re.search(r"cookie|privacy preference|subscribe|sign up|版权所有|隐私|登录", text, flags=re.I):
            blocks.append(text)
    if not blocks:
        text = " ".join(main.get_text(" ", strip=True).split())
        blocks = [text]
    deduped: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        key = block[:160].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(block)
    text = "\n\n".join(deduped)
    return text[:24000], title, [meta_desc] if meta_desc else []


async def fetch_reference_page(item: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
    url = str(item.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return {**item, "fetchStatus": "skipped", "content": str(item.get("snippet") or "")}
    path = cache_path_for_url(url)
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("content"):
                return {**item, **cached, "fetchStatus": cached.get("fetchStatus") or "cached"}
        except Exception:
            pass
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AI-Blog-Generator/1.0; +local)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            raise ValueError(f"unsupported content-type {content_type}")
        text, page_title, meta_bits = plain_text_from_html(response.text)
        data = {
            "url": url,
            "title": page_title or item.get("title") or "",
            "domain": item.get("domain") or domain_from_url(url),
            "content": text or str(item.get("snippet") or ""),
            "snippet": item.get("snippet") or (meta_bits[0] if meta_bits else ""),
            "fetchedAt": started,
            "fetchStatus": "ok" if text else "empty",
            "contentChars": len(text or ""),
        }
    except Exception as exc:
        data = {
            "url": url,
            "title": item.get("title") or "",
            "domain": item.get("domain") or domain_from_url(url),
            "content": str(item.get("snippet") or ""),
            "snippet": item.get("snippet") or "",
            "fetchedAt": started,
            "fetchStatus": "fallback_snippet",
            "fetchError": str(exc)[:240],
            "contentChars": len(str(item.get("snippet") or "")),
        }
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return {**item, **data}


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


async def fetch_reference_pages(input_data: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    existing = input_data.get("referencePages")
    if isinstance(existing, list) and any(isinstance(item, dict) and (item.get("content") or item.get("snippet")) for item in existing):
        normalized_existing = []
        for item in existing:
            if not isinstance(item, dict):
                continue
            normalized_existing.append({**item, "content": item.get("content") or item.get("snippet") or ""})
        return normalized_existing[:limit]
    source_results = input_data.get("analysisSearchResults") or input_data.get("searchResults") or []
    results = [item for item in source_results if isinstance(item, dict)][:limit]
    if not results:
        return []
    tasks = [fetch_reference_page(item) for item in results]
    pages = await asyncio.gather(*tasks)
    return [page for page in pages if isinstance(page, dict)]


def simhash_value(text: str) -> Simhash:
    tokens = tokenize_title(text)
    if not tokens:
        tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", str(text or "").lower())
    return Simhash(tokens or [str(text or "")[:64]])


def simhash_distance(left: str, right: str) -> int:
    return simhash_value(left).distance(simhash_value(right))


def alternate_language(language: str) -> str:
    return "en" if language == "zh" else "zh"


def keyword_for(input_data: dict[str, Any], language: str | None = None) -> str:
    candidates: list[str] = []
    for key in ("primaryKeyword", "keywords", "productType", "productName", "manualQuery"):
        value = str(input_data.get(key) or "").strip()
        if not value:
            continue
        if key == "keywords":
            value = re.split(r"[,，;\n]", value)[0].strip() or value
        candidates.append(value)
    if language == "zh":
        for value in candidates:
            if re.search(r"[\u4e00-\u9fff]", value):
                return value
    if language == "en":
        for value in candidates:
            if re.search(r"[A-Za-z]", value):
                return value
    if candidates:
        return candidates[0]
    return "this product" if language == "en" else "该商品"


def tokenize_title(text: str) -> list[str]:
    raw = str(text or "").lower()
    words = re.findall(r"[a-z0-9][a-z0-9\-]{1,}", raw)
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", raw)
    cjk_tokens: list[str] = []
    for chunk in cjk:
        if len(chunk) <= 4:
            cjk_tokens.append(chunk)
        else:
            cjk_tokens.extend(chunk[index : index + 2] for index in range(0, len(chunk) - 1, 2))
    return words + cjk_tokens


def lexical_overlap(left: str, right: str) -> float:
    left_tokens = set(tokenize_title(left))
    right_tokens = set(tokenize_title(right))
    if not left_tokens or not right_tokens:
        return 0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def extract_candidate_entities(text: str) -> list[str]:
    cleaned = unescape(str(text or ""))
    candidates: list[str] = []
    candidates.extend(re.findall(r"\b[A-Z][A-Za-z0-9]*(?:[\s\-][A-Z0-9][A-Za-z0-9]*){0,3}\b", cleaned))
    candidates.extend(re.findall(r"\b\d+(?:\.\d+)?\s?(?:mm|cm|ml|oz|g|kg|w|v|bar|psi|℃|°c|元|美元|inch|inches)\b", cleaned, flags=re.IGNORECASE))
    candidates.extend(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}(?:材质|规格|参数|型号|品牌|场景|问题|对比|指南|配件|工具)", cleaned))
    candidates.extend(re.findall(r"(?:不锈钢|陶瓷|玻璃|木柄|拉花|手冲|意式|咖啡|奶缸|粉锤|磨豆机|espresso|latte|pitcher|grinder|tamper|stainless steel)", cleaned, flags=re.IGNORECASE))
    normalized: list[str] = []
    for item in candidates:
        entity = re.sub(r"\s+", " ", str(item).strip(" -_:;,.，。"))
        if len(entity) < 2 or entity.lower() in {"http", "https", "www"}:
            continue
        if entity not in normalized:
            normalized.append(entity[:80])
    return normalized[:40]


def normalize_entity_key(entity: str) -> str:
    value = str(entity or "").lower().strip()
    value = re.sub(r"[\s\-_()/|:：,，.。]+", "", value)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value)


def entity_category(entity: str) -> str:
    value = entity.lower()
    if re.search(r"\d|mm|cm|ml|oz|kg|bar|psi|规格|参数|材质", value):
        return "attributes"
    if any(word in value for word in ["vs", "comparison", "compare", "对比", "versus"]):
        return "comparisons"
    if any(word in value for word in ["problem", "issue", "leak", "rust", "fail", "难", "漏", "问题", "失败"]):
        return "problems"
    if any(word in value for word in ["choose", "use", "clean", "buy", "选", "买", "使用", "清洁", "安装"]):
        return "actions"
    return "products"


def build_entity_gap_report(input_data: dict[str, Any], limit: int = 15) -> dict[str, Any]:
    source_results = input_data.get("referencePages") or input_data.get("analysisSearchResults") or input_data.get("searchResults") or []
    results = [item for item in source_results if isinstance(item, dict)][:40]
    seed_text = " ".join(
        str(input_data.get(key) or "")
        for key in ("productType", "productName", "keywords", "brief", "promotionGoal")
    )
    doc_count: Counter[str] = Counter()
    occurrence_count: Counter[str] = Counter()
    display_name: dict[str, str] = {}
    categories: dict[str, set[str]] = {
        "products": set(),
        "attributes": set(),
        "actions": set(),
        "problems": set(),
        "comparisons": set(),
    }

    seed_entities = extract_candidate_entities(seed_text)
    for entity in seed_entities:
        key = entity.lower()
        display_name[key] = entity
        doc_count[key] += 0
        categories.setdefault(entity_category(entity), set()).add(key)

    for result in results:
        text = " ".join(
            str(result.get(key) or "")
            for key in ("title", "snippet", "content", "domain", "url")
        )
        entities = extract_candidate_entities(text)
        seen_in_doc: set[str] = set()
        for entity in entities:
            key = entity.lower()
            display_name.setdefault(key, entity)
            occurrence_count[key] += max(1, text.lower().count(key))
            seen_in_doc.add(key)
            categories.setdefault(entity_category(entity), set()).add(key)
        for key in seen_in_doc:
            doc_count[key] += 1

    rows: list[dict[str, Any]] = []
    for key, name in display_name.items():
        if not name:
            continue
        coverage = int(doc_count.get(key, 0))
        occurrences = int(occurrence_count.get(key, 0))
        rows.append(
            {
                "entity": name,
                "normalized": key,
                "category": entity_category(name),
                "coverage": coverage,
                "occurrences": occurrences,
                "rarityScore": max(0, 20 - coverage * 4 - min(occurrences, 12)),
            }
        )
    rows.sort(key=lambda item: (item["coverage"], item["occurrences"], -len(str(item["entity"]))))
    gap_rows = [item for item in rows if item["coverage"] < 3][:limit]
    # coveredEntities 只包含 coverage >= 3 的实体（真正被竞品饱和覆盖的），按覆盖率从高到低排，
    # 传给正文 prompt 作为「避免重复」的反向参照。coverage < 3 的 gap 实体不得混入此列表。
    covered_rows = sorted([r for r in rows if r["coverage"] >= 3], key=lambda item: (-item["coverage"], item["occurrences"]))[:limit]
    categorized = {
        category: [
            display_name[key]
            for key in sorted(keys, key=lambda candidate: (doc_count.get(candidate, 0), occurrence_count.get(candidate, 0)))
        ][:limit]
        for category, keys in categories.items()
    }
    return {
        "entities": categorized,
        "coveredEntities": covered_rows,
        "gapEntities": gap_rows,
        "rareEntities": gap_rows,
        "sourceCount": len(results),
        "strategy": "entities with lower search-result coverage are prioritized as higher-rarity GEO opportunities",
    }


def normalize_extracted_entities(raw: Any) -> dict[str, list[str]]:
    categories = {"products": [], "attributes": [], "actions": [], "problems": [], "comparisons": []}
    if isinstance(raw, dict):
        raw = raw.get("entities") or raw
        for category in categories:
            values = raw.get(category) if isinstance(raw, dict) else []
            categories[category] = as_text_list(values)[:25]
    elif isinstance(raw, list):
        categories["products"] = as_text_list(raw)[:25]
    return categories


async def extract_entities_from_pages(
    config: dict[str, Any],
    input_data: dict[str, Any],
    pages: list[dict[str, Any]],
    language: str,
) -> list[dict[str, Any]]:
    if not pages:
        return []
    # 注意：每页 content 截断从 9000 → 4000 字符。
    # 4000 字符足够覆盖一篇页面正文的主要实体（典型 SERP 页正文 1500-3000 字符，规格/对比表通常在前半部分）。
    # 单次实体抽取 LLM 调用输入由约 45k token 降到约 20k token，单批成本 $0.18 → $0.06。
    page_payloads = [
        {
            "id": page.get("id") or f"ref-{index + 1}",
            "title": page.get("title") or "",
            "url": page.get("url") or "",
            "domain": page.get("domain") or "",
            "content": str(page.get("content") or page.get("snippet") or "")[:4000],
        }
        for index, page in enumerate(pages[:30])
    ]
    configured_prompt = config_prompts_for_language(config, language).get("entity_extractor") or ""
    fallback_system = (
        "你是 SERP 内容实体抽取器。你会看到若干网页正文摘录，请分别抽取具体实体。"
        "必须按 products, attributes, actions, problems, comparisons 五类返回。"
        "只抽取页面明确出现的实体、参数、品牌、型号、材料、步骤、痛点和比较对象，不要编造。"
        "返回严格 JSON：pages。每项包含 id, entities。entities 中五个字段都是字符串数组，单页每类最多15个。"
        if language == "zh"
        else "You are a SERP content entity extractor. For each page excerpt, extract concrete entities only. "
        "Return strict JSON: pages. Each item has id and entities with products, attributes, actions, problems, comparisons arrays. "
        "Only include entities, specs, brands, models, materials, actions, pain points, and comparison objects explicitly present in the page. Max 15 per category."
    )
    system = "\n\n".join(
        part
        for part in [
            configured_prompt.replace("{keyword}", keyword_for(input_data, language)) if configured_prompt else "",
            fallback_system,
            "批量输入时必须返回 JSON 对象：{\"pages\":[{\"id\":\"...\",\"entities\":{\"products\":[],\"attributes\":[],\"actions\":[],\"problems\":[],\"comparisons\":[]}}]}。"
            if language == "zh"
            else "For batch input, return a JSON object: {\"pages\":[{\"id\":\"...\",\"entities\":{\"products\":[],\"attributes\":[],\"actions\":[],\"problems\":[],\"comparisons\":[]}}]}.",
        ]
        if part
    )
    raw_pages = []
    extraction_errors: list[str] = []
    for offset in range(0, len(page_payloads), 10):
        batch = page_payloads[offset : offset + 10]
        try:
            text = await call_task_model(
                config,
                "entity_extractor",
                build_messages(
                    system,
                    {
                        "keyword": keyword_for(input_data, language),
                        "pages": batch,
                        "language": language,
                    },
                ),
            )
            parsed = extract_json(text, "SERP entity extraction")
            batch_pages = parsed.get("pages") or parsed.get("results") or []
            if isinstance(batch_pages, list):
                raw_pages.extend(batch_pages)
        except Exception as exc:
            extraction_errors.append(str(exc)[:240])

    by_id: dict[str, dict[str, list[str]]] = {}
    if isinstance(raw_pages, list):
        for item in raw_pages:
            if not isinstance(item, dict):
                continue
            ref_id = str(item.get("id") or "").strip()
            if ref_id:
                by_id[ref_id] = normalize_extracted_entities(item.get("entities") or item)

    extracted: list[dict[str, Any]] = []
    for page in page_payloads:
        ref_id = str(page.get("id") or "")
        entities = by_id.get(ref_id)
        source = "llm"
        if not entities:
            content_entities = extract_candidate_entities(" ".join([page.get("title", ""), page.get("content", "")]))
            entities = {"products": [], "attributes": [], "actions": [], "problems": [], "comparisons": []}
            for entity in content_entities:
                entities.setdefault(entity_category(entity), []).append(entity)
            source = "rule_fallback"
        extracted.append({**page, "entities": {key: list(dict.fromkeys(values))[:15] for key, values in entities.items()}, "entityExtractionSource": source})
    if extracted:
        extracted[0]["entityExtractionMeta"] = {
            "pageCount": len(page_payloads),
            "llmPages": sum(1 for item in extracted if item.get("entityExtractionSource") == "llm"),
            "ruleFallbackPages": sum(1 for item in extracted if item.get("entityExtractionSource") == "rule_fallback"),
            "errors": extraction_errors[:5],
        }
    return extracted


def entity_report_from_extractions(input_data: dict[str, Any], extracted_pages: list[dict[str, Any]], limit: int = 15) -> dict[str, Any]:
    doc_count: Counter[str] = Counter()
    occurrence_count: Counter[str] = Counter()
    display: dict[str, str] = {}
    category_map: dict[str, set[str]] = {"products": set(), "attributes": set(), "actions": set(), "problems": set(), "comparisons": set()}
    for page in extracted_pages:
        all_page_entities: set[str] = set()
        normalized_content = normalize_entity_key(str(page.get("content") or ""))
        for category, values in (page.get("entities") or {}).items():
            normalized_category = category if category in category_map else "products"
            for entity in as_text_list(values):
                key = normalize_entity_key(entity)
                if not key:
                    continue
                display.setdefault(key, entity)
                category_map[normalized_category].add(key)
                all_page_entities.add(key)
                occurrence_count[key] += max(1, normalized_content.count(key))
        for key in all_page_entities:
            doc_count[key] += 1
    for entity in extract_candidate_entities(" ".join(str(input_data.get(key) or "") for key in ("productType", "productName", "keywords", "brief"))):
        key = normalize_entity_key(entity)
        if not key:
            continue
        display.setdefault(key, entity)
        category_map.setdefault(entity_category(entity), set()).add(key)
    rows = [
        {
            "entity": name,
            "normalized": key,
            "category": next((cat for cat, keys in category_map.items() if key in keys), entity_category(name)),
            "coverage": int(doc_count.get(key, 0)),
            "occurrences": int(occurrence_count.get(key, 0)),
            "rarityScore": max(0, 20 - int(doc_count.get(key, 0)) * 4 - min(int(occurrence_count.get(key, 0)), 12)),
        }
        for key, name in display.items()
    ]
    rows.sort(key=lambda item: (item["coverage"], item["occurrences"], -item["rarityScore"], item["entity"]))
    # coveredEntities 只包含 coverage >= 3 的实体（真正被竞品饱和覆盖的），按覆盖率从高到低排，
    # 传给正文 prompt 作为「避免重复」的反向参照。coverage < 3 的 gap 实体不得混入此列表。
    covered = sorted([r for r in rows if r["coverage"] >= 3], key=lambda item: (-item["coverage"], item["occurrences"]))[:limit]
    gaps = [item for item in rows if item["coverage"] < 3][:limit]
    extraction_meta = {}
    if extracted_pages and isinstance(extracted_pages[0], dict):
        extraction_meta = extracted_pages[0].get("entityExtractionMeta") or {}
    return {
        "entities": {
            category: [display[key] for key in sorted(keys, key=lambda item: (doc_count.get(item, 0), occurrence_count.get(item, 0)))][:limit]
            for category, keys in category_map.items()
        },
        "coveredEntities": covered,
        "gapEntities": gaps,
        "rareEntities": gaps,
        "sourceCount": len(extracted_pages),
        "extractedPages": extracted_pages,
        "extractionMeta": extraction_meta,
        "matchingMethod": {
            "source": "fetched page body first; snippet/title only when body fetch is unavailable",
            "extraction": "LLM extracts explicit entities per reference page; rule-based keyword extraction is used only when the LLM extraction for a page fails",
            "crossPageMatch": "normalized surface-form matching across each page's extracted entity set",
            "semanticEmbedding": False,
            "coverageMeaning": "number of reference pages whose extracted entity set contains the same normalized entity",
        },
        "strategy": "LLM entity extraction from fetched SERP pages; entities with lower document coverage are prioritized.",
    }


async def build_serp_intelligence(config: dict[str, Any], input_data: dict[str, Any], language: str) -> dict[str, Any]:
    cached = input_data.get("serpIntelligence") or (input_data.get("outline") or {}).get("serpIntelligence")
    if isinstance(cached, dict) and cached.get("entityReport"):
        return cached
    pages = await fetch_reference_pages(input_data, limit=30)
    extracted = await extract_entities_from_pages(config, input_data, pages, language)
    entity_report = entity_report_from_extractions(input_data, extracted) if extracted else build_entity_gap_report({**input_data, "referencePages": pages})
    paa_questions = []
    for page in pages:
        paa_questions.extend(as_text_list(page.get("paa") or page.get("questions") or page.get("peopleAlsoAsk")))
    fetch_status = Counter(str(page.get("fetchStatus") or "unknown") for page in pages)
    non_full_content = fetch_status.get("fallback_snippet", 0) + fetch_status.get("empty", 0) + fetch_status.get("skipped", 0)
    fetch_meta = {
        "pageCount": len(pages),
        "ok": fetch_status.get("ok", 0),
        "cached": fetch_status.get("cached", 0),
        "empty": fetch_status.get("empty", 0),
        "skipped": fetch_status.get("skipped", 0),
        "fallbackSnippet": fetch_status.get("fallback_snippet", 0),
        "fallbackSnippetRate": round(fetch_status.get("fallback_snippet", 0) / max(1, len(pages)), 3),
        "nonFullContent": non_full_content,
        "nonFullContentRate": round(non_full_content / max(1, len(pages)), 3),
    }
    entity_meta = entity_report.get("extractionMeta") or {}
    return {
        "referencePages": pages,
        "entityReport": entity_report,
        "paaQuestions": list(dict.fromkeys(paa_questions))[:12],
        "fetchMeta": fetch_meta,
        "fallbackMeta": {
            "snippetFallbackRate": fetch_meta["fallbackSnippetRate"],
            "nonFullContentRate": fetch_meta["nonFullContentRate"],
            "entityRuleFallbackRate": round(float(entity_meta.get("ruleFallbackPages") or 0) / max(1, int(entity_meta.get("pageCount") or len(pages) or 1)), 3),
            "entityExtraction": entity_meta,
            "entityMatchingMethod": entity_report.get("matchingMethod") or {},
        },
    }


def fallback_intents(input_data: dict[str, Any], language: str) -> list[dict[str, Any]]:
    product = str(input_data.get("productName") or input_data.get("productType") or "").strip()
    product = product or ("this product" if language == "en" else "该商品")
    if language == "en":
        return [
            {
                "id": "intent-buying-guide",
                "title": f"{product} buying guide and selection criteria",
                "summary": "Users are comparing options and need clear fit, specs, tradeoffs, and purchase guidance.",
                "probability": 52,
                "recommended": True,
                "keywords": [product, "buying guide", "comparison", "FAQ"],
                "referenceIds": [],
                "outlineFocus": "Lead with purchase decision support, then compare scenarios, specs, pros/cons, and FAQ.",
            },
            {
                "id": "intent-use-case",
                "title": f"{product} use cases and practical benefits",
                "summary": "Users want to understand where the product fits in real daily or professional scenarios.",
                "probability": 31,
                "recommended": False,
                "keywords": [product, "use cases", "benefits"],
                "referenceIds": [],
                "outlineFocus": "Write around concrete user scenarios, benefits, limitations, and product-led examples.",
            },
            {
                "id": "intent-education",
                "title": f"What is {product} and how to choose one",
                "summary": "Users need entity-level education before they are ready to compare or buy.",
                "probability": 17,
                "recommended": False,
                "keywords": [product, "what is", "how to choose"],
                "referenceIds": [],
                "outlineFocus": "Start with a direct definition, then explain features, decision factors, and when to buy.",
            },
        ]
    return [
        {
            "id": "intent-buying-guide",
            "title": f"{product}选购与对比指南",
            "summary": "用户正在比较同类商品，需要明确适用人群、规格、取舍、价格区间和购买建议。",
            "probability": 52,
            "recommended": True,
            "keywords": [product, "选购", "对比", "FAQ"],
            "referenceIds": [],
            "outlineFocus": "围绕购买决策展开，先讲适用场景，再讲规格、优缺点、对比和常见问题。",
        },
        {
            "id": "intent-use-case",
            "title": f"{product}使用场景与卖点种草",
            "summary": "用户想知道商品能解决什么问题，适合哪些日常或专业使用场景。",
            "probability": 31,
            "recommended": False,
            "keywords": [product, "使用场景", "卖点"],
            "referenceIds": [],
            "outlineFocus": "用具体场景串联卖点、限制、适用/不适用人群，让内容更像真实编辑推荐。",
        },
        {
            "id": "intent-education",
            "title": f"{product}是什么以及如何选择",
            "summary": "用户处在认知阶段，需要先理解商品定义、核心参数和选择标准。",
            "probability": 17,
            "recommended": False,
            "keywords": [product, "是什么", "如何选择"],
            "referenceIds": [],
            "outlineFocus": "首段给出定义和直接答案，再解释参数、使用限制、购买时机和 FAQ。",
        },
    ]


def normalize_intent_options(data: dict[str, Any], input_data: dict[str, Any], language: str) -> list[dict[str, Any]]:
    raw = data.get("intents") or data.get("topics") or data.get("options") or []
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        raw = []

    references = input_data.get("searchResults") or []
    reference_ids = [
        str(item.get("id") or "")
        for item in references
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    options: list[dict[str, Any]] = []
    for index, item in enumerate(raw[:6]):
        if isinstance(item, str):
            title = item.strip()
            option = {"title": title}
        elif isinstance(item, dict):
            option = item
            title = str(item.get("title") or item.get("name") or item.get("intent") or item.get("topic") or "").strip()
        else:
            continue
        if not title:
            continue
        raw_refs = option.get("referenceIds") or option.get("references") or option.get("articles") or []
        if isinstance(raw_refs, dict):
            raw_refs = list(raw_refs.values())
        normalized_refs: list[str] = []
        for ref in raw_refs if isinstance(raw_refs, list) else [raw_refs]:
            ref_id = str(ref.get("id") if isinstance(ref, dict) else ref).strip()
            if ref_id and ref_id in reference_ids and ref_id not in normalized_refs:
                normalized_refs.append(ref_id)
        probability = parse_percent(
            option.get("probability") or option.get("share") or option.get("score") or option.get("percent"),
            max(12, 58 - index * 14),
        )
        options.append(
            {
                "id": str(option.get("id") or f"intent-{index + 1}").strip(),
                "title": title,
                "summary": str(option.get("summary") or option.get("description") or option.get("reason") or "").strip(),
                "probability": probability,
                "recommended": bool(option.get("recommended")) or index == 0,
                "keywords": as_text_list(option.get("keywords") or option.get("entities"))[:8],
                "referenceIds": normalized_refs[:6],
                "outlineFocus": str(option.get("outlineFocus") or option.get("writingFocus") or option.get("focus") or "").strip(),
            }
        )

    if not options:
        options = fallback_intents(input_data, language)
    options.sort(key=lambda item: (not item.get("recommended"), -int(item.get("probability") or 0)))
    if options:
        options[0]["recommended"] = True
    return options[:5]


def score_title_candidate(
    title: str,
    track: str,
    language: str,
    keyword: str,
    serp_titles: list[str],
    entity_report: dict[str, Any],
) -> dict[str, Any]:
    text = str(title or "").strip()
    lower = text.lower()
    keyword_tokens = tokenize_title(keyword)
    title_tokens = tokenize_title(text)
    max_overlap = max((lexical_overlap(text, serp) for serp in serp_titles), default=0)
    min_simhash_distance = min((simhash_distance(text, serp) for serp in serp_titles if serp), default=64)
    uniqueness = 1 if min_simhash_distance >= 10 and max_overlap <= 0.5 else 0.5 if min_simhash_distance >= 8 and max_overlap <= 0.65 else 0

    if keyword_tokens:
        keyword_hit = any(token in title_tokens or token in lower for token in keyword_tokens[:4])
    else:
        keyword_hit = True
    if track == "seo":
        first_window = "".join(text.split())[:8] if language == "zh" else " ".join(text.split()[:4]).lower()
        keyword_position = any(token in first_window.lower() for token in keyword_tokens[:3]) if keyword_tokens else True
        keyword_score = 1 if keyword_hit and keyword_position else 0.65 if keyword_hit else 0
    else:
        keyword_score = 1 if keyword_hit else 0

    length = len(text) if language == "zh" else len(text)
    if language == "zh":
        min_len, max_len = (14, 28) if track == "seo" else (16, 32)
    else:
        min_len, max_len = (50, 65) if track == "seo" else (60, 80)
    length_score = 1 if min_len <= length <= max_len else 0.7 if min_len - 3 <= length <= max_len + 3 else 0.3

    entity_names = [item.get("entity") for item in (entity_report.get("gapEntities") or []) + (entity_report.get("coveredEntities") or [])]
    matched_entities = [entity for entity in entity_names if entity and str(entity).lower() in lower]
    matched_entities.extend(re.findall(r"\d+(?:\.\d+)?", text))
    entity_count = len(set(matched_entities))
    entity_density = 1 if (entity_count >= 2 if track == "geo" else entity_count >= 1) else 0.5 if entity_count else 0.35

    starts_blacklisted = any(lower.startswith(item.lower()) for item in TITLE_GEO_BLACKLIST_STARTS.get(language, []))
    hooks = [hook for hook in TITLE_SEO_HOOKS.get(language, []) if hook.lower() in lower]
    standalone = 0.3 if track == "geo" and starts_blacklisted else 1 if entity_count >= 2 or keyword_hit else 0.6
    semantic = 1
    if track == "seo" and not hooks and not re.search(r"\d|vs|对比", lower):
        semantic = 0.75
    if track == "geo" and hooks:
        semantic = 0.7

    hard_failed = uniqueness == 0 or keyword_score == 0 or length_score < 0.5
    total = round(((uniqueness + keyword_score + semantic + length_score + entity_density + standalone) / 6) * 100)
    if hard_failed:
        total = min(total, 49)
    return {
        "total": max(1, min(99, int(total))),
        "scores": {
            "uniqueness": uniqueness,
            "keyword": keyword_score,
            "semantic": semantic,
            "length": length_score,
            "entityDensity": entity_density,
            "standalone": standalone,
        },
        "length": length,
        "entities": list(dict.fromkeys(str(entity) for entity in matched_entities if entity))[:8],
        "hooks": hooks[:6],
        "maxSerpOverlap": round(max_overlap, 3),
        "minSerpSimhashDistance": min_simhash_distance,
        "hardFailed": hard_failed,
    }


def title_prompt_system(language: str) -> str:
    base = (
        "You are an SEO + GEO title strategist. Your task is to produce TWO sets of title candidates for the same content:\n\n"
        "1. SEO TITLE SET - optimized for Google SERP click-through and ranking.\n"
        "Characteristics:\n"
        "- Noun-phrase or question form, with the main keyword in the first 8 characters (Chinese) or first 4 words (English)\n"
        "- Uses click-through hooks: specific numbers, current year, comparative words (\"vs\", \"对比\"), superlative qualifiers (\"最佳\", \"完整\", \"实测\"), or bracketed annotations\n"
        "- Length: 14-28 Chinese characters, or 50-65 English characters\n"
        "- May append brand name with \" | \" or \" - \" separator if brand_name is provided and seo_append_brand=true\n\n"
        "2. GEO TITLE SET - optimized for AI search engine citation and extraction (Perplexity, ChatGPT Search, AI Overviews, Claude).\n"
        "Characteristics:\n"
        "- Complete statement or precise question form. Self-contained: comprehensible without context\n"
        "- High entity density: at least 2 named entities or specific numerical parameters\n"
        "- No click-through hooks (\"最佳\", \"完整指南\", \"you must know\") - AI engines down-weight these\n"
        "- Length: 16-32 Chinese characters, or 60-80 English characters\n"
        "- The first content word should be a concrete noun or named entity, NOT a generic qualifier\n\n"
        "THREE ABSOLUTE RULES:\n"
        "R1. Both sets must include the main keyword or near-synonym, but the SEO set requires keyword-first position while the GEO set does not.\n"
        "R2. The two sets must differ in surface form, not just rearrange the same words.\n"
        "R3. Neither set may use a title with high lexical overlap (>50% token overlap) with SERP_TOP_TITLES.\n\n"
        "Return ONLY a JSON object. Each set contains exactly 3 candidates, ordered by confidence.\n"
        "Schema: {\"seo_candidates\":[\"...\"],\"geo_candidates\":[\"...\"],\"rationale\":{\"seo_hooks_used\":[],\"geo_entities_used\":[],\"key_differentiation_axis\":\"...\"}}"
    )
    if language == "zh":
        return base + "\nAll candidate titles must be Chinese."
    return base + "\nAll candidate titles must be English."


def fallback_title_candidates(input_data: dict[str, Any], language: str, track: str) -> list[str]:
    product = keyword_for(input_data, language)
    if language == "en":
        if track == "seo":
            return [
                f"{product} Buying Guide: 7 Specs That Matter in 2026",
                f"Best {product} Options Compared for Online Stores",
                f"{product} Review: Uses, Materials, and Buyer Fit",
            ]
        return [
            f"{product} materials, capacity, and buyer scenarios for ecommerce stores",
            f"{product} selection criteria across cafe, home, and gifting use cases",
            f"{product} specifications and tradeoffs for online product pages",
        ]
    if track == "seo":
        return [
            f"{product}选购指南：7个关键参数",
            f"{product}对比实测：适合电商推广的卖点",
            f"{product}推荐：材质、容量与场景解析",
        ]
    return [
        f"{product}材质容量与电商购买场景",
        f"{product}在咖啡店家用和礼品场景的选择标准",
        f"{product}规格差异与线上商品页可信说明",
    ]


def normalize_title_set(
    raw: Any,
    input_data: dict[str, Any],
    language: str,
    track: str,
    keyword: str,
    serp_titles: list[str],
    entity_report: dict[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw = list(raw.values())
    candidates = [str(item.get("title") if isinstance(item, dict) else item).strip() for item in (raw if isinstance(raw, list) else [])]
    candidates = [item for item in candidates if item and item.lower() != "none"]
    for fallback in fallback_title_candidates(input_data, language, track):
        if len(candidates) >= 3:
            break
        if fallback not in candidates:
            candidates.append(fallback)
    scored: list[dict[str, Any]] = []
    seen: set[str] = set()
    for title in candidates:
        if title in seen:
            continue
        seen.add(title)
        scoring = score_title_candidate(title, track, language, keyword, serp_titles, entity_report)
        scored.append(
            {
                "title": title,
                "score": scoring["total"],
                "track": track,
                "language": language,
                "reason": (
                    "SEO：关键词靠前、具备点击钩子并避开 SERP 同质化。"
                    if language == "zh" and track == "seo"
                    else "GEO：标题自洽、实体密度更高，适合 AI 引用。"
                    if language == "zh"
                    else "SEO: keyword-forward with click-through hooks and SERP differentiation."
                    if track == "seo"
                    else "GEO: self-contained, entity-dense, and easier for AI citation."
                ),
                "angle": "SEO title" if track == "seo" else "GEO title",
                "keywords": [keyword] + scoring["entities"][:5],
                "metrics": scoring,
            }
        )
    valid = [item for item in scored if not item["metrics"].get("hardFailed")]
    chosen = sorted(valid or scored, key=lambda item: -int(item.get("score") or 0))[:3]
    while len(chosen) < 3:
        fallback = fallback_title_candidates(input_data, language, track)[len(chosen) % 3]
        scoring = score_title_candidate(fallback, track, language, keyword, serp_titles, entity_report)
        chosen.append({"title": fallback, "score": scoring["total"], "track": track, "language": language, "reason": "fallback", "angle": track.upper(), "keywords": [keyword], "metrics": scoring})
    return chosen[:3]


async def generate_title_strategy_for_language(
    config: dict[str, Any],
    input_data: dict[str, Any],
    language: str,
    entity_report: dict[str, Any],
    serp_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compact_results = [
        compact_reference_title_only(item, index)
        for index, item in enumerate((input_data.get("analysisSearchResults") or input_data.get("searchResults") or [])[:40])
        if isinstance(item, dict)
    ]
    serp_titles = [str(item.get("title") or "") for item in compact_results]
    keyword = keyword_for(input_data, language)
    payload = {
        "keyword": keyword,
        "locale": "zh-CN" if language == "zh" else "en-US",
        "content_type": "ecommerce blog article",
        "audience_profile": input_data.get("targetAudience") or "",
        "SERP_TOP_TITLES": serp_titles[:15],
        "gap_entities_brief": [item.get("entity") for item in entity_report.get("gapEntities", [])[:12]],
        "PAA_questions": (serp_intelligence or {}).get("paaQuestions") or [],
        "brand_config": {"brand_name": input_data.get("productName") or "", "seo_append_brand": False},
        "length_bounds": {"seo": "14-28 zh chars or 50-65 en chars", "geo": "16-32 zh chars or 60-80 en chars"},
        "input": compact_input_brief({**input_data, "language": language}),
    }
    configured_title_prompt = config_prompts_for_language(config, language).get("title") or ""
    title_system = "\n\n".join(part for part in [configured_title_prompt.strip(), title_prompt_system(language)] if part)
    text = await call_task_model(config, "outline", build_messages(title_system, payload))
    try:
        data = extract_json(text, f"{language.upper()} title strategy")
    except HTTPException as exc:
        if exc.status_code != 502:
            raise
        data = await repair_json_response(config, "outline", language, text, f"{language.upper()} title strategy", ["seo_candidates", "geo_candidates", "rationale"])
    seo = normalize_title_set(data.get("seo_candidates"), input_data, language, "seo", keyword, serp_titles, entity_report)
    geo = normalize_title_set(data.get("geo_candidates"), input_data, language, "geo", keyword, serp_titles, entity_report)
    if seo and geo and seo[0]["title"] == geo[0]["title"] and len(geo) > 1:
        geo = [geo[1], geo[0], *geo[2:]]
    return {
        "language": language,
        "keyword": keyword,
        "seo": {"recommended": seo[0], "alternatives": seo[1:], "candidates": seo},
        "geo": {"recommended": geo[0], "alternatives": geo[1:], "candidates": geo},
        "rationale": data.get("rationale") or {},
        "strategyNote": "SEO 推荐用于 HTML title；GEO 推荐用于 H1、Schema headline 和 AI 引用锚点。",
    }


async def generate_titles(input_data: dict[str, Any]) -> dict[str, Any]:
    config = read_config(mask_key=False)
    language = active_language(input_data, config)
    search_payload: dict[str, Any] = {}
    if not (input_data.get("analysisSearchResults") or input_data.get("searchResults") or input_data.get("referencePages")):
        try:
            from backend.services.reference_search import search_references

            search_payload = await search_references(input_data)
            input_data = {
                **input_data,
                "searchResults": search_payload.get("items") or [],
                "analysisSearchResults": search_payload.get("analysisItems") or search_payload.get("items") or [],
            }
        except Exception:
            search_payload = {}
    serp_intelligence = await build_serp_intelligence(config, input_data, language)
    entity_report = serp_intelligence.get("entityReport") or build_entity_gap_report(input_data)
    enriched_input = {**input_data, "referencePages": serp_intelligence.get("referencePages") or [], "serpIntelligence": serp_intelligence}
    primary = await generate_title_strategy_for_language(config, enriched_input, language, entity_report, serp_intelligence)
    flattened: list[dict[str, Any]] = []
    for track in ("seo", "geo"):
        for index, item in enumerate(primary[track]["candidates"], start=1):
            flattened.append(
                {
                    **item,
                    "id": f"{primary['language']}-{track}-{index}",
                    "label": f"{track.upper()} / {primary['language'].upper()}",
                }
            )
    flattened.sort(key=lambda item: (item.get("language") != language, item.get("track") != "geo", -int(item.get("score") or 0)))
    recommended = primary["geo"]["recommended"]
    return {
        "language": language,
        "titles": flattened[:12],
        "recommendedTitle": recommended["title"],
        "titleStrategy": {"primary": primary, "entityReport": entity_report, "serpIntelligence": serp_intelligence},
        "entityReport": entity_report,
        "serpIntelligence": serp_intelligence,
        "searchResults": input_data.get("searchResults") or search_payload.get("items") or [],
        "analysisSearchResults": input_data.get("analysisSearchResults") or search_payload.get("analysisItems") or [],
    }


async def analyze_intents(input_data: dict[str, Any]) -> dict[str, Any]:
    config = read_config(mask_key=False)
    language = active_language(input_data, config)
    search_results = input_data.get("analysisSearchResults") or input_data.get("searchResults") or []
    compact_results = [
        compact_reference_title_only(item, index)
        for index, item in enumerate(search_results[:40])
        if isinstance(item, dict)
    ]
    system = (
        "你是电商 Blog 意图分析器。根据用户需求和搜索结果标题，归纳 3-5 个可能的写作意图/主题方向。"
        "不要读取网页全文，搜索结果只提供标题、URL 和域名，用来判断主题趋势。"
        "重点是商品推广和内容索引，不要输出“如何写 blog”这种格式型需求。"
        "每个意图要能直接指导后续大纲生成，说明用户可能想解决什么购买、比较、认知或使用场景问题。"
        "结合搜索结果时，只引用和当前商品高度相关的来源 id。"
        "只返回严格 JSON 对象，不要 markdown 代码块，不要 JSON 外文字。"
        "JSON 字段：intents。每个 intent 包含 id, title, summary, probability, recommended, keywords, referenceIds, outlineFocus。"
        if language == "zh"
        else "You are an ecommerce blog intent analyst. From the user requirements and search-result titles, infer 3-5 likely writing intents/topic directions. "
        "Do not read full pages; search results provide only title, URL, and domain as topic-trend signals. "
        "Focus on product promotion and content indexing, not format advice such as how to write a blog. "
        "Each intent must directly guide outline generation and explain the purchase, comparison, education, or use-case need. "
        "When using search results, reference only highly relevant source ids. "
        "Return a strict JSON object only, with no markdown fence and no prose outside JSON. "
        "JSON field: intents. Each intent has id, title, summary, probability, recommended, keywords, referenceIds, outlineFocus."
    )
    payload = {
        "input": compact_input_brief(input_data),
        "searchResultTitles": compact_results,
        "responseContract": {
            "format": "strict JSON object only",
            "requiredFields": ["intents"],
            "intentShape": {
                "id": "stable short id",
                "title": "topic / intent title",
                "summary": "why this intent fits the user and search results",
                "probability": "integer 1-99, spread scores clearly",
                "recommended": "boolean",
                "keywords": ["product/entity/search terms"],
                "referenceIds": ["ids from searchResults"],
                "outlineFocus": "how the next outline should be targeted",
            },
            "language": language,
        },
    }
    text = await call_task_model(config, "outline", build_messages(system, payload))
    try:
        data = extract_json(text, "Intent analysis")
    except HTTPException as exc:
        if exc.status_code != 502:
            raise
        data = await repair_json_response(config, "outline", language, text, "Intent analysis", ["intents"])
    return {
        "language": language,
        "intents": normalize_intent_options(data, input_data, language),
        "sourceCount": len(compact_results),
    }


def normalize_outline_sections(outline: dict[str, Any], input_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = outline.get("outline") or outline.get("structure") or []
    if isinstance(raw, dict):
        nested = raw.get("structure") or raw.get("sections") or raw.get("outline")
        if isinstance(nested, list):
            raw = nested
        else:
            skip_keys = {"title", "metaDescription", "meta_description", "keywords", "slug"}
            raw = [
                {"heading": key, "description": value}
                for key, value in raw.items()
                if key not in skip_keys and value
            ]
    elif not isinstance(raw, list):
        raw = [raw] if raw else []

    sections: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            heading = (
                item.get("h2")
                or item.get("H2")
                or item.get("heading")
                or item.get("title")
                or item.get("name")
                or item.get("section")
                or f"Section {index}"
            )
            sections.append(
                {
                    "heading": str(heading),
                    "detail": item,
                    "targetEntities": as_text_list(item.get("targetEntities") or item.get("entities") or item.get("entityTargets")),
                    "seoPurpose": str(item.get("seoPurpose") or item.get("seo_goal") or item.get("seo") or ""),
                    "geoPurpose": str(item.get("geoPurpose") or item.get("geo_goal") or item.get("geo") or ""),
                }
            )
        elif str(item).strip():
            sections.append({"heading": str(item).strip(), "detail": str(item).strip()})

    if sections:
        return sections[:5]

    topic = (
        outline.get("selectedTopic")
        or input_data.get("productName")
        or input_data.get("productType")
        or input_data.get("primaryKeyword")
        or "Blog"
    )
    if input_data.get("language") == "en":
        fallback = ["Opening answer", "Product value and scenarios", "Comparison and selection guide", "FAQ and final recommendation"]
    else:
        fallback = ["开篇直接回答", "产品价值与使用场景", "对比与选购建议", "FAQ 与最终推荐"]
    return [{"heading": f"{topic} - {name}", "detail": name} for name in fallback]


def clean_markdown_fragment(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    return cleaned


def title_from_strategy(input_data: dict[str, Any], language: str, track: str, fallback: str) -> str:
    strategy = input_data.get("titleStrategy") or {}
    for key in ("primary", "secondary"):
        block = strategy.get(key) or {}
        if block.get("language") != language:
            continue
        candidate = ((block.get(track) or {}).get("recommended") or {}).get("title")
        if candidate:
            return str(candidate).strip()
    selected = input_data.get("selectedTitle")
    return str(selected or fallback).strip()


def build_article_system_prompt(
    base_prompt: str,
    language: str,
    track: str,
    input_data: dict[str, Any],
    entity_report: dict[str, Any],
    mode: str = "segment",
) -> str:
    blacklist = "、".join(CONTENT_BLACKLIST.get(language, []))
    # 按规范 (SEO-GEO 模块 §3.2 / 4.2)：gap_entities 是「信息增益」主驱动，正文覆盖率必须 ≥80%；
    # covered_entities 只用作「不要复述」的反向参照，份量大幅缩小、措辞改成「仅差异化对照」。
    gap_entities = ", ".join(str(item.get("entity")) for item in entity_report.get("gapEntities", [])[:20] if item.get("entity"))
    covered_entities = ", ".join(str(item.get("entity")) for item in entity_report.get("coveredEntities", [])[:6] if item.get("entity"))
    paa_questions = " / ".join(as_text_list((input_data.get("serpIntelligence") or {}).get("paaQuestions"))[:10])
    geo_first_word_blacklist = "、".join(TITLE_GEO_BLACKLIST_STARTS.get(language, []))
    if language == "en":
        if mode == "whole":
            length_scope = (
                "OUTPUT SCOPE: write the WHOLE article in a single response. Target length 1200-2000 words total, with 3-5 H2 sections "
                "and 2-4 paragraphs per H2 (each paragraph under 120 words)."
            )
        else:
            length_scope = (
                "OUTPUT SCOPE: this call writes ONE section only (one H2 fragment), NOT the whole article. "
                "Target 250-500 words for this section, organized as 2-4 paragraphs of under 120 words each. "
                "The whole-article 1200-2000-word budget is enforced by the orchestrator across all sections — do not pack it all into this segment."
            )
        if track == "seo":
            template = (
                "━━━ SEO ARTICLE TEMPLATE ━━━\n"
                "ROLE: Senior ecommerce SEO editor targeting Google organic ranking and SERP click-through.\n"
                "DESIGN PATTERN — SEO PERSUASIVE/COMMERCIAL:\n"
                "• H1 must contain the primary keyword (already confirmed as the article title).\n"
                "• Opening paragraph: lead with a concrete number, product name, or buyer scenario — never a generic overview. "
                "Put the keyword and buyer intent in the first two sentences.\n"
                "• H2 headings: use click-worthy language with specifics (numbers, comparisons, year, brackets) — "
                "e.g. '5 Ways to…', 'X vs Y: Which Is Better?', 'The [Year] Buyer's Checklist'.\n"
                "• Body structure per H2: 2-4 tight paragraphs (under 120 words each). "
                "Include at least one comparison table if the content involves product selection. "
                "Include a FAQ section (3-5 questions) near the end with concise answers. "
                "Close with a clear buying/usage recommendation section.\n"
                "• Voice: persuasive but factual — use specific numbers, named entities, price ranges, model names. "
                "Avoid pure superlatives without evidence. Avoid generic AI-sounding phrases.\n"
                "• SERP differentiation: do NOT repeat angles already saturated by competitors (see reference below).\n"
                "[INFORMATION-GAIN — PRIMARY WRITING TARGETS]\n"
                f"Rare/gap entities (low SERP coverage, must cover ≥80%): {gap_entities}\n"
                f"PAA/user sub-questions (must address ≥80%): {paa_questions}\n"
                f"[COMPETITOR SATURATION — AVOID DUPLICATION] Already covered by top SERP pages; do NOT restate: {covered_entities}\n"
                f"Blacklist terms (must not appear anywhere): {blacklist}\n"
                f"{length_scope}\n"
                "Output Markdown only. No JSON, no commentary."
            )
        else:
            template = (
                "━━━ GEO ARTICLE TEMPLATE ━━━\n"
                "ROLE: Senior content editor writing for AI search citation and extraction "
                "(Perplexity, ChatGPT Search, Google AI Overviews, Claude).\n"
                "DESIGN PATTERN — GEO ENCYCLOPEDIC/REFERENCE:\n"
                "• Opening paragraph (LEADING QUOTABLE PARAGRAPH): must be a complete, self-contained answer "
                "to the implied query — include at least 2 named entities or specific numerical parameters, "
                "state concrete facts and conditions. This paragraph must be directly quotable by an AI engine "
                "with no surrounding context needed.\n"
                "• H2 headings: use precise, descriptive noun-phrases — never click-hooks like 'Best', 'Ultimate', 'You Must Know'. "
                "H2 should name the entity or concept being explained, e.g. 'Conical vs Flat Burr Grinder: Grind Consistency'.\n"
                "• Each H2 section: first sentence must be a self-contained factual statement (AI citation anchor). "
                "2-4 paragraphs under 120 words each. Include structured lists or tables for extraction-friendly comparisons. "
                "Include 'Suitable for / Not suitable for' guidance when applicable.\n"
                "• FAQ section: include 3-5 questions in the form precise answers (not 'it depends'), "
                "each answer self-contained and quotable.\n"
                "• Conclusion (WIKI-STYLE SUMMARY): end with 80-120 words summarizing the key facts, "
                "entities, and parameters — written in encyclopedic tone for AI extraction.\n"
                "• Voice: neutral, encyclopedic. No promotional adjectives, no first-person imperatives, "
                "no click-bait openers. Entity density must be high throughout.\n"
                "[INFORMATION-GAIN — PRIMARY WRITING TARGETS]\n"
                f"Rare/gap entities (low SERP coverage, must cover ≥80%): {gap_entities}\n"
                f"PAA/user sub-questions (must address ≥80%): {paa_questions}\n"
                f"[COMPETITOR SATURATION — AVOID DUPLICATION] Already covered by top SERP pages; do NOT restate: {covered_entities}\n"
                f"Blacklist terms (must not appear anywhere): {blacklist}\n"
                f"SELF-CONTAINMENT RULE: opening sentence and every H2 first sentence MUST NOT start with context-dependent phrases: {geo_first_word_blacklist}. "
                "Rewrite any such sentence to lead with a concrete entity, number, or scenario.\n"
                f"{length_scope}\n"
                "Output Markdown only. No JSON, no commentary."
            )
    else:
        if mode == "whole":
            length_scope = (
                "【输出范围】在一次回复内写完整篇文章。目标字数 1200-2000 字，3-5 个 H2，"
                "每个 H2 下 2-4 段，每段不超过 120 字。"
            )
        else:
            length_scope = (
                "【输出范围】本次仅写当前 H2 章节的 Markdown 片段，不是整篇文章。"
                "本段目标 250-500 字，2-4 个段落，每段不超过 120 字。"
                "整篇 1200-2000 字由后端跨章节合并后校验，本段不要试图写完整篇。"
            )
        if track == "seo":
            template = (
                "━━━ SEO 文章模板 ━━━\n"
                "角色：资深电商 SEO 内容编辑，目标是 Google 自然搜索排名和 SERP 点击率。\n"
                "设计模式 — SEO 说服式/商业化：\n"
                "• H1 必须包含核心关键词（已在文章标题中确认）。\n"
                "• 首段（开门见山型）：以具体数字、产品名或购买场景开头——禁止泛泛概述。"
                "前两句必须前置关键词和购买意图。\n"
                "• H2 标题：使用有点击吸引力的具体表达——数字、对比、年份、方括号标注，"
                "如「5 种方法…」「A vs B：哪个更好？」「[2026] 选购清单」。\n"
                "• 每个 H2 正文：2-4 段（每段不超过 120 字）。"
                "如果涉及商品选购，必须包含至少一个对比表格。"
                "文章临近结尾处包含 FAQ 小节（3-5 问），每个回答简洁有据。"
                "最后用一个购买/使用推荐段落收尾。\n"
                "• 语气：说服性但有事实支撑——使用具体数字、命名实体、价格区间、型号名称。"
                "禁止无据的最高级，禁止通用 AI 口吻。\n"
                "• SERP 差异化：禁止重复竞品已大量覆盖的角度（见下方参照）。\n"
                "【信息增益主驱动】\n"
                f"稀有/缺口实体（SERP 低覆盖率，必须覆盖 ≥80%）：{gap_entities}\n"
                f"PAA/用户子问题（必须回答 ≥80%）：{paa_questions}\n"
                f"【竞品饱和参照——不要复述】以下角度竞品已大量覆盖，只用作避免雷同：{covered_entities}\n"
                f"黑名单（全文禁止出现）：{blacklist}\n"
                f"{length_scope}\n"
                "只输出 Markdown，禁止输出 JSON 或任何解释。"
            )
        else:
            template = (
                "━━━ GEO 文章模板 ━━━\n"
                "角色：面向 AI 搜索引用与抽取的资深内容编辑（Perplexity、ChatGPT Search、"
                "Google AI Overviews、Claude 等）。\n"
                "设计模式 — GEO 百科式/参考型：\n"
                "• 首段（可引用引导段）：必须是对隐含查询的完整自含回答——"
                "包含至少 2 个命名实体或具体数值参数，陈述具体事实与适用条件。"
                "AI 引擎必须能在不依赖上下文的情况下直接引用此段。\n"
                "• H2 标题：使用精准描述性名词短语——禁止「最佳」「终极」「你必须知道」等钩子词。"
                "H2 应命名被解释的实体或概念，如「锥形与平刀磨豆机：研磨均匀度对比」。\n"
                "• 每个 H2 正文：首句必须是自含事实陈述（AI 引用锚点）。"
                "2-4 段，每段不超过 120 字。提供结构化列表或表格便于抽取。"
                "适用时加入「适用场景 / 不适用场景」指引。\n"
                "• FAQ 小节：3-5 问，每个回答精准自含（禁止「视情况而定」等模糊回答），"
                "每条 FAQ 独立可被 AI 引用。\n"
                "• 结尾（Wiki 体摘要）：80-120 字概括核心事实、实体和参数——"
                "百科全书语气，专供 AI 抽取。\n"
                "• 语气：中立、客观、百科式。禁止促销形容词、第一人称祈使句、点击诱饵式开头。"
                "全文实体密度必须高。\n"
                "【信息增益主驱动】\n"
                f"稀有/缺口实体（SERP 低覆盖率，必须覆盖 ≥80%）：{gap_entities}\n"
                f"PAA/用户子问题（必须回答 ≥80%）：{paa_questions}\n"
                f"【竞品饱和参照——不要复述】以下角度竞品已大量覆盖，只用作避免雷同：{covered_entities}\n"
                f"黑名单（全文禁止出现）：{blacklist}\n"
                f"自含性硬规则：整篇开篇句及每个 H2 首句禁止以下列上下文依赖词开头（不区分大小写）：{geo_first_word_blacklist}。"
                "如发现，请改写为以「实体/数值/场景」开头的自含陈述句。\n"
                f"{length_scope}\n"
                "只输出 Markdown，禁止输出 JSON 或任何解释。"
            )
    return "\n\n".join(part for part in [base_prompt.strip(), template] if part)


def build_outline_system_prompt(base_prompt: str, language: str, entity_report: dict[str, Any], input_data: dict[str, Any]) -> str:
    gap_entities = ", ".join(str(item.get("entity")) for item in entity_report.get("gapEntities", [])[:18] if item.get("entity"))
    # 与 build_article_system_prompt 一致：outline 阶段 covered 也按"差异化对照"角色减量。
    covered_entities = ", ".join(str(item.get("entity")) for item in entity_report.get("coveredEntities", [])[:6] if item.get("entity"))
    title_strategy = input_data.get("titleStrategy") or {}
    selected_title = str(input_data.get("selectedTitle") or "").strip()
    if language == "en":
        rules = (
            "SEO + GEO OUTLINE RULES\n"
            "You are not writing a generic outline. Build a publishable ecommerce Blog structure that uses SERP entity intelligence.\n"
            "1. Use selectedTitle as the H1 when present. Do not replace it with a generic title.\n"
            "2. Create an outline that can support TWO article variants later: SEO-friendly and GEO-friendly.\n"
            "3. SEO needs keyword-forward sections, buyer intent, product comparisons, specs, scenarios, FAQ, and source-backed trust signals.\n"
            "4. GEO needs directly quotable answers, clear entity definitions, rare entities, constraints, tables/lists, and AI-extractable summaries.\n"
            "5. At least 70% of H2/H3 headings or summaries must explicitly use rare/gap entities or entity questions when available.\n"
            "6. Covered SERP entities show what competitors already mention; rare/gap entities are information-gain opportunities and must shape the structure.\n"
            "7. Include sourceAngles for how selected references should be used as citations without copying.\n"
            "8. SECTION COUNT LIMIT: sections array must contain exactly 3-5 H2 items. Each H2 targets ~300-400 words. Total article budget is 1200-2000 words — do NOT exceed this by creating extra sections.\n"
            "9. Each H2 section must cover a DISTINCT angle. Never repeat the same point across different sections.\n"
            f"Selected H1: {selected_title or '-'}\n"
            f"Covered SERP entities: {covered_entities or '-'}\n"
            f"Rare/gap entities: {gap_entities or '-'}\n"
            f"Title strategy: {json.dumps(title_strategy, ensure_ascii=False)[:1800]}\n"
            "Return strict JSON only."
        )
    else:
        rules = (
            "SEO + GEO 大纲规则\n"
            "你不是在写普通大纲，而是在用 SERP 实体情报设计可发布的电商 Blog 结构。\n"
            "1. 如果存在 selectedTitle，必须把它作为 H1，不要换成泛泛标题。\n"
            "2. 大纲必须能支撑后续两个正文版本：SEO 友好版本和 GEO/AI 检索友好版本。\n"
            "3. SEO 需要关键词前置、购买意图、产品对比、规格参数、使用场景、FAQ、引用信任信号。\n"
            "4. GEO 需要可直接引用的答案、清晰实体定义、稀有实体、限制条件、表格/清单、便于 AI 抽取的摘要。\n"
            "5. 如果有稀有/缺口实体，至少 70% 的 H2/H3 或 summary 要显式使用这些实体或相关 entityQuestions。\n"
            "6. coveredEntities 代表竞品常见信息；gapEntities/rareEntities 代表信息增益机会，必须影响章节结构。\n"
            "7. sourceAngles 要说明参考来源如何作为引用支撑，不得复制原文。\n"
            "8. 【章节数量硬限制】sections 数组长度必须严格控制在 3-5 个 H2，每个 H2 对应约 300-400 字，整篇文章字数目标 1200-2000 字，禁止通过增加章节超出此上限。\n"
            "9. 每个 H2 章节必须覆盖不同角度，禁止在不同章节中重复相同观点或信息。\n"
            f"已确认 H1：{selected_title or '-'}\n"
            f"SERP 已覆盖实体：{covered_entities or '-'}\n"
            f"稀有/缺口实体：{gap_entities or '-'}\n"
            f"标题策略：{json.dumps(title_strategy, ensure_ascii=False)[:1800]}\n"
            "只返回严格 JSON。"
        )
    return "\n\n".join(part for part in [base_prompt.strip(), rules] if part)


async def generate_article_segmented(
    config: dict[str, Any],
    language: str,
    prompts: dict[str, str],
    input_data: dict[str, Any],
    outline: dict[str, Any],
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    track: str = "geo",
    entity_report: dict[str, Any] | None = None,
) -> str:
    track = "seo" if track == "seo" else "geo"
    entity_report = entity_report or build_entity_gap_report(input_data)
    intelligence = input_data.get("serpIntelligence") or {}
    sections = normalize_outline_sections(outline, input_data)
    fallback_title = (
        outline.get("selectedTopic")
        or first_topic_title(outline)
        or input_data.get("productName")
        or input_data.get("productType")
        or ("Untitled Blog" if language == "en" else "未命名文章")
    )
    title = title_from_strategy(input_data, language, track, str(fallback_title))
    # mode 选择：大纲段数 ≤ 2 时一次性写完整文章；段数较多时按章节分段，避免上游超时
    # 阈值可通过 input_data["forceSegmentation"] / ["forceWholeArticle"] 覆盖
    force_whole = bool(input_data.get("forceWholeArticle"))
    force_segment = bool(input_data.get("forceSegmentation"))
    article_mode = "whole" if (force_whole or (not force_segment and len(sections) <= 2)) else "segment"
    article_system = build_article_system_prompt(
        prompts.get("article", ""), language, track, input_data, entity_report, mode=article_mode
    )
    if article_mode == "whole":
        if on_progress:
            await on_progress(
                {
                    "type": "progress",
                    "stage": "article_whole",
                    "message": f"正在一次性生成 {track.upper()} {language.upper()} 整篇正文",
                    "track": track,
                    "language": language,
                    "totalSegments": 1,
                }
            )
        if language == "en":
            whole_instruction = (
                "Single-call whole-article mode. Write the ENTIRE article (H1 + all H2 sections) as one coherent Markdown response. "
                "Do not output JSON. Respect the OUTPUT SCOPE length budget above and the section ordering implied by the outline."
            )
        else:
            whole_instruction = (
                "一次性整篇生成模式。请一次性输出完整文章（H1 + 所有 H2 章节）的 Markdown，不要输出 JSON，"
                "严格遵守上面的「本次输出范围」字数约束，并按 outline 的章节顺序组织正文。"
            )
        whole_text = await call_task_model(
            config,
            "article",
            build_messages(
                f"{article_system}\n\n{whole_instruction}",
                {
                    "input": input_data,
                    "referenceContext": reference_context(input_data),
                    "outline": outline,
                    "articleTitle": title,
                    "seoGeoTrack": track,
                    "targetLanguage": language,
                    "entityReport": entity_report,
                    "serpIntelligence": intelligence,
                    "sections": sections,
                    "internalSeoStrategy": AI_EXPOSURE_NOTES.get(language, AI_EXPOSURE_NOTES["zh"]),
                },
            ),
        )
        whole_fragment = clean_markdown_fragment(whole_text)
        if whole_fragment:
            chunks: list[str] = [whole_fragment]
        else:
            chunks = []
        generated_brief: list[str] = []
        if on_progress:
            await on_progress(
                {
                    "type": "progress",
                    "stage": "article_whole_done",
                    "message": f"{track.upper()} {language.upper()} 整篇正文已生成",
                    "track": track,
                    "language": language,
                    "totalSegments": 1,
                }
            )
    else:
        chunks = []
        generated_brief = []
    for index, section in enumerate(sections, start=1):
        if article_mode == "whole":
            break
        if on_progress:
            await on_progress(
                {
                    "type": "progress",
                    "stage": "article_segment",
                    "message": f"正在生成 {track.upper()} {language.upper()} 第 {index}/{len(sections)} 段正文",
                    "segment": index,
                    "totalSegments": len(sections),
                    "sectionTitle": section.get("heading"),
                    "track": track,
                    "language": language,
                }
            )
        if language == "en":
            section_instruction = (
                "Segmented long-form generation mode. Write ONLY the current section as a Markdown fragment. "
                "Do not output JSON. Do not repeat the whole article. The first section may include the H1 title "
                "and direct opening answer; later sections should use H2/H3 headings. Keep continuity with the "
                "previous section brief and avoid generic AI-sounding filler."
            )
        else:
            section_instruction = (
                "长文分段生成模式。只写当前章节的 Markdown 片段，不要输出 JSON，不要重复整篇文章。"
                "第一段可以包含 H1 标题和首段直接答案，后续章节使用 H2/H3。"
                "结合前文摘要保持连贯，避免模板化 AI 腔。"
            )
        text = await call_task_model(
            config,
            "article",
            build_messages(
                f"{article_system}\n\n{section_instruction}",
                {
                    "input": input_data,
                    "referenceContext": reference_context(input_data),
                    "outline": outline,
                    "articleTitle": title,
                    "seoGeoTrack": track,
                    "targetLanguage": language,
                    "entityReport": entity_report,
                    "serpIntelligence": intelligence,
                    "currentSection": section,
                    "sectionIndex": index,
                    "totalSections": len(sections),
                    "previousSectionBrief": generated_brief[-4:],
                    "sectionEntityTargets": section.get("targetEntities") or section.get("entities") or [],
                    "sectionSeoPurpose": section.get("seoPurpose") or "",
                    "sectionGeoPurpose": section.get("geoPurpose") or "",
                    "internalSeoStrategy": AI_EXPOSURE_NOTES.get(language, AI_EXPOSURE_NOTES["zh"]),
                },
            ),
        )
        fragment = clean_markdown_fragment(text)
        if fragment:
            chunks.append(fragment)
            generated_brief.append(fragment[:700])
        if on_progress:
            await on_progress(
                {
                    "type": "progress",
                    "stage": "article_segment_done",
                    "message": f"{track.upper()} {language.upper()} 第 {index}/{len(sections)} 段正文已生成",
                    "segment": index,
                    "totalSegments": len(sections),
                    "sectionTitle": section.get("heading"),
                    "track": track,
                    "language": language,
                }
            )

    article = "\n\n".join(chunks).strip()
    if not article:
        raise HTTPException(status_code=502, detail="正文生成模型没有返回有效内容。")
    if not re.search(r"^#\s+", article, flags=re.MULTILINE):
        article = f"# {title}\n\n{article}"
    article = ensure_reference_section(article, input_data, language)
    return article.strip() + "\n"


async def translate_article_variant(
    config: dict[str, Any],
    source_article: str,
    source_language: str,
    target_language: str,
    track: str,
    input_data: dict[str, Any],
) -> str:
    system = (
        "You translate and localize ecommerce blog Markdown while preserving SEO/GEO intent. "
        "Keep Markdown structure, links, source citations, tables, and factual constraints. "
        "Do not add commentary. Output only the translated Markdown."
        if target_language == "en"
        else "你负责翻译并本地化电商 Blog Markdown，同时保留 SEO/GEO 写作意图。"
        "保留 Markdown 结构、链接、参考来源、表格和事实限制。不要解释，只输出翻译后的 Markdown。"
    )
    text = await call_task_model(
        config,
        "article",
        build_messages(
            system,
            {
                "track": track,
                "sourceLanguage": source_language,
                "targetLanguage": target_language,
                "input": compact_input_brief({**input_data, "language": target_language}),
                "article": source_article,
            },
        ),
    )
    translated = clean_markdown_fragment(text)
    if not translated:
        raise HTTPException(status_code=502, detail="翻译模型没有返回有效内容。")
    return translated.strip() + "\n"


def combine_seo_geo_articles(variants: dict[str, Any], language: str) -> str:
    labels = {
        "zh": {
            "bundle": "SEO/GEO 双版本交付稿",
            "seoPrimary": "SEO 友好版本",
            "geoPrimary": "GEO 友好版本",
        },
        "en": {
            "bundle": "SEO/GEO Dual-Version Delivery",
            "seoPrimary": "SEO-Friendly Version",
            "geoPrimary": "GEO-Friendly Version",
        },
    }[language]
    data = variants.get("variants") or {}
    seo_body = (data.get("seo") or {}).get("primary", "").strip()
    geo_body = (data.get("geo") or {}).get("primary", "").strip()
    parts = [f"# {labels['bundle']}"]
    # 单 track 模式下空段只放标题反而碍眼，过滤掉
    if seo_body:
        parts.append(f"\n## {labels['seoPrimary']} ({language.upper()})\n\n{seo_body}")
    if geo_body:
        parts.append(f"\n## {labels['geoPrimary']} ({language.upper()})\n\n{geo_body}")
    return "\n\n---\n\n".join(part for part in parts if part.strip()).strip() + "\n"


def normalize_seo_geo_preference(input_data: dict[str, Any]) -> str:
    raw = str(
        input_data.get("seoGeoPreference")
        or input_data.get("contentPreference")
        or input_data.get("generationPreference")
        or ""
    ).strip().lower()
    if raw in {"seo", "seo_first", "seo-priority"}:
        return "seo"
    if raw in {"both", "dual", "seo_geo", "seo+geo", "all"}:
        return "both"
    return "geo"


def article_from_seo_geo_variants(variants: dict[str, Any], language: str, preference: str) -> str:
    preference = "both" if preference == "both" else "seo" if preference == "seo" else "geo"
    data = variants.get("variants") or {}
    if preference == "both":
        return variants.get("combinedArticle") or combine_seo_geo_articles(variants, language)
    selected = ((data.get(preference) or {}).get("primary") or "").strip()
    if selected:
        return selected + "\n"
    other = "geo" if preference == "seo" else "seo"
    fallback = ((data.get(other) or {}).get("primary") or "").strip()
    if fallback:
        return fallback + "\n"
    return variants.get("combinedArticle") or ""


async def generate_seo_geo_article_variants(
    config: dict[str, Any],
    language: str,
    prompts: dict[str, str],
    input_data: dict[str, Any],
    outline: dict[str, Any],
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    serp_intelligence = await build_serp_intelligence(config, input_data, language)
    entity_report = serp_intelligence.get("entityReport") or build_entity_gap_report(input_data)
    enriched_input = {**input_data, "referencePages": serp_intelligence.get("referencePages") or [], "serpIntelligence": serp_intelligence, "entityReport": entity_report}
    # 按用户偏好决定要生成的 track 集合：preference=seo 只生成 SEO，=geo 只生成 GEO，=both 才两条都生成
    # 这能直接砍掉一半正文生成调用（~$0.13/篇），但 combinedArticle 字段在单 track 时只含已生成那份
    preference = normalize_seo_geo_preference(input_data)
    tracks_to_run: tuple[str, ...] = ("seo", "geo") if preference == "both" else (preference,)
    variants: dict[str, Any] = {
        "primaryLanguage": language,
        "entityReport": entity_report,
        "serpIntelligence": serp_intelligence,
        "variants": {"seo": {}, "geo": {}},
        "qualityReports": {},
        "schemas": {},
        "preference": preference,
        "generatedTracks": list(tracks_to_run),
    }

    async def _run_track(track: str) -> None:
        """生成单个 track（SEO 或 GEO）并写回 variants 字典。
        两条 track 通过 asyncio.gather 并行执行，互不阻塞。
        """
        if on_progress:
            await on_progress({"type": "progress", "stage": f"{track}_article", "message": f"开始生成 {track.upper()} 主语言版本", "track": track, "language": language})
        primary = await generate_article_segmented(config, language, prompts, enriched_input, outline, on_progress, track=track, entity_report=entity_report)
        primary, quality_report = await enforce_article_quality(config, primary, language, enriched_input, serp_intelligence.get("referencePages") or [])
        schema = build_json_ld_schema(primary, {**enriched_input, "entityReport": entity_report}, language, track)
        schema_validation = validate_json_ld_schema(schema)
        if not schema_validation["ok"]:
            raise HTTPException(status_code=502, detail=f"{track.upper()} Schema 本地校验失败：{'; '.join(schema_validation['errors'])}")
        primary_with_schema = append_schema_block(primary, schema)
        # asyncio 单线程，字典写入无竞争条件
        variants["variants"][track] = {
            "primary": primary_with_schema,
            "primaryTitle": markdown_title(primary, title_from_strategy(enriched_input, language, track, "")),
            "schema": schema,
            "schemaValidation": schema_validation,
        }
        variants["qualityReports"][track] = {"primary": quality_report}
        variants["schemas"][track] = schema

    # preference="both" 时 SEO 和 GEO 并行生成，总时长 = max(SEO, GEO) 而非二者之和
    await asyncio.gather(*[_run_track(t) for t in tracks_to_run])

    variants["combinedArticle"] = combine_seo_geo_articles(variants, language)
    return variants


def ensure_reference_section(article: str, input_data: dict[str, Any], language: str) -> str:
    refs = input_data.get("selectedCitationReferences") or input_data.get("citationReferences") or []
    if not isinstance(refs, list) or not refs:
        return article
    heading_pattern = r"^##\s+(参考来源|References|Sources)\s*$"
    if re.search(heading_pattern, article, flags=re.IGNORECASE | re.MULTILINE):
        return article
    heading = "## Sources" if language == "en" else "## 参考来源"
    lines = [heading]
    seen: set[str] = set()
    for index, ref in enumerate(refs[:12], start=1):
        if not isinstance(ref, dict):
            continue
        url = str(ref.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        title = str(ref.get("title") or ref.get("domain") or f"Source {index}").strip()
        domain = str(ref.get("domain") or "").strip()
        label = f"{title} - {domain}" if domain and domain not in title else title
        lines.append(f"{index}. [{label}]({url})")
    if len(lines) == 1:
        return article
    return article.rstrip() + "\n\n" + "\n".join(lines) + "\n"


def split_markdown_sections(article: str, max_chars: int = 3600) -> list[str]:
    text = str(article or "").strip()
    if not text:
        return []
    parts: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^##\s+", line) and current:
            parts.append("\n".join(current).strip())
            current = []
        current.append(line)
    if current:
        parts.append("\n".join(current).strip())

    split_parts: list[str] = []
    for part in parts or [text]:
        if len(part) <= max_chars:
            split_parts.append(part)
            continue
        paragraphs = re.split(r"\n\s*\n", part)
        chunk = ""
        for paragraph in paragraphs:
            candidate = f"{chunk}\n\n{paragraph}".strip() if chunk else paragraph.strip()
            if len(candidate) > max_chars and chunk:
                split_parts.append(chunk.strip())
                chunk = paragraph.strip()
            else:
                chunk = candidate
        if chunk:
            split_parts.append(chunk.strip())
    return [part for part in split_parts if part]


def blacklist_hits(article: str, language: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for term in CONTENT_BLACKLIST.get(language, []):
        if not term:
            continue
        for match in re.finditer(re.escape(term), article, flags=re.IGNORECASE):
            start = max(0, match.start() - 90)
            end = min(len(article), match.end() + 90)
            hits.append({"term": term, "context": article[start:end]})
    return hits[:30]


def serp_near_duplicate_segments(article: str, reference_pages: list[dict[str, Any]], threshold: int = 8) -> list[dict[str, Any]]:
    ref_chunks: list[dict[str, str]] = []
    for page in reference_pages[:10]:
        content = str(page.get("content") or page.get("snippet") or "")
        for chunk in split_markdown_sections(content, max_chars=1200):
            if len(chunk) >= 120:
                ref_chunks.append({"title": str(page.get("title") or ""), "url": str(page.get("url") or ""), "text": chunk[:1400]})
    duplicates: list[dict[str, Any]] = []
    for index, segment in enumerate(split_markdown_sections(article, max_chars=1600), start=1):
        if len(segment) < 120:
            continue
        distances = [
            (simhash_distance(segment, ref["text"]), ref)
            for ref in ref_chunks
        ]
        if not distances:
            continue
        distance, ref = min(distances, key=lambda item: item[0])
        if distance < threshold:
            duplicates.append({"segmentIndex": index, "distance": distance, "segment": segment[:1800], "sourceTitle": ref["title"], "sourceUrl": ref["url"]})
    return duplicates[:12]


async def rewrite_quality_issues(
    config: dict[str, Any],
    article: str,
    language: str,
    input_data: dict[str, Any],
    issue_payload: dict[str, Any],
) -> str:
    if not issue_payload.get("blacklistHits") and not issue_payload.get("nearDuplicates"):
        return article
    system = (
        "你是内容质量后处理编辑。根据检测结果改写 Markdown 文章，必须保留事实、标题层级、链接和引用来源。"
        "目标：删除所有反低熵黑名单表达；对接近 SERP 来源的段落重新表达并加入用户独有信息或更具体场景。"
        "不要输出解释，不要返回 JSON，只输出完整 Markdown。"
        if language == "zh"
        else "You are a content quality post-editor. Rewrite the full Markdown article using the detected issues. "
        "Preserve facts, heading hierarchy, links, and sources. Remove all low-entropy blacklist phrases and rewrite SERP-near-duplicate segments with more specific scenarios or unique user information. "
        "Return the full Markdown only, no commentary and no JSON."
    )
    text = await call_task_model(
        config,
        "revision",
        build_messages(
            system,
            {
                "input": compact_input_brief(input_data),
                "issues": issue_payload,
                "article": article,
            },
        ),
    )
    revised = clean_markdown_fragment(text)
    return revised.strip() + "\n" if revised else article


async def enforce_article_quality(
    config: dict[str, Any],
    article: str,
    language: str,
    input_data: dict[str, Any],
    reference_pages: list[dict[str, Any]],
    max_passes: int = 2,
) -> tuple[str, dict[str, Any]]:
    current = article
    passes: list[dict[str, Any]] = []
    initial_blacklist = blacklist_hits(current, language)
    initial_duplicates = serp_near_duplicate_segments(current, reference_pages)
    for pass_index in range(max(1, max_passes)):
        hits = blacklist_hits(current, language)
        duplicates = serp_near_duplicate_segments(current, reference_pages)
        passes.append({"pass": pass_index + 1, "blacklistHits": hits, "nearDuplicates": duplicates})
        if not hits and not duplicates:
            break
        current = await rewrite_quality_issues(
            config,
            current,
            language,
            input_data,
            {"blacklistHits": hits, "nearDuplicates": duplicates},
        )
    final_blacklist = blacklist_hits(current, language)
    final_duplicates = serp_near_duplicate_segments(current, reference_pages)
    report = {
        "blacklistHitsBefore": initial_blacklist,
        "nearDuplicatesBefore": initial_duplicates,
        "blacklistHitsAfter": final_blacklist,
        "nearDuplicatesAfter": final_duplicates,
        "passes": passes,
        "passed": not final_blacklist and not final_duplicates,
    }
    if not report["passed"]:
        raise HTTPException(
            status_code=502,
            detail=(
                "正文质量后处理未通过：仍存在反低熵词或 SERP 近重复段落。"
                if language == "zh"
                else "Article quality post-processing failed: blacklist terms or SERP-near-duplicate segments remain."
            ),
        )
    return current, report


def article_summary(article: str, max_chars: int = 260) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", article)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", lambda m: re.sub(r"[\[\]\(\)]", "", m.group(0)).split("http")[0], text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def extract_faq_schema(article: str) -> list[dict[str, Any]]:
    faq_items: list[dict[str, Any]] = []
    lines = article.splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^#{2,4}\s+(.+\?)\s*$", line.strip())
        if not heading:
            continue
        answer_parts: list[str] = []
        for next_line in lines[index + 1 :]:
            if re.match(r"^#{1,4}\s+", next_line):
                break
            if next_line.strip():
                answer_parts.append(next_line.strip())
            if len(" ".join(answer_parts)) > 500:
                break
        answer = re.sub(r"[*_`>#-]", "", " ".join(answer_parts)).strip()
        if answer:
            faq_items.append({"@type": "Question", "name": heading.group(1).strip(), "acceptedAnswer": {"@type": "Answer", "text": answer[:900]}})
    return faq_items[:8]


def build_json_ld_schema(article: str, input_data: dict[str, Any], language: str, track: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).date().isoformat()
    title = markdown_title(article, str(input_data.get("selectedTitle") or input_data.get("productName") or "Blog Article"))
    author = str(input_data.get("author") or input_data.get("tenantName") or input_data.get("brand") or input_data.get("scenarioName") or "Editorial Team").strip()
    url = str(input_data.get("pageUrl") or input_data.get("canonicalUrl") or "").strip()
    article_schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],
        "description": article_summary(article, 300),
        "inLanguage": "en" if language == "en" else "zh-CN",
        "datePublished": now,
        "dateModified": now,
        "author": {"@type": "Person", "name": author},
        "publisher": {"@type": "Organization", "name": author},
        "articleBody": article_summary(article, 4500),
        "about": [item.get("entity") for item in (input_data.get("entityReport") or {}).get("gapEntities", [])[:8] if item.get("entity")],
        "keywords": as_text_list(input_data.get("keywords"))[:12],
    }
    if url:
        article_schema["mainEntityOfPage"] = {"@type": "WebPage", "@id": url}
    faq_items = extract_faq_schema(article)
    if faq_items:
        return {"@context": "https://schema.org", "@graph": [article_schema, {"@type": "FAQPage", "mainEntity": faq_items}]}
    return article_schema


def validate_json_ld_schema(schema: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    graph = schema.get("@graph") if isinstance(schema, dict) else None
    article = next((item for item in graph if isinstance(item, dict) and item.get("@type") == "Article"), None) if isinstance(graph, list) else schema
    if not isinstance(article, dict):
        errors.append("missing Article schema")
        return {"ok": False, "errors": errors, "warnings": warnings}
    required = ["@context", "@type", "headline", "author", "datePublished", "articleBody"]
    for field in required:
        if not article.get(field) and not schema.get(field):
            errors.append(f"missing {field}")
    if article.get("@type") not in {"Article", "BlogPosting", "NewsArticle"}:
        errors.append("schema @type must be Article-compatible")
    if len(str(article.get("headline") or "")) > 110:
        warnings.append("headline is longer than Google's common display limit")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def append_schema_block(article: str, schema: dict[str, Any]) -> str:
    block = json.dumps(schema, ensure_ascii=False, indent=2)
    return article.rstrip() + "\n\n## JSON-LD Schema\n\n```json\n" + block + "\n```\n"


async def revise_article_segmented(
    config: dict[str, Any],
    language: str,
    payload: dict[str, Any],
    label: str,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    round_index: int = 0,
    total_rounds: int = 0,
) -> dict[str, Any]:
    article = str(payload.get("article") or "").strip()
    sections = split_markdown_sections(article)
    if not sections:
        raise HTTPException(status_code=400, detail="没有可迭代的正文内容。")

    revised_parts: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    summaries: list[str] = []
    changed_focus: list[str] = []
    article_title = markdown_title(article, str((payload.get("outline") or {}).get("selectedTopic") or "Untitled Blog"))
    for index, section in enumerate(sections, start=1):
        if on_progress:
            await on_progress(
                {
                    "type": "progress",
                    "stage": "modify_segment",
                    "message": f"修改 AI 正在处理第 {index}/{len(sections)} 段",
                    "round": round_index,
                    "totalRounds": total_rounds,
                    "segment": index,
                    "totalSegments": len(sections),
                }
            )
        if language == "en":
            instruction = (
                "Revise only this article segment. Return STRICT JSON only. revisedArticle must contain only the revised "
                "Markdown segment, not the full article. Keep headings coherent with the full article."
            )
        else:
            instruction = (
                "只改写当前文章片段。只返回严格 JSON。revisedArticle 只放当前片段改写后的 Markdown，"
                "不要返回完整文章。保留与全文一致的标题层级。"
            )
        segment_payload = {
            **payload,
            "article": section,
            "fullArticleTitle": article_title,
            "segmentIndex": index,
            "totalSegments": len(sections),
            "segmentInstruction": instruction,
        }
        revision_text = await call_task_model(
            config,
            "revision",
            build_messages(
                REVISION_SYSTEM_PROMPTS.get(language, REVISION_SYSTEM_PROMPTS["zh"]),
                segment_payload,
            ),
        )
        modification = await revise_article_with_repair(
            config,
            language,
            segment_payload,
            revision_text,
            f"{label} segment {index}",
        )
        revised = modification.get("revisedArticle") or modification.get("article") or modification.get("updatedArticle") or section
        if isinstance(revised, list):
            revised = "\n".join(str(item) for item in revised)
        revised = str(revised)
        # 兜底：若 revisedArticle 本身是一个 JSON 对象字符串（模型把整个 JSON 放进了该字段），
        # 尝试再解析一层，提取真正的 Markdown 内容。
        stripped_revised = revised.strip()
        if stripped_revised.startswith("{") and "revisedArticle" in stripped_revised:
            try:
                inner = json.loads(stripped_revised)
                if isinstance(inner, dict):
                    inner_article = inner.get("revisedArticle") or inner.get("article") or inner.get("updatedArticle")
                    if inner_article and isinstance(inner_article, str) and inner_article.strip():
                        revised = inner_article
            except (json.JSONDecodeError, ValueError):
                pass
        revised_parts.append(clean_markdown_fragment(revised))
        added.extend(as_text_list(modification.get("added"))[:6])
        removed.extend(as_text_list(modification.get("removed"))[:6])
        summaries.extend(as_text_list(modification.get("changeSummary"))[:2])
        changed_focus.extend(as_text_list(modification.get("changedFocus"))[:2])
        if on_progress:
            await on_progress(
                {
                    "type": "progress",
                    "stage": "modify_segment_done",
                    "message": f"第 {index}/{len(sections)} 段已完成",
                    "round": round_index,
                    "totalRounds": total_rounds,
                    "segment": index,
                    "totalSegments": len(sections),
                }
            )

    revised_article = "\n\n".join(part for part in revised_parts if part).strip()
    if not revised_article:
        raise HTTPException(status_code=502, detail="修改 AI 没有返回可用正文。")
    if re.search(r"updatedPrompt|promptPatch|systemPrompt", revised_article, flags=re.IGNORECASE):
        raise HTTPException(status_code=502, detail="修改 AI 返回了 prompt 内容，而不是正文。请检查内容修改模型。")
    return {
        "revisedArticle": revised_article + "\n",
        "changeSummary": "；".join(summaries[:8]) or ("已按章节完成内容优化。" if language == "zh" else "Segmented content revision completed."),
        "added": added[:20],
        "removed": removed[:20],
        "changedFocus": "；".join(changed_focus[:8]),
        "segments": len(sections),
    }


async def build_outline(input_data: dict[str, Any]) -> dict[str, Any]:
    config = read_config(mask_key=False)
    language = active_language(input_data, config)
    prompts = prompts_for(input_data, config)
    serp_intelligence = await build_serp_intelligence(config, input_data, language)
    entity_report = serp_intelligence.get("entityReport") or build_entity_gap_report(input_data)
    outline_system = build_outline_system_prompt(prompts["outline"], language, entity_report, input_data)
    text = await call_task_model(
        config,
        "outline",
        build_messages(
            outline_system,
            {
                "input": input_data,
                "selectedIntent": input_data.get("selectedIntent") or {},
                "selectedTitle": input_data.get("selectedTitle") or "",
                "titleStrategy": input_data.get("titleStrategy") or {},
                "entityReport": entity_report,
                "serpIntelligence": {
                    "entityReport": entity_report,
                    "paaQuestions": serp_intelligence.get("paaQuestions") or [],
                    "referencePages": [
                        {
                            "id": page.get("id"),
                            "title": page.get("title"),
                            "url": page.get("url"),
                            "domain": page.get("domain"),
                            "fetchStatus": page.get("fetchStatus"),
                            "contentPreview": str(page.get("content") or "")[:1200],
                        }
                        for page in (serp_intelligence.get("referencePages") or [])[:10]
                    ],
                },
                "entityInstruction": (
                    "大纲必须优先覆盖 entityReport.gapEntities 中覆盖率低的稀有实体；这些实体越少被 SERP 结果提到，越应该作为信息增益来源。"
                    if language == "zh"
                    else "Prioritize low-coverage rare entities from entityReport.gapEntities; fewer SERP mentions mean stronger information-gain opportunities."
                ),
                "intentInstruction": (
                    "必须围绕 selectedIntent 和 selectedTitle 生成大纲；selectedTitle 是用户确认或手动修改后的 H1 标题。"
                    if language == "zh"
                    else "Generate the outline around selectedIntent and selectedTitle. selectedTitle is the user-approved or manually edited H1 title."
                ),
                "referenceContext": reference_context(input_data),
                "responseContract": {
                    "format": "strict JSON object only; no markdown fence; no explanation outside JSON",
                    "requiredFields": [
                        "topics",
                        "selectedTopic",
                        "searchIntent",
                        "audience",
                        "outline",
                        "entityQuestions",
                        "sourceAngles",
                        "aiExposureNotes",
                    ],
                    "outlineShape": {
                        "title": "string, H1 article title",
                        "sections": [
                            {
                                "h2": "string, primary section heading",
                                "summary": "string, short writing direction that names the SEO/GEO purpose and target entities",
                                "h3": ["string, subsection heading"],
                                "targetEntities": ["rare/gap/covered entities used by this section"],
                                "seoPurpose": "buyer/search ranking role of this section",
                                "geoPurpose": "AI citation/extraction role of this section",
                            }
                        ],
                    },
                    "language": language,
                },
            },
        ),
    )
    try:
        outline = extract_json(text, "Outline")
    except HTTPException as exc:
        if exc.status_code != 502:
            raise
        outline = await repair_json_response(
            config,
            "outline",
            language,
            text,
            "Outline",
            ["topics", "selectedTopic", "searchIntent", "audience", "outline", "entityQuestions", "sourceAngles", "aiExposureNotes"],
        )
    outline["language"] = language
    outline["entityReport"] = entity_report
    outline["serpIntelligence"] = serp_intelligence
    return outline


async def generate_blog(input_data: dict[str, Any]) -> dict[str, Any]:
    config = read_config(mask_key=False)
    language = active_language(input_data, config)
    prompts = prompts_for(input_data, config)
    outline = input_data.get("outline") or await build_outline(input_data)

    seo_geo_variants = await generate_seo_geo_article_variants(config, language, prompts, input_data, outline)
    preference = normalize_seo_geo_preference(input_data)
    article = article_from_seo_geo_variants(seo_geo_variants, language, preference)
    article = insert_images_contextually(article, input_data.get("images") or [], language)

    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    title_match = re.search(r"^#\s+(.+)$", article, flags=re.MULTILINE)
    title = (
        title_match.group(1).strip()
        if title_match
        else input_data.get("selectedTitle")
        or outline.get("selectedTopic")
        or first_topic_title(outline)
        or input_data.get("productName")
        or "Untitled Blog"
    )
    blog = {
        "id": str(uuid.uuid4()),
        "title": title,
        "createdAt": created_at,
        "updatedAt": created_at,
        "input": input_data,
        "plan": outline,
        "article": article,
        "seoGeoVariants": seo_geo_variants,
        "seoGeoPreference": preference,
        "evaluation": {},
        "rounds": [],
        "language": language,
    }
    blog["groupId"] = blog["id"]
    blog["groupName"] = title
    blog["versionIndex"] = 1
    blog["versionLabel"] = "初始版本"
    return save_blog(blog)


async def _auto_score_article(
    config: dict[str, Any],
    article: str,
    input_data: dict[str, Any],
    language: str,
    prompts: dict[str, str],
    eeat_rules: dict[str, Any],
) -> dict[str, Any]:
    """对一篇文章做一次 E-E-A-T 评分（含 GPTZero），返回 merged evaluation。"""
    rule_eval = evaluate_eeat_rules(article, input_data, eeat_rules)
    evaluation_text = await call_task_model(
        config,
        "evaluator",
        build_messages(
            prompts.get("optimizer") or prompts.get("training_evaluator") or "",
            {
                "article": article,
                "language": language,
                "eeatScoringRules": {
                    "scoreValues": eeat_rules.get("scoreValues"),
                    "quadrantFormula": eeat_rules.get("quadrantFormula"),
                    "defaultWeights": eeat_rules.get("defaultWeights"),
                    "contentTypeWeights": eeat_rules.get("contentTypeWeights"),
                    "blockerIds": eeat_rules.get("blockerIds"),
                    "items": eeat_rules_for_prompt(eeat_rules, rule_eval),
                },
                "deterministicRuleEvaluation": rule_eval,
                "instruction": (
                    "只评分，不改文章。逐项打分 60 项 E-E-A-T 指标，每项 0/0.5/1，返回 itemScores 和 contentType。"
                    if language == "zh"
                    else "Score only. Do not rewrite. Score all 60 E-E-A-T items (0, 0.5, or 1). Return itemScores and contentType."
                ),
            },
        ),
    )
    raw_eval = extract_json(evaluation_text, "auto-iter evaluator")
    raw_eval = apply_rule_scores(raw_eval, rule_eval)
    eeat_report = calculate_eeat_report(raw_eval, eeat_rules, str(raw_eval.get("contentType") or ""))
    model_eval = {
        **raw_eval,
        **eeat_report,
        "score": eeat_report["score"],
        "revisionAdvice": eeat_report["revisionAdvice"] or as_text_list(raw_eval.get("revisionAdvice")),
        "eeatReport": eeat_report,
    }
    gptzero_eval = await call_gptzero_score(config, article, language)
    return merge_evaluation_scores(model_eval, gptzero_eval, language, config)


async def generate_blog_events(input_data: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    progress_events: list[dict[str, Any]] = []

    async def queue_progress(event: dict[str, Any]) -> None:
        progress_events.append(event)

    try:
        config = read_config(mask_key=False)
        language = active_language(input_data, config)
        prompts = prompts_for(input_data, config)
        yield {"type": "progress", "stage": "outline", "message": "正在准备大纲", "percent": 8}
        outline = input_data.get("outline") or await build_outline(input_data)
        preference = normalize_seo_geo_preference(input_data)
        yield {"type": "progress", "stage": "outline_done", "message": "大纲已确认，开始生成 SEO/GEO 正文候选", "percent": 18}
        variants_task = asyncio.create_task(generate_seo_geo_article_variants(config, language, prompts, input_data, outline, queue_progress))
        while not variants_task.done():
            while progress_events:
                yield progress_events.pop(0)
            await asyncio.sleep(0.2)
        seo_geo_variants = await variants_task
        while progress_events:
            yield progress_events.pop(0)
        article = article_from_seo_geo_variants(seo_geo_variants, language, preference)
        article = insert_images_contextually(article, input_data.get("images") or [], language)

        # ── 自动一轮迭代：评分 → 修改 → 再评分 → 选最优 ────────────────────────
        eeat_rules = load_eeat_rules()
        auto_iter_rounds: list[dict[str, Any]] = []
        final_article = article
        final_evaluation: dict[str, Any] = {}
        version_label = "初始版本" if language == "zh" else "Initial Version"

        try:
            yield {"type": "progress", "stage": "auto_iter_score0", "message": "自动迭代：对初始正文评分中…", "percent": 60}
            eval_v0 = await _auto_score_article(config, article, input_data, language, prompts, eeat_rules)
            score_v0 = float(eval_v0.get("score") or 0)
            yield {
                "type": "progress",
                "stage": "auto_iter_revise",
                "message": f"自动迭代：初始得分 {score_v0:.1f}，正在根据建议优化正文…",
                "percent": 70,
                "score": score_v0,
            }

            revision_payload = {
                "input": iteration_model_input(input_data),
                "outline": outline,
                "article": article,
                "referenceContext": reference_context(input_data),
                "evaluation": eval_v0,
                "humanFeedback": "",
                "trainingGoal": (
                    "提升 E-E-A-T 综合得分：改善真人感、引用密度、实体覆盖和结构清晰度。"
                    if language == "zh"
                    else "Improve E-E-A-T score: enhance authenticity, citation density, entity coverage, and structure clarity."
                ),
            }
            modify_events: list[dict[str, Any]] = []

            async def queue_modify(event: dict[str, Any]) -> None:
                modify_events.append(event)

            revision_task = asyncio.create_task(
                revise_article_segmented(config, language, revision_payload, "auto-iter revision", queue_modify, 1, 1)
            )
            while not revision_task.done():
                while modify_events:
                    yield modify_events.pop(0)
                await asyncio.sleep(0.2)
            modification = await revision_task
            while modify_events:
                yield modify_events.pop(0)

            article_v1 = modification.get("revisedArticle") or modification.get("article") or article
            if isinstance(article_v1, list):
                article_v1 = "\n".join(str(item) for item in article_v1)
            article_v1 = str(article_v1).strip() or article

            yield {"type": "progress", "stage": "auto_iter_score1", "message": "自动迭代：对优化版本重新评分…", "percent": 85}
            eval_v1 = await _auto_score_article(config, article_v1, input_data, language, prompts, eeat_rules)
            score_v1 = float(eval_v1.get("score") or 0)

            auto_iter_rounds = [
                {
                    "round": 0,
                    "label": "初始版本" if language == "zh" else "Initial",
                    "article": article,
                    "score": score_v0,
                    "evaluation": eval_v0,
                },
                {
                    "round": 1,
                    "label": "自动迭代版" if language == "zh" else "Auto-Iterated",
                    "article": article_v1,
                    "score": score_v1,
                    "evaluation": eval_v1,
                    "modification": modification,
                },
            ]

            if score_v1 >= score_v0:
                final_article = article_v1
                final_evaluation = eval_v1
                version_label = (
                    f"自动迭代版（{score_v1:.1f} 分 > 初始 {score_v0:.1f} 分）"
                    if language == "zh"
                    else f"Auto-Iterated ({score_v1:.1f} > initial {score_v0:.1f})"
                )
            else:
                final_article = article
                final_evaluation = eval_v0
                version_label = (
                    f"初始版本（{score_v0:.1f} 分优于迭代 {score_v1:.1f} 分）"
                    if language == "zh"
                    else f"Initial Version ({score_v0:.1f} vs iterated {score_v1:.1f})"
                )
            yield {
                "type": "progress",
                "stage": "auto_iter_done",
                "message": f"自动迭代完成，选用：{version_label}",
                "percent": 95,
                "score": max(score_v0, score_v1),
                "scoreV0": score_v0,
                "scoreV1": score_v1,
            }

        except HTTPException:
            # 评分/修改模型未配置或出错，跳过自动迭代直接保存初始版本
            yield {
                "type": "progress",
                "stage": "auto_iter_skipped",
                "message": "自动迭代跳过（评分或修改模型未配置），已保存初始版本",
                "percent": 90,
            }
        except Exception as iter_exc:
            yield {
                "type": "progress",
                "stage": "auto_iter_skipped",
                "message": f"自动迭代遇到错误，已保存初始版本：{iter_exc}",
                "percent": 90,
            }

        # ── 保存最终结果 ──────────────────────────────────────────────────────────
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        title = markdown_title(
            final_article,
            str(input_data.get("selectedTitle") or outline.get("selectedTopic") or first_topic_title(outline) or input_data.get("productName") or "Untitled Blog"),
        )
        blog = {
            "id": str(uuid.uuid4()),
            "title": title,
            "createdAt": created_at,
            "updatedAt": created_at,
            "input": input_data,
            "plan": outline,
            "article": final_article,
            "seoGeoVariants": seo_geo_variants,
            "seoGeoPreference": preference,
            "evaluation": final_evaluation,
            "rounds": auto_iter_rounds,
            "language": language,
        }
        blog["groupId"] = blog["id"]
        blog["groupName"] = title
        blog["versionIndex"] = 1
        blog["versionLabel"] = version_label
        saved = save_blog(blog)
        yield {"type": "result", "stage": "done", "message": "正文已生成", "blog": saved}
    except HTTPException as exc:
        yield {"type": "error", "stage": "error", "message": exc.detail, "statusCode": exc.status_code}
    except Exception as exc:
        yield {"type": "error", "stage": "error", "message": f"正文生成失败：{exc}"}


def numeric_score(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
        return float(match.group(0)) if match else default


async def call_gptzero_score(config: dict[str, Any], article: str, language: str) -> dict[str, Any]:
    """Call GPTZero /v2/predict/text and return human-likeness score + sentence-level advice.

    Response fields used:
      documents[0].completely_generated_prob  – overall AI probability (0-1)
      documents[0].predicted_class            – "ai" | "human" | "mixed"
      documents[0].confidence_category        – "high" | "medium" | "low"
      documents[0].result_message             – human-readable verdict
      documents[0].document_classification    – "AI_ONLY" | "HUMAN_ONLY" | "MIXED"
      documents[0].sentences[].generated_prob – per-sentence AI probability (0-1)
      documents[0].sentences[].sentence       – sentence text
      documents[0].sentences[].highlight_sentence_for_ai – boolean flag
    """
    settings = config.get("gptZeroSettings") or {}
    if language != "en":
        return {"enabled": False, "skipped": "GPTZero is only used for English content."}
    if not settings.get("enabled"):
        return {"enabled": False, "skipped": "GPTZero is not enabled."}
    endpoint = str(settings.get("endpoint") or "").strip()
    api_key = str(settings.get("apiKey") or "").strip()
    if not endpoint or not api_key:
        return {"enabled": False, "skipped": "GPTZero endpoint or API key is not configured."}

    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    # Use "document" field as per GPTZero API spec
    payload = {"document": article}
    try:
        async with httpx.AsyncClient(timeout=float(settings.get("timeoutSeconds") or 60)) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        raw = response.json()
    except Exception as exc:
        return {"enabled": True, "error": str(exc), "score": None, "raw": {}}

    # Parse documents array (GPTZero wraps results in documents[])
    docs = raw.get("documents") or []
    doc = docs[0] if docs else {}

    # Overall AI probability (0-1 float)
    ai_prob_raw = doc.get("completely_generated_prob") or doc.get("average_generated_prob") or 0.0
    ai_probability = round(float(ai_prob_raw) * 100, 1)
    human_score = round(100 - ai_probability, 1)

    predicted_class = str(doc.get("predicted_class") or "unknown")
    confidence_category = str(doc.get("confidence_category") or "")
    result_message = str(doc.get("result_message") or "")
    doc_classification = str(doc.get("document_classification") or "")

    # Sentence-level analysis: collect flagged sentences (AI-highlighted)
    sentences = doc.get("sentences") or []
    flagged: list[dict] = []
    for sent in sentences:
        if not isinstance(sent, dict):
            continue
        gp = float(sent.get("generated_prob") or 0)
        highlighted = sent.get("highlight_sentence_for_ai") is True
        if highlighted or gp >= 0.85:
            flagged.append({
                "sentence": str(sent.get("sentence") or "")[:200],
                "ai_prob": round(gp * 100, 1),
            })

    # Build actionable revision advice
    advice: list[str] = []
    if result_message:
        advice.append(f"GPTZero verdict: {result_message}")

    if predicted_class in ("ai", "mixed") and flagged:
        # Group flagged sentences into advice items (max 5 to avoid noise)
        top_flagged = sorted(flagged, key=lambda x: x["ai_prob"], reverse=True)[:5]
        for item in top_flagged:
            advice.append(
                f"Rewrite this AI-flagged sentence ({item['ai_prob']:.0f}% AI): "
                f"\"{item['sentence'][:120]}\""
            )
        advice.append(
            "General fix: replace generic AI-sounding sentences with specific facts, "
            "first-person observations, concrete numbers, or source citations."
        )
    elif predicted_class in ("ai", "mixed"):
        advice.append(
            "Overall text reads as AI-generated. Add personal experience, named sources, "
            "product-specific details, and vary sentence rhythm."
        )

    return {
        "enabled": True,
        "score": human_score,
        "aiProbability": ai_probability,
        "predictedClass": predicted_class,
        "confidenceCategory": confidence_category,
        "documentClassification": doc_classification,
        "flaggedSentences": flagged,
        "flaggedCount": len(flagged),
        "totalSentences": len(sentences),
        "revisionAdvice": advice,
        "raw": raw,
    }


def merge_evaluation_scores(model_eval: dict[str, Any], gptzero_eval: dict[str, Any], language: str, config: dict[str, Any]) -> dict[str, Any]:
    model_score = numeric_score(model_eval.get("score"), 0)
    gptzero_score = numeric_score(gptzero_eval.get("score"), 0) if gptzero_eval.get("score") is not None else None
    weight = float((config.get("gptZeroSettings") or {}).get("weight") or 0.35)
    use_gptzero = language == "en" and gptzero_score is not None and not gptzero_eval.get("error")
    combined = round(model_score * (1 - weight) + gptzero_score * weight, 1) if use_gptzero else round(model_score, 1)
    gptzero_advice = as_text_list(gptzero_eval.get("revisionAdvice"))
    model_advice = as_text_list(model_eval.get("revisionAdvice"))
    merged = dict(model_eval)
    merged["score"] = combined
    merged["modelScore"] = round(model_score, 1)
    merged["gptZeroScore"] = gptzero_score
    merged["combinedScore"] = combined
    merged["scoreBreakdown"] = {
        "modelScore": round(model_score, 1),
        "gptZeroScore": gptzero_score,
        "combinedScore": combined,
        "gptZeroWeight": weight if use_gptzero else 0,
        "mode": "model+gptzero" if use_gptzero else "model-only",
        "language": language,
        "gptZeroSkipped": gptzero_eval.get("skipped"),
        "gptZeroError": gptzero_eval.get("error"),
    }
    merged["gptZero"] = gptzero_eval
    merged["modelEvaluation"] = model_eval
    merged["revisionAdvice"] = gptzero_advice + [item for item in model_advice if item not in gptzero_advice]
    return merged


async def score_article(input_data: dict[str, Any]) -> dict[str, Any]:
    config = read_config(mask_key=False)
    language = active_language(input_data, config)
    prompts = prompts_for(input_data, config)
    eeat_rules = load_eeat_rules()
    article = str(input_data.get("article") or "").strip()
    if not article:
        raise HTTPException(status_code=400, detail="请先输入需要评价的文章内容。")
    rule_evaluation = evaluate_eeat_rules(article, input_data, eeat_rules)

    evaluation_text = await call_task_model(
        config,
        "evaluator",
        build_messages(
            prompts["optimizer"],
            {
                "article": article,
                "language": language,
                "humanFeedback": input_data.get("humanFeedback") or "",
                "rubric": input_data.get("rubric") or "",
                "eeatScoringRules": {
                    "scoreValues": eeat_rules.get("scoreValues"),
                    "quadrantFormula": eeat_rules.get("quadrantFormula"),
                    "defaultWeights": eeat_rules.get("defaultWeights"),
                    "contentTypeWeights": eeat_rules.get("contentTypeWeights"),
                    "blockerIds": eeat_rules.get("blockerIds"),
                    "items": eeat_rules_for_prompt(eeat_rules, rule_evaluation),
                },
                "deterministicRuleEvaluation": rule_evaluation,
                "strictInstruction": (
                    "必须严格按 eeatScoringRules 的 60 项逐项评分。每项 score 只能是 0、0.5、1。"
                    "deterministicRuleEvaluation 中 locked=true 的项目已有后端规则证据，除非正文证据明显相反，否则沿用该分数。"
                    "不要自行发明指标。返回 JSON 必须包含 itemScores 数组，每项含 id, score, evidence, suggestion；"
                    "同时给出 contentType。后端会按表格权重重新计算最终分。"
                    if language == "zh"
                    else "Strictly score all 60 items in eeatScoringRules. Each score must be 0, 0.5, or 1. "
                    "Items with locked=true in deterministicRuleEvaluation already have backend rule evidence; preserve those scores unless the article clearly contradicts them. "
                    "Do not invent metrics. Return JSON with itemScores array; each item has id, score, evidence, suggestion; "
                    "also include contentType. The backend recalculates the final score using spreadsheet weights."
                ),
                "trainingMode": True,
            },
        ),
    )
    raw_model_eval = extract_json(evaluation_text, "Content evaluator")
    raw_model_eval = apply_rule_scores(raw_model_eval, rule_evaluation)
    eeat_report = calculate_eeat_report(raw_model_eval, eeat_rules, str(raw_model_eval.get("contentType") or input_data.get("contentType") or ""))
    model_eval = {
        **raw_model_eval,
        **eeat_report,
        "score": eeat_report["score"],
        "revisionAdvice": eeat_report["revisionAdvice"] or as_text_list(raw_model_eval.get("revisionAdvice")),
        "eeatReport": eeat_report,
    }
    gptzero_eval = await call_gptzero_score(config, article, language)
    return merge_evaluation_scores(model_eval, gptzero_eval, language, config)


async def compare_article_scores(input_data: dict[str, Any]) -> dict[str, Any]:
    articles = input_data.get("articles") or []
    if not isinstance(articles, list) or not articles:
        raise HTTPException(status_code=400, detail="请至少选择一篇文章进行评分比较。")
    if len(articles) > 8:
        raise HTTPException(status_code=400, detail="一次最多比较 8 篇文章，避免消耗过多模型额度。")

    results: list[dict[str, Any]] = []
    for index, item in enumerate(articles, start=1):
        article = str((item or {}).get("article") or "").strip()
        if not article:
            continue
        evaluation = await score_article(
            {
                **input_data,
                "article": article,
                "humanFeedback": input_data.get("humanFeedback") or "",
                "rubric": input_data.get("rubric") or "只评分，不修改文章。比较真人感、AI 检索曝光、可信度和结构完整性。",
            }
        )
        results.append(
            {
                "id": item.get("id") or f"article-{index}",
                "title": item.get("title") or item.get("versionLabel") or f"文章 {index}",
                "versionLabel": item.get("versionLabel") or "",
                "groupName": item.get("groupName") or item.get("title") or "",
                "articlePreview": article[:360],
                "evaluation": evaluation,
                "score": evaluation.get("score"),
            }
        )

    if not results:
        raise HTTPException(status_code=400, detail="选择的文章没有可评分正文。")
    sorted_results = sorted(results, key=lambda item: float(item.get("score") or 0), reverse=True)
    best = sorted_results[0]
    weakest = sorted_results[-1]
    average = round(sum(float(item.get("score") or 0) for item in results) / len(results), 1)
    language = active_language(input_data, read_config(mask_key=False))
    summary = (
        f"本次共比较 {len(results)} 篇，平均分 {average}。最高分是「{best.get('title')}」"
        f"（{best.get('score', '-')}），最低分是「{weakest.get('title')}」（{weakest.get('score', '-')}）。"
        "优先参考高分文章的结构、证据密度和自然口吻。"
        if language == "zh"
        else f"Compared {len(results)} articles, average score {average}. Best: {best.get('title')} "
        f"({best.get('score', '-')}); weakest: {weakest.get('title')} ({weakest.get('score', '-')}). "
        "Use the highest-scoring article as the benchmark for structure, evidence density, and natural voice."
    )
    return {
        "results": sorted_results,
        "averageScore": average,
        "bestId": best.get("id"),
        "summary": summary,
    }


def compact_prompt_diff(before: str, after: str) -> dict[str, Any]:
    before_lines = [line.strip() for line in before.splitlines() if line.strip()]
    after_lines = [line.strip() for line in after.splitlines() if line.strip()]
    added = [line[2:] for line in difflib.ndiff(before_lines, after_lines) if line.startswith("+ ")]
    removed = [line[2:] for line in difflib.ndiff(before_lines, after_lines) if line.startswith("- ")]
    return {
        "added": added[:5],
        "removed": removed[:5],
        "changed": max(len(added), len(removed)),
    }


def iteration_model_input(input_data: dict[str, Any]) -> dict[str, Any]:
    blocked = {"promptOverrides", "prompts", "prompt_modifier", "training_evaluator", "optimizer", "revision", "articlePrompt", "outlinePrompt"}
    clean = {key: value for key, value in input_data.items() if key not in blocked and "prompt" not in key.lower()}
    return clean


async def revise_article_with_repair(
    config: dict[str, Any],
    language: str,
    payload: dict[str, Any],
    first_text: str,
    label: str,
) -> dict[str, Any]:
    modification = extract_revision_json(first_text, label)
    if not modification.get("formatError"):
        return modification
    repair_text = await call_task_model(
        config,
        "revision",
        build_messages(
            REVISION_SYSTEM_PROMPTS.get(language, REVISION_SYSTEM_PROMPTS["zh"]),
            {
                **payload,
                "previousBadOutput": first_text[:5000],
                "repairInstruction": (
                    "The previous answer modified a prompt instead of rewriting the article. Ignore that output. "
                    "Now rewrite the article itself and return strict JSON with revisedArticle as the full Markdown article."
                ),
            },
        ),
    )
    repaired = extract_revision_json(repair_text, f"{label} repair")
    if repaired.get("formatError") or not str(repaired.get("revisedArticle") or "").strip():
        raise HTTPException(status_code=502, detail="修改 AI 仍返回了 prompt 修改格式，未得到正文。请检查内容迭代模型配置。")
    return repaired


async def await_with_progress(
    awaitable: Awaitable[str],
    *,
    stage: str,
    round_index: int,
    total_rounds: int,
    message: str,
    heartbeat: str,
    interval: int = 20,
) -> AsyncIterator[dict[str, Any]]:
    task = asyncio.create_task(awaitable)
    try:
        while not task.done():
            yield {
                "type": "progress",
                "stage": stage,
                "message": message,
                "heartbeat": heartbeat,
                "round": round_index,
                "totalRounds": total_rounds,
            }
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=interval)
            except asyncio.TimeoutError:
                continue
        yield {
            "type": "model_result",
            "stage": stage,
            "round": round_index,
            "totalRounds": total_rounds,
            "text": await task,
        }
    finally:
        if not task.done():
            task.cancel()



async def adversarial_train(input_data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] | None = None
    async for event in adversarial_train_events(input_data):
        if event.get("type") == "result":
            result = event["result"]
    if result is None:
        raise HTTPException(status_code=502, detail="迭代没有返回结果。")
    return result


async def adversarial_train_events(input_data: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    config = read_config(mask_key=False)
    language = active_language(input_data, config)
    prompts = prompts_for(input_data, config)
    eeat_rules = load_eeat_rules()
    clean_input = iteration_model_input(input_data)
    rounds_count = max(1, min(6, int(input_data.get("rounds") or input_data.get("iterations") or 3)))
    outline = input_data.get("outline") or await build_outline(input_data)
    human_feedback = str(input_data.get("humanFeedback") or "").strip()
    training_goal = str(input_data.get("trainingGoal") or "").strip()
    seed_article = str(input_data.get("seedArticle") or "").strip()
    rounds: list[dict[str, Any]] = []
    article = str(input_data.get("seedArticle") or input_data.get("article") or "").strip()
    if not article:
        article = await generate_article_segmented(config, language, prompts, input_data, outline)

    yield {"type": "progress", "stage": "outline", "message": "准备迭代样本", "round": 0, "totalRounds": rounds_count}
    for round_index in range(1, rounds_count + 1):
        yield {"type": "progress", "stage": "evaluate", "message": "评价 AI 正在读取当前文章并打分建议", "round": round_index, "totalRounds": rounds_count}
        evaluation_text = ""
        rule_evaluation = evaluate_eeat_rules(article, input_data, eeat_rules)
        async for model_event in await_with_progress(
            call_task_model(
                config,
                "evaluator",
                build_messages(
                    prompts.get("training_evaluator") or prompts["optimizer"],
                    {
                        "input": clean_input,
                        "outline": outline,
                        "article": article,
                        "referenceContext": reference_context(input_data),
                        "seedArticle": seed_article,
                        "round": round_index,
                        "humanFeedback": human_feedback,
                        "trainingGoal": training_goal,
                        "eeatScoringRules": {
                            "scoreValues": eeat_rules.get("scoreValues"),
                            "quadrantFormula": eeat_rules.get("quadrantFormula"),
                            "defaultWeights": eeat_rules.get("defaultWeights"),
                            "contentTypeWeights": eeat_rules.get("contentTypeWeights"),
                            "blockerIds": eeat_rules.get("blockerIds"),
                            "items": eeat_rules_for_prompt(eeat_rules, rule_evaluation),
                        },
                        "deterministicRuleEvaluation": rule_evaluation,
                        "instruction": (
                            "Evaluate only. Do not rewrite the article. Strictly score all 60 E-E-A-T checklist items. "
                            "Each score must be 0, 0.5, or 1. Return itemScores with id, score, evidence, suggestion; "
                            "also include contentType. Preserve locked deterministicRuleEvaluation scores unless the article clearly contradicts them."
                        ),
                    },
                ),
            ),
            stage="evaluate",
            round_index=round_index,
            total_rounds=rounds_count,
            message="评价 AI 正在读取当前文章并打分建议",
            heartbeat="评价 AI 仍在处理，请稍候",
        ):
            if model_event.get("type") == "model_result":
                evaluation_text = str(model_event.get("text") or "")
            else:
                yield model_event
        raw_model_evaluation = extract_json(evaluation_text, f"Content iteration round {round_index}")
        raw_model_evaluation = apply_rule_scores(raw_model_evaluation, rule_evaluation)
        eeat_report = calculate_eeat_report(raw_model_evaluation, eeat_rules, str(raw_model_evaluation.get("contentType") or input_data.get("contentType") or ""))
        model_evaluation = {
            **raw_model_evaluation,
            **eeat_report,
            "score": eeat_report["score"],
            "revisionAdvice": eeat_report["revisionAdvice"] or as_text_list(raw_model_evaluation.get("revisionAdvice")),
            "eeatReport": eeat_report,
        }
        gptzero_evaluation = await call_gptzero_score(config, article, language)
        evaluation = merge_evaluation_scores(model_evaluation, gptzero_evaluation, language, config)
        yield {
            "type": "progress",
            "stage": "modify",
            "message": "修改 AI 正在根据评分建议直接优化文章",
            "round": round_index,
            "totalRounds": rounds_count,
            "score": evaluation.get("score"),
        }
        revision_payload = {
            "input": clean_input,
            "outline": outline,
            "article": article,
            "referenceContext": reference_context(input_data),
            "seedArticle": seed_article,
            "evaluation": evaluation,
            "humanFeedback": human_feedback,
            "trainingGoal": training_goal,
        }
        pending_progress: list[dict[str, Any]] = []

        async def queue_modify_progress(event: dict[str, Any]) -> None:
            pending_progress.append(event)

        revision_task = asyncio.create_task(
            revise_article_segmented(
                config,
                language,
                revision_payload,
                f"Content revision round {round_index}",
                queue_modify_progress,
                round_index,
                rounds_count,
            )
        )
        while not revision_task.done():
            while pending_progress:
                yield pending_progress.pop(0)
            await asyncio.sleep(0.2)
        modification = await revision_task
        while pending_progress:
            yield pending_progress.pop(0)
        next_article = modification.get("revisedArticle") or modification.get("article") or modification.get("updatedArticle") or article
        if isinstance(next_article, list):
            next_article = "\n".join(str(item) for item in next_article)
        next_article = str(next_article)
        diff = compact_prompt_diff(article, next_article)
        round_result = {
            "round": round_index,
            "score": evaluation.get("score"),
            "evaluation": evaluation,
            "articleBefore": article,
            "articleAfter": next_article,
            "modification": modification,
            "diff": diff,
            "article": next_article,
        }
        rounds.append(round_result)
        article = next_article
        yield {
            "type": "round",
            "stage": "round_done",
            "message": "本轮完成",
            "round": round_index,
            "totalRounds": rounds_count,
            "evaluation": evaluation,
            "score": evaluation.get("score"),
            "diff": diff,
        }
        article = next_article

    result: dict[str, Any] = {
        "article": article,
        "rounds": rounds,
        "evaluation": rounds[-1]["evaluation"] if rounds else {},
        "outline": outline,
    }
    yield {"type": "result", "stage": "done", "message": "迭代完成", "result": result}
