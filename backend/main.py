from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import json

from backend.services.generator import adversarial_train, adversarial_train_events, analyze_intents, build_outline, compare_article_scores, generate_blog, generate_blog_events, generate_titles, score_article
from backend.services.model_client import test_profile, get_token_log, reset_token_log
from backend.services.reference_search import generate_image_placeholder, search_references
from backend.services.storage import (
    delete_blog,
    create_blog_version,
    get_blog,
    list_blogs,
    next_version_index,
    read_config,
    save_blog,
    update_blog_group,
    update_blog,
    write_config,
)
from backend.settings import PUBLIC_DIR

app = FastAPI(title="Local AI Blog Generator", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
def api_get_config() -> dict[str, Any]:
    return read_config(mask_key=True)


@app.put("/api/config")
def api_update_config(payload: dict[str, Any]) -> dict[str, Any]:
    saved = write_config(payload)
    return read_config(mask_key=True)


@app.post("/api/outline")
async def api_outline(payload: dict[str, Any]) -> dict[str, Any]:
    return await build_outline(payload)


@app.post("/api/intent-analysis")
async def api_intent_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    return await analyze_intents(payload)


@app.post("/api/title-options")
async def api_title_options(payload: dict[str, Any]) -> dict[str, Any]:
    return await generate_titles(payload)


@app.post("/api/search-references")
async def api_search_references(payload: dict[str, Any]) -> dict[str, Any]:
    return await search_references(payload)


@app.post("/api/generate-image")
async def api_generate_image(payload: dict[str, Any]) -> dict[str, Any]:
    return await generate_image_placeholder(payload)


@app.post("/api/generate")
async def api_generate(payload: dict[str, Any]) -> dict[str, Any]:
    return await generate_blog(payload)


@app.post("/api/generate/stream")
async def api_generate_stream(payload: dict[str, Any]) -> StreamingResponse:
    async def stream():
        async for event in generate_blog_events(payload):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/score")
async def api_score(payload: dict[str, Any]) -> dict[str, Any]:
    return await score_article(payload)


@app.post("/api/score/compare")
async def api_score_compare(payload: dict[str, Any]) -> dict[str, Any]:
    return await compare_article_scores(payload)


@app.post("/api/adversarial-train")
async def api_adversarial_train(payload: dict[str, Any]) -> dict[str, Any]:
    return await adversarial_train(payload)


@app.post("/api/adversarial-train/stream")
async def api_adversarial_train_stream(payload: dict[str, Any]) -> StreamingResponse:
    async def stream():
        try:
            async for event in adversarial_train_events(payload):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except HTTPException as exc:
            event = {"type": "error", "stage": "error", "message": exc.detail, "statusCode": exc.status_code}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            event = {"type": "error", "stage": "error", "message": f"迭代请求失败：{exc}"}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/test-profile")
async def api_test_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return await test_profile(payload.get("profile") or {}, payload.get("model") or "")


@app.get("/api/blogs")
def api_list_blogs() -> list[dict[str, Any]]:
    return list_blogs()


@app.post("/api/blogs")
def api_create_blog(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("groupId") and not payload.get("versionIndex"):
        payload["versionIndex"] = next_version_index(str(payload.get("groupId")))
    return save_blog(payload)


@app.get("/api/blogs/{blog_id}")
def api_get_blog(blog_id: str) -> dict[str, Any]:
    try:
        return get_blog(blog_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Blog not found.") from exc


@app.delete("/api/blogs/{blog_id}")
def api_delete_blog(blog_id: str) -> dict[str, bool]:
    delete_blog(blog_id)
    return {"ok": True}


@app.put("/api/blogs/{blog_id}")
def api_update_blog(blog_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return update_blog(blog_id, payload)


@app.post("/api/blogs/{blog_id}/versions")
def api_create_blog_version(blog_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return create_blog_version(blog_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Blog not found.") from exc


@app.put("/api/blog-groups/{group_id}")
def api_update_blog_group(group_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    group_name = str(payload.get("groupName") or "").strip()
    if not group_name:
        raise HTTPException(status_code=400, detail="组名不能为空。")
    updated = update_blog_group(group_id, group_name)
    if not updated:
        raise HTTPException(status_code=404, detail="文章组不存在。")
    return {"ok": True, "count": len(updated), "groupId": group_id, "groupName": group_name}


@app.get("/api/token-log")
def api_token_log() -> dict[str, Any]:
    return {"entries": get_token_log()}

@app.post("/api/token-log/reset")
def api_token_log_reset() -> dict[str, Any]:
    reset_token_log()
    return {"ok": True}

app.mount("/assets", StaticFiles(directory=str(PUBLIC_DIR)), name="assets")


@app.get("/{path:path}")
def serve_frontend(path: str) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found.")
    NO_CACHE = {"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"}
    target = PUBLIC_DIR / path if path else PUBLIC_DIR / "index.html"
    if target.is_file() and target.resolve().is_relative_to(PUBLIC_DIR.resolve()):
        # 只对 index.html 禁止缓存，静态资源（js/css）依赖版本号缓存
        headers = NO_CACHE if target.name == "index.html" else {}
        return FileResponse(target, headers=headers)
    return FileResponse(PUBLIC_DIR / "index.html", headers=NO_CACHE)
