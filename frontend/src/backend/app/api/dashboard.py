from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.bom import BomItem
from app.models.event import MarketEvent
from app.services.dashboard_notification import (
    build_dashboard_notification_preview,
    list_dashboard_notification_history,
    list_notification_channels,
    prepare_dashboard_notification_dispatch,
)
from app.services.dashboard_summary import build_dashboard_summary
from app.services.upstream.propagation_rules import CATEGORY_MODEL_WEIGHTS

router = APIRouter()


class NotificationDispatchRequest(BaseModel):
    channel: str = "manual"
    idempotency_key: str | None = None


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    return build_dashboard_summary(db)


# ── 双轨风险看板 ──
@router.get("/dual-track")
def get_dual_track_board(db: Session = Depends(get_db)):
    """返回双轨风险看板所需的结构化数据：
    - material_chains: 材料传导链（铜→PCB/连接器/电感、银→继电器 等）
    - demand_signals: 供需信号（交期拉长、库存下降、同行联动）
    统计来自实际数据库中的 BOM 物料风险分布和市场事件。
    """
    # 1. 统计各品类的风险物料数
    category_stats = {}
    rows = db.execute(
        "SELECT normalized_category, COUNT(*) as cnt, "
        "SUM(CASE WHEN risk_level IN ('red','orange') THEN 1 ELSE 0 END) as high_risk "
        "FROM bom_items WHERE normalized_category IS NOT NULL AND normalized_category != 'unknown' "
        "GROUP BY normalized_category"
    ).fetchall()
    for row in rows:
        category_stats[row[0]] = {"item_count": row[1], "high_risk_count": row[2] or 0}

    # 2. 统计各品类影响的项目数
    project_stats = {}
    proj_rows = db.execute(
        "SELECT normalized_category, COUNT(DISTINCT project_id) as proj_cnt "
        "FROM bom_items WHERE normalized_category IS NOT NULL AND normalized_category != 'unknown' "
        "GROUP BY normalized_category"
    ).fetchall()
    for row in proj_rows:
        project_stats[row[0]] = row[1] or 0

    # 3. 活跃市场事件统计
    active_events = db.query(MarketEvent).filter(
        MarketEvent.is_active == True
    ).order_by(MarketEvent.created_at.desc()).limit(20).all()

    # 按品类分组事件
    event_by_category = {}
    for evt in active_events:
        cat = getattr(evt, "category", "") or "unknown"
        if cat not in event_by_category:
            event_by_category[cat] = []
        event_by_category[cat].append({
            "id": evt.id,
            "title": getattr(evt, "raw_title", "") or getattr(evt, "title", ""),
            "brand": getattr(evt, "brand", ""),
            "event_type": getattr(evt, "event_type", ""),
            "severity": getattr(evt, "severity", ""),
            "source_name": getattr(evt, "source_name", ""),
            "estimated_price_impact_pct": getattr(evt, "estimated_price_impact_pct", None),
            "estimated_lead_time_impact_weeks": getattr(evt, "estimated_lead_time_impact_weeks", None),
        })

    # 4. 构建材料传导链（从品类权重表 + 实际统计数据）
    material_chains_config = {
        "copper": {
            "material": "铜", "material_alert": True,
            "chains": [
                {"key": "pcb", "mid_node": "铜箔→覆铜板", "category": "PCB", "pass_through": "60%-80%", "lag": "1-3月"},
                {"key": "connector", "mid_node": "铜合金端子", "category": "连接器", "pass_through": "20%-40%", "lag": "3-6月"},
                {"key": "inductor_transformer", "mid_node": "漆包线", "category": "电感/变压器", "pass_through": "50%-70%", "lag": "2-4月"},
                {"key": "wire_harness", "mid_node": "铜线材", "category": "线束", "pass_through": "60%-80%", "lag": "2-4月"},
            ]
        },
        "silver": {
            "material": "银", "material_alert": True,
            "chains": [
                {"key": "relay", "mid_node": "银触点(AgSnO₂)", "category": "继电器", "pass_through": "30%-50%", "lag": "2-4月"},
                {"key": "varistor_thermistor", "mid_node": "银电极", "category": "压敏/热敏", "pass_through": "20%-35%", "lag": "3-6月"},
            ]
        },
        "aluminum": {
            "material": "铝", "material_alert": False,
            "chains": [
                {"key": "aluminum_electrolytic_capacitor", "mid_node": "电极箔", "category": "铝电解电容", "pass_through": "40%-60%", "lag": "3-6月"},
            ]
        },
    }

    material_chains = []
    for mat_key, mat_conf in material_chains_config.items():
        for chain in mat_conf["chains"]:
            stats = category_stats.get(chain["key"], {})
            chain_data = {
                **chain,
                "material": mat_conf["material"],
                "material_alert": mat_conf["material_alert"],
                "item_count": stats.get("item_count", 0),
                "high_risk_count": stats.get("high_risk_count", 0),
                "project_count": project_stats.get(chain["key"], 0),
                "risk_level": "red" if stats.get("high_risk_count", 0) > 0 else "yellow" if stats.get("item_count", 0) > 0 else "green",
                "events": event_by_category.get(chain["key"], []),
            }
            material_chains.append(chain_data)

    # 5. 构建供需信号
    demand_signals = []
    # 从活跃事件中提取供需信号
    for evt in active_events:
        severity = getattr(evt, "severity", "")
        event_type = getattr(evt, "event_type", "")
        if severity in ("critical", "high") and event_type in ("shortage", "price_increase", "lead_time"):
            demand_signals.append({
                "category": getattr(evt, "category", "") or "unknown",
                "severity": severity,
                "title": getattr(evt, "raw_title", "") or getattr(evt, "title", ""),
                "event_type": event_type,
                "evidence": f"来源: {getattr(evt, 'source_name', '未知')}",
                "item_count": category_stats.get(getattr(evt, "category", ""), {}).get("item_count", 0),
                "project_count": project_stats.get(getattr(evt, "category", ""), 0),
            })

    # 去重（同类事件合并）
    seen = set()
    unique_signals = []
    for sig in demand_signals:
        key = (sig["category"], sig["event_type"])
        if key not in seen:
            seen.add(key)
            unique_signals.append(sig)

    return {
        "material_chains": material_chains,
        "demand_signals": unique_signals[:10],  # 最多10条
    }


@router.get("/notification/channels")
def get_dashboard_notification_channels():
    return list_notification_channels()


@router.get("/notification/preview")
def get_dashboard_notification_preview(channel: str = "manual", db: Session = Depends(get_db)):
    return build_dashboard_notification_preview(db, channel=channel)


@router.post("/notification/dispatch")
def dispatch_dashboard_notification(payload: NotificationDispatchRequest, db: Session = Depends(get_db)):
    return prepare_dashboard_notification_dispatch(db, channel=payload.channel, idempotency_key=payload.idempotency_key)


@router.get("/notification/history")
def get_dashboard_notification_history(limit: int = 20, db: Session = Depends(get_db)):
    return list_dashboard_notification_history(db, limit=limit)
