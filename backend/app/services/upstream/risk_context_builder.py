from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.config import settings
from app.services.upstream.category_classifier import classify_component_category
from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk
from app.services.upstream.evidence_chain_builder import build_evidence_chain
from app.services.upstream.manual_event_service import extract_market_facts_from_events

logger = logging.getLogger(__name__)

# 模块级 material_tracker 引用（惰性注入，避免循环导入）
_material_tracker: Optional[Any] = None


def set_material_tracker(tracker):
    """注入 MaterialTracker 实例。在 main.py lifespan 中调用。"""
    global _material_tracker
    _material_tracker = tracker


def _lead_time_weeks_from_realtime(realtime_data: dict) -> int | None:
    lead_time_days = realtime_data.get("lead_time_days")
    if lead_time_days is None:
        return None
    try:
        return int(round(float(lead_time_days) / 7))
    except (TypeError, ValueError):
        return None


def _body_signals(realtime_data: dict, market_facts: dict) -> dict:
    lead_time_weeks = market_facts.get("lead_time_weeks") or _lead_time_weeks_from_realtime(realtime_data)
    total_stock = realtime_data.get("total_stock")
    return {
        "stock_down": bool(total_stock == 0 or realtime_data.get("stock_down")),
        "lead_time_weeks": lead_time_weeks,
        # v3.3: 新增实时数据维度
        "supplier_count": realtime_data.get("supplier_count", 0) or 0,
        "lifecycle_status": realtime_data.get("lifecycle_status") or "Unknown",
    }


def _material_signals_for_category(category: str, market_facts: dict) -> dict:
    """获取品类级原材料信号。

    优先使用 MaterialTracker 的实时价格变动数据（百分比 × 传导系数）。
    若 MaterialTracker 不可用或材料追踪未启用，退化为市场事实推断的布尔信号。
    """
    # v3.4: 优先使用 MaterialTracker 实时价格数据
    if settings.material_tracking_enabled and _material_tracker is not None:
        try:
            return _material_signals_from_tracker(category)
        except Exception as e:
            logger.warning(f"MaterialTracker failed for category '{category}': {e}, falling back to market facts")

    # ═══ 退化路径：从 market_facts 推断 ═══
    if category == "high_cap_mlcc":
        return {"ceramic_powder_pressure": bool(market_facts.get("price_up_confirmed") or market_facts.get("shortage_confirmed"))}
    if category == "pcb":
        return {"copper_foil_price_up": bool(market_facts.get("price_up_confirmed"))}
    if category in {"mcu", "power_ic"}:
        return {"silicon_wafer_price_up": bool(market_facts.get("price_up_confirmed"))}
    return {}


def _material_signals_from_tracker(category: str) -> Dict[str, float]:
    """从 MaterialTracker 同步获取品类材料价格信号。

    返回格式: {material_key_score: float, ...} 和 {material_key_risk: float, ...}
    供 dual_track_risk_engine 的 material_signals 字典使用。
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已有事件循环中运行（FastAPI 异步路径）
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                _material_tracker.track_for_category(category), loop
            )
            results = future.result(timeout=10.0)
        else:
            results = loop.run_until_complete(
                _material_tracker.track_for_category(category)
            )
    except RuntimeError:
        # 无线程安全事件循环，尝试 asyncio.run
        try:
            results = asyncio.run(_material_tracker.track_for_category(category))
        except RuntimeError:
            return {}

    signals: Dict[str, float] = {}
    for mk, tracking in results.items():
        if tracking.has_alert:
            signals[f"{mk}_score"] = tracking.material_track_score
            signals[f"{mk}_risk"] = 1.0 if tracking.risk_level in ("RED", "ORANGE") else 0.5

    return signals


def _buffers(commonality: dict) -> dict:
    return {
        "safety_stock_days": commonality.get("safety_stock_days", 0) or 0,
        "multi_source_available": bool(commonality.get("has_multi_source")),
        # v3.3: supplier_count 缓冲因子
        "supplier_count": commonality.get("supplier_count", 0) or 0,
    }


def build_v32_context(
    item: Any,
    events: list[Any] | None,
    realtime_data: dict | None,
    commonality: dict | None,
) -> dict:
    """构建单个 BOM 行的 v3.2 风险上下文。

    该函数保持纯服务层逻辑，供 FastAPI 接口和测试复用。
    """
    events = events or []
    realtime_data = realtime_data or {}
    commonality = commonality or {}

    description = " ".join(
        str(value or "")
        for value in [
            getattr(item, "normalized_category", ""),
            getattr(item, "raw_spec", ""),
            getattr(item, "raw_category", ""),
            getattr(item, "raw_part_number", ""),
        ]
    )
    manufacturer = getattr(item, "normalized_brand", None) or getattr(item, "raw_brand", "")
    category_result = classify_component_category(description, manufacturer=manufacturer)

    market_facts = extract_market_facts_from_events(events)
    body_signals = _body_signals(realtime_data, market_facts)
    material_signals = _material_signals_for_category(category_result.category, market_facts)
    buffers = _buffers(commonality)

    dual_track = evaluate_dual_track_risk(
        category=category_result.category,
        body_signals=body_signals,
        market_facts=market_facts,
        material_signals=material_signals,
        buffers=buffers,
    )
    evidence = build_evidence_chain(
        item=item,
        category_result=category_result,
        matched_events=events,
        dual_track_result=dual_track,
        realtime_data=realtime_data,
        buffers=buffers,
    )

    return {
        "v32_category": category_result.category,
        "v32_category_display": category_result.display_name,
        "v32_primary_track": dual_track.primary_track,
        "v32_track_scores": dual_track.track_scores,
        "v32_risk_level": dual_track.risk_level,
        "v32_risk_score": dual_track.total_score,
        "v32_evidence_chain": evidence.upstream_chain,
        "v32_evidence_summary": evidence.summary,
        "v32_action_suggestion": evidence.action_suggestion,
    }
