"""WebSocket 实时原材料预警推送。

端点：
  WS /api/material-alerts/ws  — 实时推送材料价格变动与预警事件

推送机制：
  - 每 60s 从缓存轮询各材料最新价格，与上一次快照比对
  - 价格变动超过阈值（≥5%）或风险等级变化时推送
  - 客户端可发送 {"action": "subscribe", "materials": ["cu_cathode", ...]} 定制订阅
  - 支持心跳保活（30s ping/pong）
"""

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.knowledge.material_mapping import MATERIAL_REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局价格快照 {material_key: {"price": float, "risk_level": str, "ts": float}}
_price_snapshot: dict[str, dict] = {}
_ws_poll_interval: float = 60.0  # 秒
_ws_change_threshold: float = 5.0  # 价格变动阈值 (%)


def _get_current_snapshot() -> dict[str, dict]:
    """从全局 singleton MaterialPriceService 缓存读取当前价格快照。"""
    try:
        from app.services.material_price_service import get_material_price_service
        svc = get_material_price_service()
        cache = svc.get_cached_prices()  # {key: {price, unit, source, timestamp, degraded}}
        snapshot = {}
        for key, entry in cache.items():
            reg = MATERIAL_REGISTRY.get(key)
            if not reg:
                continue
            snapshot[key] = {
                "price": entry["price"],
                "unit": entry.get("unit", reg.unit),
                "source": entry.get("source", "unknown"),
                "ts": entry.get("timestamp", time.time()),
                "degraded": entry.get("degraded", False),
            }
        return snapshot
    except Exception as e:
        logger.warning(f"WS snapshot read failed: {e}")
        return {}


def _compute_risk_level(material_key: str, current_price: float) -> str:
    """根据当前价格与缓存基线计算风险等级（简化版，无 DB）。"""
    old = _price_snapshot.get(material_key, {})
    old_price = old.get("price")
    if old_price and old_price > 0:
        change_pct = ((current_price - old_price) / old_price) * 100
    else:
        return "NORMAL"

    if change_pct >= 20:
        return "RED"
    elif change_pct >= 10:
        return "ORANGE"
    elif change_pct >= 5:
        return "YELLOW"
    elif change_pct <= -10:
        return "GREEN"
    return "NORMAL"


def _diff_snapshots(old_snap: dict, new_snap: dict) -> list[dict]:
    """比对两次快照，返回有价差或风险等级变化的材料列表。"""
    events = []
    for key in set(old_snap.keys()) | set(new_snap.keys()):
        old_entry = old_snap.get(key, {})
        new_entry = new_snap.get(key, {})

        old_price = old_entry.get("price")
        new_price = new_entry.get("price")

        if old_price is None or new_price is None:
            continue

        if old_price == 0:
            continue

        change_pct = ((new_price - old_price) / old_price) * 100
        old_risk = old_entry.get("risk_level", "NORMAL")
        new_risk = new_entry.get("risk_level", "NORMAL")

        if abs(change_pct) >= _ws_change_threshold or old_risk != new_risk:
            reg = MATERIAL_REGISTRY.get(key)
            events.append({
                "type": "price_update" if abs(change_pct) >= _ws_change_threshold else "risk_change",
                "material_key": key,
                "material_name_zh": reg.name_zh if reg else key,
                "domain": reg.domain if reg else "unknown",
                "old_price": round(old_price, 2),
                "new_price": round(new_price, 2),
                "change_pct": round(change_pct, 2),
                "old_risk": old_risk,
                "new_risk": new_risk,
                "unit": new_entry.get("unit", ""),
                "source": new_entry.get("source", "unknown"),
                "ts": time.time(),
            })
    return events


@router.websocket("/api/material-alerts/ws")
async def material_alerts_websocket(websocket: WebSocket):
    """实时推送原材料预警。

    客户端可发送：
      {"action": "subscribe", "materials": ["cu_cathode", "al_ingot"]}  — 订阅特定材料
      {"action": "unsubscribe"}                                           — 取消订阅，接收全部
      {"action": "ping"}                                                  — 心跳
    """
    await websocket.accept()
    logger.info("Material WebSocket client connected")

    subscribed: Optional[set[str]] = None  # None = 全部订阅
    last_snapshot = _get_current_snapshot()

    # 为快照补充 risk_level
    for key, entry in last_snapshot.items():
        entry["risk_level"] = _compute_risk_level(key, entry["price"])

    _price_snapshot.clear()
    _price_snapshot.update(last_snapshot)

    try:
        # 发送初始摘要
        await websocket.send_json({
            "type": "init",
            "materials_count": len(last_snapshot),
            "domains": {
                domain: len([k for k in last_snapshot
                            if MATERIAL_REGISTRY.get(k) and MATERIAL_REGISTRY[k].domain == domain])
                for domain in ["metals", "rare_earth", "chemical"]
            },
            "ts": time.time(),
        })

        async def poll_task():
            """后台轮询任务。"""
            nonlocal last_snapshot
            while True:
                await asyncio.sleep(_ws_poll_interval)
                try:
                    new_snap = _get_current_snapshot()
                    for key, entry in new_snap.items():
                        entry["risk_level"] = _compute_risk_level(key, entry["price"])

                    events = _diff_snapshots(last_snapshot, new_snap)

                    # 更新快照
                    _price_snapshot.clear()
                    _price_snapshot.update(new_snap)
                    last_snapshot = new_snap

                    # 按订阅过滤推送
                    for event in events:
                        if subscribed is None or event["material_key"] in subscribed:
                            await websocket.send_json(event)

                    # 汇总推送（批量）
                    if events:
                        filtered = [e for e in events
                                   if subscribed is None or e["material_key"] in subscribed]
                        if filtered:
                            red_count = sum(1 for e in filtered if e["new_risk"] == "RED")
                            orange_count = sum(1 for e in filtered if e["new_risk"] == "ORANGE")
                            await websocket.send_json({
                                "type": "batch_summary",
                                "event_count": len(filtered),
                                "red": red_count,
                                "orange": orange_count,
                                "ts": time.time(),
                            })
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.warning(f"WS poll error: {e}")

        # 启动后台轮询
        poll_future = asyncio.create_task(poll_task())

        # 主循环：处理客户端消息
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
                msg = json.loads(data)
                action = msg.get("action", "")

                if action == "subscribe":
                    materials = msg.get("materials", [])
                    subscribed = set(materials) if materials else None
                    await websocket.send_json({
                        "type": "subscribed",
                        "count": len(subscribed) if subscribed else "all",
                    })

                elif action == "unsubscribe":
                    subscribed = None
                    await websocket.send_json({"type": "unsubscribed"})

                elif action == "ping":
                    await websocket.send_json({"type": "pong", "ts": time.time()})

            except asyncio.TimeoutError:
                # 30s 无消息，发心跳
                await websocket.send_json({"type": "pong", "ts": time.time()})

    except WebSocketDisconnect:
        logger.info("Material WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        poll_future.cancel()
        try:
            await poll_future
        except asyncio.CancelledError:
            pass
