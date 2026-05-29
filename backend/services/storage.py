import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.settings import BLOG_DIR, CONFIG_PATH, DATA_DIR, DEFAULT_CONFIG


def deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def ensure_data() -> None:
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        write_config(DEFAULT_CONFIG)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_config(mask_key: bool = False) -> dict[str, Any]:
    ensure_data()
    config = normalize_config(read_json(CONFIG_PATH, {}))
    if mask_key:
        config = mask_config_keys(config)
    return config


def write_config(incoming: dict[str, Any]) -> dict[str, Any]:
    current = read_config(mask_key=False) if CONFIG_PATH.exists() else deepcopy(DEFAULT_CONFIG)
    incoming = deepcopy(incoming)
    current_profiles = {profile.get("id"): profile for profile in current.get("apiProfiles", [])}
    next_profiles = []
    for profile in incoming.get("apiProfiles", []):
        profile = dict(profile)
        old = current_profiles.get(profile.get("id"), {})
        if profile.get("apiKey") in {"********", ""} and old.get("apiKey"):
            profile["apiKey"] = old.get("apiKey", "")
        next_profiles.append(profile)
    if "apiProfiles" in incoming:
        incoming["apiProfiles"] = next_profiles
    if "gptZeroSettings" in incoming:
        incoming_gptzero = dict(incoming.get("gptZeroSettings") or {})
        old_gptzero = current.get("gptZeroSettings") or {}
        if incoming_gptzero.get("apiKey") in {"********", ""} and old_gptzero.get("apiKey"):
            incoming_gptzero["apiKey"] = old_gptzero.get("apiKey", "")
        incoming["gptZeroSettings"] = incoming_gptzero

    merged = normalize_config(deep_merge(current, incoming))
    write_json(CONFIG_PATH, merged)
    return merged


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = deep_merge(DEFAULT_CONFIG, raw or {})
    legacy_api = raw.get("api") if isinstance(raw, dict) else None
    legacy_models = raw.get("models") if isinstance(raw, dict) else None
    if legacy_api and not config.get("apiProfiles"):
        profile = {
            "id": "default",
            "name": "默认 API",
            "endpoint": legacy_api.get("endpoint", ""),
            "apiKey": legacy_api.get("apiKey", ""),
            "headersJson": legacy_api.get("headersJson", "{}"),
            "models": {
                "outline": (legacy_models or {}).get("planner", ""),
                "article": (legacy_models or {}).get("generator", ""),
                "evaluator": (legacy_models or {}).get("evaluator", ""),
                "revision": (legacy_models or {}).get("evaluator", ""),
            },
        }
        config["apiProfiles"] = [profile]
        config["taskAssignments"] = {
            "outline": "default",
            "article": "default",
            "evaluator": "default",
            "revision": "default",
            "search_planner": "default",
        }
    assignments = config.setdefault("taskAssignments", {})
    if assignments.get("optimizer"):
        if not assignments.get("evaluator"):
            assignments["evaluator"] = assignments.get("optimizer")
        if not assignments.get("revision"):
            assignments["revision"] = assignments.get("optimizer")
    if "image" not in assignments:
        assignments["image"] = assignments.get("article") or ""
    if not assignments.get("search_planner"):
        assignments["search_planner"] = assignments.get("outline") or ""
    for profile in config.get("apiProfiles", []):
        models = profile.setdefault("models", {})
        if models.get("optimizer"):
            if not models.get("evaluator"):
                models["evaluator"] = models.get("optimizer")
            if not models.get("revision"):
                models["revision"] = models.get("optimizer")
        if not models.get("image") and models.get("article"):
            models["image"] = models.get("article")
        if not models.get("search_planner") and models.get("outline"):
            models["search_planner"] = models.get("outline")
    if config.get("language") not in {"zh", "en"}:
        config["language"] = "zh"
    if config.get("outputLanguage") not in {"zh", "en"}:
        config["outputLanguage"] = config.get("language") or "zh"
    return config


def mask_config_keys(config: dict[str, Any]) -> dict[str, Any]:
    masked = deepcopy(config)
    for profile in masked.get("apiProfiles", []):
        if profile.get("apiKey"):
            profile["apiKey"] = "********"
    if (masked.get("gptZeroSettings") or {}).get("apiKey"):
        masked["gptZeroSettings"]["apiKey"] = "********"
    return masked


