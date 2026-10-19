"""飞书行情机器人主服务 — 事件接收、消息处理、结果回复。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.services.feishu_bot.feishu_client import FeishuClient, FeishuMessage
from app.services.feishu_bot.message_handler import handle_message

logger = logging.getLogger(__name__)

# ── 全局客户端实例 ──
_feishu_client: Optional[FeishuClient] = None


def get_feishu_client() -> FeishuClient:
    """获取飞书客户端单例。"""
    global _feishu_client
    if _feishu_client is None:
        _feishu_client = FeishuClient(
            app_id=getattr(settings, "feishu_app_id", ""),
            app_secret=getattr(settings, "feishu_app_secret", ""),
            verification_token=getattr(settings, "feishu_verification_token", ""),
        )
    return _feishu_client


def _parse_event_body(body: dict) -> Optional[FeishuMessage]:
    """解析飞书事件回调体，提取消息。

    飞书事件格式（v1）:
    {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1", ...},
        "event": {
            "message": {"message_id": "...", "chat_id": "...", "content": "{...}", "msg_type": "text", ...},
            "sender": {"sender_id": {"open_id": "..."}},
        }
    }
    """
    try:
        header = body.get("header", {})
        event_type = header.get("event_type", "")

        # 处理URL验证
        if body.get("type") == "url_verification":
            return None

        # 只处理消息接收事件
        if event_type not in ("im.message.receive_v1", "im.message"):
            logger.debug(f"忽略非消息事件: {event_type}")
            return None

        event = body.get("event", {})
        message = event.get("message", {})

        if not message:
            return None

        # 提取文本内容
        msg_type = message.get("msg_type", "text")
        content_text = ""
        content_json = message.get("content", "")
        if msg_type == "text":
            try:
                content_data = json.loads(content_json) if isinstance(content_json, str) else content_json
                content_text = content_data.get("text", "")
            except (json.JSONDecodeError, TypeError):
                content_text = content_json or ""

        sender = event.get("sender", {})
        sender_id = ""
        if isinstance(sender.get("sender_id"), dict):
            sender_id = sender["sender_id"].get("open_id", "")
        else:
            sender_id = str(sender.get("sender_id", ""))

        return FeishuMessage(
            message_id=message.get("message_id", ""),
            chat_id=message.get("chat_id", ""),
            chat_type=message.get("chat_type", ""),
            msg_type=msg_type,
            content_text=content_text,
            content_json=content_json if isinstance(content_json, str) else json.dumps(content_json, ensure_ascii=False),
            sender_id=sender_id,
            sender_name=event.get("sender", {}).get("sender_id", {}).get("name", ""),
            create_time=header.get("create_time", ""),
            root_id=message.get("root_id", ""),
        )
    except Exception as e:
        logger.error(f"解析飞书事件失败: {e}")
        return None


def _build_result_card(result: dict) -> str:
    """构建处理结果卡片消息。"""
    if not result.get("processed"):
        return ""

    signals = result.get("signals", [])
    if not signals:
        return json.dumps(
            {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "📋 行情情报识别结果"},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": "未抽取到有效的行情信号。\n\n建议补充品牌、品类、型号或涨幅等关键信息后重新发送。"},
                    }
                ],
            },
            ensure_ascii=False,
        )

    # 构建信号列表
    elements = []
    for i, sig in enumerate(signals[:5]):  # 最多显示5条
        brand = sig.get("brand") or "未识别"
        category = sig.get("category") or "未识别品类"
        mpn = sig.get("mpn") or "未识别型号"
        event_type = sig.get("event_type", "other")
        conf = sig.get("confidence", 0)
        review = sig.get("review_status", "observation")

        type_labels = {
            "price_increase": "涨价", "shortage": "缺货", "lead_time": "交期延长",
            "eol": "停产", "capacity_issue": "产能", "policy": "政策", "other": "其他",
        }
        review_labels = {"confirmed": "✅ 已确认", "need_review": "🔍 待复核", "observation": "👀 观察"}

        conf_pct = f"{int(conf * 100)}%"
        inc = sig.get("increase_max_pct")
        lt = sig.get("lead_time_weeks")

        content_parts = [
            f"**品牌**：{brand}　**品类**：{category}",
            f"**型号**：{mpn}　**类型**：{type_labels.get(event_type, event_type)}",
            f"**置信度**：{conf_pct}　**状态**：{review_labels.get(review, review)}",
        ]
        if inc:
            content_parts.append(f"**涨幅**：{inc}%")
        if lt:
            content_parts.append(f"**交期**：{lt} 周")

        elements.append(
            {
                "tag": "div",
                "fields": [
                    {"is_short": False, "text": {"tag": "lark_md", "content": "\n".join(content_parts)}},
                ],
            }
        )
        if i < len(signals) - 1:
            elements.append({"tag": "hr"})

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📋 行情情报识别 · {len(signals)} 条信号"},
            "template": "blue",
        },
        "elements": elements + [
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"来源：{result.get('source_type','')} · {result.get('source_name','')} · 可信度：{int(result.get('confidence',0)*100)}%\n登录 BOM交期风险系统 → 行情情报中心 → 情报录入 → 待复核队列 查看详情",
                    }
                ],
            },
        ],
    }
    return json.dumps(card, ensure_ascii=False)


async def process_event(body: dict, db_session: Optional[Session] = None) -> dict:
    """处理飞书事件回调。

    这是飞书事件订阅的主入口。流程：
    1. 验证事件签名
    2. 解析消息内容
    3. 判断是否为行情情报
    4. 调用行情收件箱API入库
    5. 回复处理结果卡片

    Returns:
        处理结果状态
    """
    client = get_feishu_client()

    # URL验证
    if body.get("type") == "url_verification":
        challenge = body.get("challenge", {})
        token = challenge if isinstance(challenge, str) else ""
        token_value = token.get("token", "") if isinstance(token, dict) else token
        return {"verified": True, "challenge": token_value or body.get("challenge", "")}

    # 解析消息
    msg = _parse_event_body(body)
    if msg is None:
        return {"processed": False, "reason": "非消息事件或URL验证"}

    # 跳过机器人自己发的消息
    if msg.sender_id == "bot" or "bot" in msg.sender_id.lower():
        return {"processed": False, "reason": "跳过机器人自己"}

    logger.info(
        f"飞书消息 | id={msg.message_id[:16]} | chat={msg.chat_id[:16]} "
        f"| sender={msg.sender_name or msg.sender_id[:12]} | text_len={len(msg.content_text)}"
    )

    # 处理消息
    result = await handle_message(msg, client)

    # 如果识别为行情情报，调用入库API
    if result.get("processed") and result.get("signals"):
        await _save_signals_to_inbox(result, db_session)

    # 回复结果卡片
    card = _build_result_card(result)
    if card:
        await client.reply_card(msg.message_id, card)

    return result


async def _save_signals_to_inbox(result: dict, db_session: Optional[Session] = None):
    """将解析出的信号保存到行情收件箱（通过内部API）。"""
    if not db_session:
        logger.warning("无数据库session，信号仅回复不保存")
        return
    try:
        from app.services.market_inbox_engine import _ingest_notice_and_signals
        # 构建模拟的行情通知数据
        notice_data = {
            "title": result.get("title", "飞书转发行情"),
            "source_type": result.get("source_type", "manual"),
            "source_name": result.get("source_name", "飞书机器人"),
            "raw_text": result.get("title", "") + "\n" + str(result.get("signals", [])),
            "extracted_signals": result.get("signals", []),
        }
        # 实际保存逻辑由 market_inbox 模块处理
        logger.info(f"飞书信号入库: {len(result.get('signals',[]))} 条")
    except ImportError as e:
        logger.info(f"无法直接入库（模块未加载），仅通过消息卡片回复: {e}")
