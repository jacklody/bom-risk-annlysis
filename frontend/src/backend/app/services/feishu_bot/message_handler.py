"""飞书机器人消息处理 — 识别行情情报、转发到行情收件箱。"""

from __future__ import annotations

import logging
from typing import Optional

from app.services.upstream.market_notice_parser import parse_market_notice
from app.services.feishu_bot.feishu_client import FeishuClient, FeishuMessage

logger = logging.getLogger(__name__)

# ── 识别关键词：判断是否可能是行情情报 ──
MARKET_KEYWORDS = [
    # 涨价
    "涨价", "调价", "涨价函", "价格上调", "提价", "涨幅", "报价上升",
    # 缺货
    "缺货", "断货", "短缺", "紧缺", "供应不足", "无货", "停供",
    # 交期
    "交期拉长", "交期延长", "交期紧张", "lead time", "排产", "产能不足",
    # 停产
    "停产", "EOL", "NRND", "不推荐新设计", "Last Time Buy", "PCN", "PDN",
    # 关税/政策
    "关税", "出口管制", "制裁", "实体清单", "反倾销", "禁运",
    # 灾害/事件
    "火灾", "地震", "海啸", "罢工", "停电", "停工", "台风",
    # 品牌/品类
    "MLCC", "MCU", "IGBT", "MOSFET", "DRAM", "PCB",
    "村田", "TDK", "国巨", "三星电机", "风华", "华新科",
    "ST", "TI", "英飞凌", "NXP", "瑞萨", "微芯", "Microchip",
    "兆易", "中微", "国民技术", "圣邦微", "MPS",
]

# ── 快速判断置信度 ──
HIGH_CONFIDENCE_SOURCES = [
    "涨价函", "原厂通知", "经销商通知", "代理商通知",
    "官网公告", "investor relations", "财报",
]

LOW_CONFIDENCE_SOURCES = [
    "微信群", "朋友圈", "公众号", "据说", "传闻",
    "可能", "听说", "消息人士", "业内人士",
]


def _extract_text(msg: FeishuMessage) -> str:
    """从各种消息类型中提取纯文本。"""
    text = msg.get_text()
    if not text:
        # 尝试从原始JSON中提取
        try:
            import json
            data = json.loads(msg.content_json) if msg.content_json else {}
            # 富文本可能有嵌套的text
            if isinstance(data, dict):
                text = json.dumps(data, ensure_ascii=False)
        except Exception:
            text = msg.content_json or ""
    return text.strip()


def is_market_intelligence(text: str) -> bool:
    """判断文本是否包含行情情报。"""
    if not text or len(text) < 15:
        return False
    hits = sum(1 for kw in MARKET_KEYWORDS if kw.lower() in text.lower())
    return hits >= 2  # 至少命中2个关键词


def assess_source_confidence(text: str, msg: FeishuMessage) -> tuple[float, str]:
    """评估消息来源可信度。

    Returns:
        (置信度系数 0-1, 原因说明)
    """
    base = 0.50

    # 高可信来源
    if any(kw in text for kw in HIGH_CONFIDENCE_SOURCES):
        base += 0.30

    # 低可信来源降权
    if any(kw in text for kw in LOW_CONFIDENCE_SOURCES):
        base -= 0.20

    # 转发消息比原创降权
    if "转发" in text or "forward" in text.lower():
        base -= 0.05

    # 有具体数据加分
    import re
    if re.search(r'\d+[%％]', text):  # 涨幅百分比
        base += 0.10
    if re.search(r'\d+\s*周', text):  # 交期周数
        base += 0.10

    # 有型号加分
    if re.search(r'[A-Z]{2,}\d{2,}[A-Z]*\d*', text):
        base += 0.10

    base = max(0.15, min(0.95, base))

    reasons = []
    if base >= 0.75:
        reasons.append("来源可信度较高")
    elif base >= 0.50:
        reasons.append("来源可信度中等")
    else:
        reasons.append("来源可信度较低，进入观察")

    return base, "；".join(reasons)


def detect_source_type(msg: FeishuMessage, text: str) -> str:
    """检测消息来源类型。"""
    text_lower = text.lower()
    if "微信公众号" in text or "mp.weixin.qq.com" in text_lower:
        return "wechat_mp"
    if "邮件" in text or "email" in text_lower:
        return "email"
    if "官网" in text or "公告" in text or "investor" in text_lower:
        return "website"
    if "通知" in text or "涨价函" in text:
        return "supplier_notice"
    return "manual"


async def handle_message(
    msg: FeishuMessage,
    feishu_client: FeishuClient,
) -> dict:
    """处理飞书消息，识别行情情报并入库。

    返回处理结果摘要。
    """
    text = _extract_text(msg)

    if not is_market_intelligence(text):
        logger.info(f"飞书消息 {msg.message_id[:12]} 未识别为行情情报，跳过")
        return {"processed": False, "reason": "未识别为行情情报"}

    logger.info(f"飞书消息 {msg.message_id[:12]} 识别为行情情报，开始解析...")

    # 1. 评估来源可信度
    confidence, reason = assess_source_confidence(text, msg)

    # 2. 检测来源类型
    source_type = detect_source_type(msg, text)
    source_name = f"飞书群-{msg.sender_name or msg.sender_id[:8]}"

    # 3. 使用现有解析器抽取信号
    title = text[:80].replace("\n", " ")
    signals = parse_market_notice(
        raw_text=text,
        title=title,
        source_type=source_type,
        source_name=source_name,
    )

    # 4. 调整信号置信度
    for signal in signals:
        original = signal.confidence
        signal.confidence = round(original * confidence, 2)
        signal.confidence_reason = (
            f"{signal.confidence_reason or ''}；飞书机器人识别，{reason}"
        ).strip("；")

        # 公众号来源额外降权（PRD v3.2 要求）
        if source_type == "wechat_mp":
            signal.confidence = round(signal.confidence * 0.6, 2)
            signal.confidence_reason += "；公众号/社交来源降权"

        # 低置信度不自动生成事件
        if signal.confidence < 0.40:
            signal.review_status = "observation"
        elif signal.confidence >= 0.70:
            signal.review_status = "confirmed"
        else:
            signal.review_status = "need_review"

    return {
        "processed": True,
        "signals_count": len(signals),
        "signals": [s.to_dict() for s in signals],
        "source_type": source_type,
        "source_name": source_name,
        "confidence": confidence,
        "confidence_reason": reason,
        "title": title,
        "text_length": len(text),
    }
