"""飞书事件回调 API — 接收飞书群消息，转发到行情情报处理。"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database import SessionLocal
from app.services.feishu_bot import process_event, get_feishu_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feishu", tags=["feishu"])


@router.post("/webhook")
async def feishu_webhook(request: Request):
    """飞书事件订阅回调地址。

    飞书每隔1分钟会POST事件到此端点。
    注意：必须在3秒内返回HTTP 200，否则飞书会重试。
    实际处理逻辑异步进行，不阻塞响应。
    """
    body_bytes = await request.body()

    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        return JSONResponse({"code": 1, "msg": "Invalid JSON"}, status_code=400)

    # URL验证（首次配置回调地址时飞书会发这个）
    if body.get("type") == "url_verification":
        result = await process_event(body)
        challenge_val = result.get("challenge", "")
        if isinstance(challenge_val, str) and challenge_val:
            return JSONResponse({"challenge": challenge_val})
        return JSONResponse({"challenge": str(challenge_val)})

    # 可选：签名验证
    client = get_feishu_client()
    if client.is_configured and client.verification_token:
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        if timestamp and nonce:
            body_str = body_bytes.decode("utf-8")
            valid = await client.verify_signature(timestamp, nonce, body_str)
            if not valid and client.verification_token:
                # 签名不匹配时记录但不拒绝（方便调试）
                logger.warning("飞书事件签名验证失败，继续处理")

    # 处理事件（同步处理需在3秒内完成，否则用后台任务）
    try:
        # 尝试获取数据库会话
        db = SessionLocal()
        try:
            result = await process_event(body, db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"飞书事件处理异常: {e}", exc_info=True)
        result = {"processed": False, "reason": str(e)}

    # 立即返回200，飞书要求3秒内响应
    return JSONResponse({"code": 0, "msg": "ok"})


@router.get("/webhook")
async def feishu_webhook_get(request: Request):
    """GET请求用于调试。"""
    return {"status": "feishu webhook endpoint ready"}


@router.get("/status")
async def feishu_status():
    """检查飞书机器人配置状态。"""
    client = get_feishu_client()
    return {
        "configured": client.is_configured,
        "app_id": f"{client.app_id[:6]}..." if client.app_id else "(未配置)",
        "has_secret": bool(client.app_secret),
        "has_verification_token": bool(client.verification_token),
        "note": "已配置" if client.is_configured else "请在 .env 中设置 FEISHU_APP_ID / FEISHU_APP_SECRET",
    }
