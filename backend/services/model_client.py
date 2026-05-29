import json
import time
import asyncio
from typing import Any

import httpx
from fastapi import HTTPException

from backend.services.storage import read_config

# ── Token usage log ────────────────────────────────────────────────────────
_TOKEN_LOG: list[dict[str, Any]] = []


def reset_token_log() -> None:
    global _TOKEN_LOG
    _TOKEN_LOG = []


def get_token_log() -> list[dict[str, Any]]:
    return list(_TOKEN_LOG)


def _extract_usage(raw: Any) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) from any API response format."""
    if not isinstance(raw, dict):
        return 0, 0
    usage = raw.get("usage") or {}
    if not isinstance(usage, dict):
        return 0, 0
    # Debug: write raw usage to workspace so we can inspect the actual format
    try:
        import os
        import pathlib
        debug_path = pathlib.Path(__file__).parent.parent.parent / "usage_debug.jsonl"
        top_keys = list(raw.keys())
        with open(debug_path, "a") as f:
            f.write(json.dumps({"top_keys": top_keys, "usage": dict(usage)}) + "\n")
    except Exception:
        pass
    # Anthropic format: input_tokens / output_tokens (may include cache tokens)
    # OpenAI / DeepSeek format: prompt_tokens / completion_tokens
    inp_anthropic = (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )
    inp_openai = usage.get("prompt_tokens") or 0
    out_anthropic = usage.get("output_tokens") or 0
    out_openai = usage.get("completion_tokens") or 0
    # Prefer whichever gives a larger (more realistic) input count
    inp = max(inp_anthropic, inp_openai)
    out = max(out_anthropic, out_openai)
    return int(inp), int(out)


TASK_LABELS = {
    "outline": "大纲生成",
    "article": "正文生成",
    "optimizer": "内容迭代",
    "evaluator": "内容评分",
    "revision": "内容修改",
    "image": "图片生成",
    "search_planner": "搜索规划",
}

MODEL_REQUEST_TIMEOUT = 1200
PROFILE_TEST_TIMEOUT = 180
MODEL_RETRY_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504, 524, 529}
MODEL_MAX_ATTEMPTS = 3


def profile_for_task(config: dict[str, Any], task: str) -> dict[str, Any]:
    assignment = (config.get("taskAssignments") or {}).get(task)
    if not assignment and task in {"evaluator", "revision"}:
        assignment = (config.get("taskAssignments") or {}).get("optimizer")
    if not assignment and task == "entity_extractor":
        assignment = (config.get("taskAssignments") or {}).get("outline")
    profile_id = assignment.get("profileId") if isinstance(assignment, dict) else assignment
    profiles = config.get("apiProfiles") or []
    profile = next((item for item in profiles if item.get("id") == profile_id), None)
    if not profile:
        raise HTTPException(status_code=400, detail=f"请先为“{TASK_LABELS.get(task, task)}”分配一个 API 卡片。")
    return profile


def selected_model_for_task(config: dict[str, Any], profile: dict[str, Any], task: str) -> str:
    assignment = (config.get("taskAssignments") or {}).get(task)
    if not assignment and task in {"evaluator", "revision"}:
        assignment = (config.get("taskAssignments") or {}).get("optimizer")
    if not assignment and task == "entity_extractor":
        assignment = (config.get("taskAssignments") or {}).get("outline")
    if isinstance(assignment, dict):
        model = str(assignment.get("model") or "").strip()
    else:
        models = profile.get("models") or {}
        model = str(models.get(task) or (models.get("optimizer") if task in {"evaluator", "revision"} else "") or "").strip()
    return model


def require_profile(config: dict[str, Any], profile: dict[str, Any], task: str) -> tuple[str, str, str]:
    endpoint = str(profile.get("endpoint") or "").strip()
    api_key = str(profile.get("apiKey") or "").strip()
    model = selected_model_for_task(config, profile, task)
    if not endpoint or not api_key:
        raise HTTPException(status_code=400, detail=f"“{profile.get('name') or profile.get('id')}”缺少 endpoint 或 API Key。")
    if not model:
        raise HTTPException(status_code=400, detail=f"请在 API 卡片中配置“{TASK_LABELS.get(task, task)}”模型名。")
    return endpoint, api_key, model


def parse_headers(profile: dict[str, Any]) -> dict[str, str]:
    raw_headers = str(profile.get("headersJson") or "{}").strip()
    try:
        parsed = json.loads(raw_headers)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Extra Headers JSON 格式无效。") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Extra Headers JSON 必须是对象。")
    api_key = str(profile.get("apiKey") or "")
    return {str(key): str(value).replace("{{apiKey}}", api_key) for key, value in parsed.items()}


def build_messages(system_prompt: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def endpoint_for_request(endpoint: str, mode: str) -> str:
    endpoint = endpoint.rstrip("/")
    if mode == "anthropic_messages" and not endpoint.endswith(("/messages", "/v1/messages")):
        return f"{endpoint}/v1/messages"
    return endpoint


async def call_task_model(config: dict[str, Any], task: str, messages: list[dict[str, str]]) -> str:
    profile = profile_for_task(config, task)
    endpoint, api_key, model = require_profile(config, profile, task)
    mode = str(profile.get("mode") or "openai_chat").strip()
    endpoint = endpoint_for_request(endpoint.replace("{{model}}", model), mode)
    headers = {
        "Content-Type": "application/json",
        **parse_headers(profile),
    }
    lower_headers = {key.lower(): value for key, value in headers.items()}
    if mode == "anthropic_messages":
        if "authorization" not in lower_headers:
            headers.setdefault("x-api-key", api_key)
        headers.setdefault("anthropic-version", "2023-06-01")
    elif mode == "gemini_generate_content":
        headers.setdefault("x-goog-api-key", api_key)
    elif api_key and not any(key in lower_headers for key in ("authorization", "x-api-key", "api-key", "x-goog-api-key")):
        headers["Authorization"] = f"Bearer {api_key}"
    payload = build_payload(profile, mode, model, messages)

    response = None
    last_error: Exception | None = None
    _t0 = time.time()
    for attempt in range(1, MODEL_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=MODEL_REQUEST_TIMEOUT) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MODEL_MAX_ATTEMPTS:
                await asyncio.sleep(attempt * 2)
                continue
            raise HTTPException(status_code=504, detail=f"模型接口超时：已等待 {MODEL_REQUEST_TIMEOUT} 秒，重试 {MODEL_MAX_ATTEMPTS} 次仍未返回。") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MODEL_MAX_ATTEMPTS:
                await asyncio.sleep(attempt * 2)
                continue
            raise HTTPException(status_code=502, detail=f"模型接口请求失败：{exc}") from exc
        if response.status_code in MODEL_RETRY_STATUSES and attempt < MODEL_MAX_ATTEMPTS:
            await asyncio.sleep(attempt * 2)
            continue
        break

    if response is None:
        raise HTTPException(status_code=502, detail=f"模型接口请求失败：{last_error or '未知错误'}")

    try:
        raw = response.json()
    except ValueError:
        raw = {"text": response.text}

    if response.status_code >= 400:
        message = (
            ((raw.get("error") or {}).get("message") if isinstance(raw.get("error"), dict) else None)
            or raw.get("message")
            or raw.get("detail")
            or response.text[:500]
            or f"Model request failed: {response.status_code}"
        )
        if response.status_code == 524:
            message = f"网关等待模型响应超时（HTTP 524）。通常是上游代理或模型服务处理时间过长，请稍后重试或换更快的模型。原始信息：{message}"
        raise HTTPException(status_code=response.status_code, detail=f"模型接口返回 HTTP {response.status_code}：{message}")

    text = extract_text(raw)
    inp, out = _extract_usage(raw)
    _TOKEN_LOG.append({
        "task": task,
        "model": model,
        "elapsed_ms": round((time.time() - _t0) * 1000),
        "input_tokens": inp,
        "output_tokens": out,
    })
    return text or json.dumps(raw, ensure_ascii=False)


def build_payload(profile: dict[str, Any], mode: str, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    if mode == "anthropic_messages":
        system = "\n\n".join(item["content"] for item in messages if item.get("role") == "system")
        user_messages = [
            {"role": "user" if item.get("role") == "system" else item.get("role", "user"), "content": item.get("content", "")}
            for item in messages
            if item.get("role") != "system"
        ]
        return {
            "model": model,
            "max_tokens": int(profile.get("maxTokens") or 4096),
            "system": system,
            "messages": user_messages,
        }
    if mode == "gemini_generate_content":
        text = "\n\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in messages)
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": text}],
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
            },
        }
    if mode == "openai_responses":
        return {
            "model": model,
            "input": messages,
            "temperature": 0.7,
        }
    if mode == "custom_json":
        template = str(profile.get("bodyTemplate") or "").strip()
        if template:
            try:
                raw = template.replace("{{model}}", model).replace("{{messages}}", json.dumps(messages, ensure_ascii=False))
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail="自定义请求体模板不是有效 JSON。") from exc
        return {"model": model, "messages": messages, "temperature": 0.7}
    return {"model": model, "messages": messages, "temperature": 0.7}


def extract_text(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ""
    text = (
        (((raw.get("choices") or [{}])[0].get("message") or {}).get("content"))
        or raw.get("output_text")
        or raw.get("text")
    )
    if not text and isinstance(raw.get("content"), list) and raw["content"]:
        chunks = [item.get("text", "") for item in raw["content"] if isinstance(item, dict)]
        text = "\n".join(chunk for chunk in chunks if chunk)
    if not text and isinstance(raw.get("output"), list):
        chunks = []
        for item in raw["output"]:
            for content in item.get("content", []) if isinstance(item, dict) else []:
                if isinstance(content, dict) and content.get("text"):
                    chunks.append(content["text"])
        text = "\n".join(chunks)
    if not text and isinstance(raw.get("candidates"), list):
        chunks = []
        for candidate in raw["candidates"]:
            content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
            for part in content.get("parts", []) if isinstance(content, dict) else []:
                if isinstance(part, dict) and part.get("text"):
                    chunks.append(part["text"])
        text = "\n".join(chunks)
    return text or ""


async def test_profile(profile: dict[str, Any], model: str = "") -> dict[str, Any]:
    profile = resolve_test_profile_secret(profile)
    model = model or (profile.get("availableModels") or [""])[0] or next(iter((profile.get("models") or {}).values()), "")
    endpoint = str(profile.get("endpoint") or "").strip()
    api_key = str(profile.get("apiKey") or "").strip()
    mode = str(profile.get("mode") or "openai_chat").strip()
    if not endpoint or not api_key or not model:
        raise HTTPException(status_code=400, detail="检测需要 endpoint、API Key 和至少一个模型名。")
    headers = {"Content-Type": "application/json", **parse_headers(profile)}
    endpoint = endpoint_for_request(endpoint.replace("{{model}}", model), mode)
    lower_headers = {key.lower(): value for key, value in headers.items()}
    if mode == "anthropic_messages":
        if "authorization" not in lower_headers:
            headers.setdefault("x-api-key", api_key)
        headers.setdefault("anthropic-version", "2023-06-01")
    elif mode == "gemini_generate_content":
        headers.setdefault("x-goog-api-key", api_key)
    elif not any(key in lower_headers for key in ("authorization", "x-api-key", "api-key", "x-goog-api-key")):
        headers["Authorization"] = f"Bearer {api_key}"
    messages = build_messages("Reply with OK only.", {"ping": "ok"})
    payload = build_payload(profile, mode, model, messages)
    try:
        async with httpx.AsyncClient(timeout=PROFILE_TEST_TIMEOUT) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"连通性检测失败：{exc}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=f"连通性检测失败：HTTP {response.status_code} {response.text[:300]}")
    return {"ok": True, "status": response.status_code, "model": model, "mode": mode}


def resolve_test_profile_secret(profile: dict[str, Any]) -> dict[str, Any]:
    profile = dict(profile or {})
    api_key = str(profile.get("apiKey") or "").strip()
    if api_key and api_key != "********":
        return profile
    profile_id = profile.get("id")
    if not profile_id:
        return profile
    config = read_config(mask_key=False)
    saved = next((item for item in config.get("apiProfiles", []) if item.get("id") == profile_id), None)
    if saved and saved.get("apiKey"):
        profile["apiKey"] = saved.get("apiKey")
    return profile