def blog_path(blog_id: str) -> Path:
    safe_id = "".join(ch for ch in str(blog_id) if ch.isalnum() or ch in "-_")
    return BLOG_DIR / f"{safe_id}.json"


def normalize_blog_record(blog: dict[str, Any]) -> dict[str, Any]:
    blog = dict(blog or {})
    blog_id = str(blog.get("id") or "")
    title = blog.get("title") or "Untitled"
    blog.setdefault("groupId", blog.get("sourceBlogId") or blog_id)
    blog.setdefault("groupName", title)
    blog.setdefault("versionIndex", 1)
    blog.setdefault("versionLabel", "初始版本")
    blog.setdefault("tags", [])
    blog.setdefault("updatedAt", blog.get("createdAt"))
    return blog


def next_version_index(group_id: str) -> int:
    ensure_data()
    max_index = 0
    for path in BLOG_DIR.glob("*.json"):
        try:
            blog = normalize_blog_record(read_json(path, {}))
            if blog.get("groupId") == group_id:
                max_index = max(max_index, int(blog.get("versionIndex") or 1))
        except Exception:
            continue
    return max_index + 1


def save_blog(blog: dict[str, Any]) -> dict[str, Any]:
    blog = normalize_blog_record(blog)
    write_json(blog_path(blog["id"]), blog)
    return blog


def update_blog(blog_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    blog = normalize_blog_record(get_blog(blog_id))
    blog.update(updates)
    blog["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return save_blog(blog)


def update_blog_group(group_id: str, group_name: str) -> list[dict[str, Any]]:
    ensure_data()
    updated: list[dict[str, Any]] = []
    for path in BLOG_DIR.glob("*.json"):
        try:
            blog = normalize_blog_record(read_json(path, {}))
            if blog.get("groupId") != group_id:
                continue
            blog["groupName"] = group_name
            blog["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            write_json(blog_path(blog["id"]), blog)
            updated.append(blog)
        except Exception:
            continue
    return updated


def create_blog_version(source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    source = get_blog(source_id)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    version_index = next_version_index(str(source.get("groupId") or source.get("id")))
    article = str(payload.get("article") or source.get("article") or "")
    version_label = str(payload.get("versionLabel") or f"手动编辑版本 {version_index}").strip()
    title = str(payload.get("title") or f"{source.get('groupName') or source.get('title') or 'Untitled'} - {version_label}")
    blog = {
        **source,
        "id": str(payload.get("id") or f"manual_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{version_index}"),
        "title": title,
        "createdAt": now,
        "updatedAt": now,
        "article": article,
        "groupId": source.get("groupId") or source.get("id"),
        "groupName": source.get("groupName") or source.get("title") or "Untitled",
        "versionIndex": version_index,
        "versionLabel": version_label,
        "sourceBlogId": source.get("id"),
        "tags": payload.get("tags") or source.get("tags") or [],
    }
    return save_blog(blog)


def get_blog(blog_id: str) -> dict[str, Any]:
    path = blog_path(blog_id)
    if not path.exists():
        raise FileNotFoundError("Blog not found.")
    return normalize_blog_record(read_json(path, {}))


def delete_blog(blog_id: str) -> None:
    path = blog_path(blog_id)
    if path.exists():
        path.unlink()


def list_blogs() -> list[dict[str, Any]]:
    ensure_data()
    records: list[dict[str, Any]] = []
    for path in BLOG_DIR.glob("*.json"):
        try:
            blog = normalize_blog_record(read_json(path, {}))
            records.append(
                {
                    "id": blog.get("id"),
                    "title": blog.get("title"),
                    "createdAt": blog.get("createdAt"),
                    "updatedAt": blog.get("updatedAt"),
                    "score": (blog.get("evaluation") or {}).get("score"),
                    "productType": (blog.get("input") or {}).get("productType"),
                    "tags": blog.get("tags") or [],
                    "groupId": blog.get("groupId"),
                    "groupName": blog.get("groupName") or blog.get("title"),
                    "versionIndex": blog.get("versionIndex") or 1,
                    "versionLabel": blog.get("versionLabel") or "初始版本",
                }
            )
        except Exception:
            continue

    def sort_key(item: dict[str, Any]) -> datetime:
        try:
            return datetime.fromisoformat(str(item.get("createdAt")).replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(records, key=sort_key, reverse=True)
