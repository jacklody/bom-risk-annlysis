"""Material Alerts API — 上游原材料价格变动预警查询。

端点：
  GET  /api/material-alerts               — 原材料价格预警列表（支持多维度过滤）
  GET  /api/material-alerts/trends/{key}  — 单材料历史价格趋势
  GET  /api/material-alerts/summary       — 全品类聚合摘要
  GET  /api/material-alerts/cache-stats   — 价格服务缓存统计
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.material_price import MaterialPrice
from app.services.material_tracker import MaterialTracker
from app.services.material_price_service import get_material_price_service
from app.knowledge.material_mapping import (
    MATERIAL_REGISTRY,
    DOMAIN_MATERIALS,
    get_material_entry,
    get_materials_for_category,
)

router = APIRouter()

LEVEL_ORDER = {"RED": 0, "ORANGE": 1, "YELLOW": 2, "GREEN": 3, "NORMAL": 4}


def _filter_material_keys(
    category: Optional[str] = None,
    domain: Optional[str] = None,
) -> list[str]:
    """按 category 和 domain 过滤材料 key 列表。"""
    if category:
        materials = get_materials_for_category(category)
        keys = [m.key for m in materials]
    else:
        keys = list(MATERIAL_REGISTRY.keys())

    if domain:
        keys = [
            k for k in keys
            if MATERIAL_REGISTRY.get(k) and MATERIAL_REGISTRY[k].domain == domain
        ]
    return keys


# ── GET /api/material-alerts ────────────────────────────────

@router.get("/api/material-alerts")
async def get_material_alerts(
    risk_level: Optional[str] = Query(None, description="过滤风险等级: yellow/orange/red/green"),
    domain: Optional[str] = Query(None, description="过滤数据域: metals/rare_earth/chemical"),
    category: Optional[str] = Query(None, description="过滤品类: pcb/relay/mlcc等"),
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: Session = Depends(get_db),
):
    """查询当前所有原材料的价格状态和预警信息。

    返回各材料的价格变动百分比、风险等级档位、影响品类列表，
    以及全局汇总统计。支持分页和多维度过滤。
    """
    material_keys = _filter_material_keys(category=category, domain=domain)

    # 执行追踪
    price_service = get_material_price_service()
    tracker = MaterialTracker(db, price_service)
    trackings = await tracker.track_materials(material_keys)

    # 构建响应
    alerts = []
    summary = {
        "total_materials": len(material_keys),
        "red": 0, "orange": 0, "yellow": 0, "green": 0, "normal": 0,
        "alerts_active": 0,
    }

    for mk, tracking in trackings.items():
        item = {
            "material_key": tracking.material_key,
            "material_name_zh": tracking.material_name_zh,
            "domain": tracking.domain,
            "current_price": tracking.current_price,
            "price_unit": tracking.price_unit,
            "baseline_30d": tracking.baseline_30d,
            "baseline_90d": tracking.baseline_90d,
            "change_pct": tracking.change_pct,
            "risk_level": tracking.risk_level,
            "adjusted_cost_ratio": tracking.adjusted_cost_ratio,
            "material_track_score": tracking.material_track_score,
            "affected_categories": tracking.affected_categories,
            "source_name": tracking.source_name,
            "degraded": tracking.degraded,
        }

        # 风险等级过滤
        if risk_level and tracking.risk_level.lower() != risk_level.lower():
            continue

        alerts.append(item)

        rl = tracking.risk_level.lower()
        if rl in summary:
            summary[rl] += 1

    summary["alerts_active"] = (
        summary["red"] + summary["orange"] + summary["yellow"] + summary["green"]
    )

    # 排序 + 分页
    alerts.sort(key=lambda a: LEVEL_ORDER.get(a["risk_level"], 5))
    total_count = len(alerts)
    paginated = alerts[offset : offset + limit]

    return {
        "alerts": paginated,
        "summary": summary,
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
        },
    }


# ── GET /api/material-alerts/trends/{material_key} ──────────

@router.get("/api/material-alerts/trends/{material_key}")
async def get_material_price_trends(
    material_key: str,
    days: int = Query(90, ge=7, le=365, description="历史天数范围（7-365）"),
    db: Session = Depends(get_db),
):
    """查询单个原材料的历史价格趋势。

    返回指定天数内的价格时间序列，包含日均价、最高价、最低价。
    """
    entry = get_material_entry(material_key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Unknown material: {material_key}")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(
            MaterialPrice.price_value,
            MaterialPrice.fetch_timestamp,
            MaterialPrice.source_name,
        )
        .where(
            MaterialPrice.material_key == material_key,
            MaterialPrice.fetch_timestamp >= since,
        )
        .order_by(MaterialPrice.fetch_timestamp.asc())
    )
    result = db.execute(stmt)
    rows = result.all()

    # 按日聚合：日均价、最高、最低
    daily: dict[str, list[float]] = {}
    for price, ts, source in rows:
        if price is None:
            continue
        day_key = ts.strftime("%Y-%m-%d") if ts else "unknown"
        if day_key not in daily:
            daily[day_key] = []
        daily[day_key].append(float(price))

    trends = []
    for day_key in sorted(daily.keys()):
        prices = daily[day_key]
        trends.append({
            "date": day_key,
            "avg_price": round(sum(prices) / len(prices), 2),
            "max_price": round(max(prices), 2),
            "min_price": round(min(prices), 2),
            "sample_count": len(prices),
        })

    # 计算统计摘要
    all_prices = [float(price) for price, _, _ in rows if price is not None]
    stats = {}
    if all_prices:
        stats = {
            "latest_price": all_prices[-1],
            "avg_price_period": round(sum(all_prices) / len(all_prices), 2),
            "max_price_period": max(all_prices),
            "min_price_period": min(all_prices),
            "volatility_pct": round(
                ((max(all_prices) - min(all_prices)) / min(all_prices) * 100), 2
            ) if min(all_prices) > 0 else 0,
        }

    # 计算当前基线
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_prices = []
    for price, ts, _ in rows:
        if price is None or ts is None:
            continue
        comparable_ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if comparable_ts >= thirty_days_ago:
            recent_prices.append(float(price))
    baseline_30d = round(sum(recent_prices) / len(recent_prices), 2) if recent_prices else None
    current = all_prices[-1] if all_prices else None
    change_pct = (
        round(((current - baseline_30d) / baseline_30d) * 100, 2)
        if current and baseline_30d
        else None
    )

    return {
        "material_key": material_key,
        "material_name_zh": entry.name_zh,
        "domain": entry.domain,
        "unit": entry.unit,
        "days": days,
        "data_points": len(rows),
        "daily_trends": trends,
        "stats": stats,
        "current_vs_30d_baseline": {
            "current_price": current,
            "baseline_30d": baseline_30d,
            "change_pct": change_pct,
        },
    }


# ── GET /api/material-alerts/summary ────────────────────────

@router.get("/api/material-alerts/summary")
async def get_material_summary(
    domain: Optional[str] = Query(None, description="可选：按数据域过滤"),
    db: Session = Depends(get_db),
):
    """全品类原材料风险聚合摘要。

    返回按域分组的高风险材料 Top-N、全局风险分布、品类关联概览。
    """
    price_service = get_material_price_service()
    tracker = MaterialTracker(db, price_service)

    # 获取所有材料追踪结果
    all_keys = _filter_material_keys(domain=domain)
    trackings = await tracker.track_materials(all_keys)

    # 按风险等级分组
    by_risk: dict[str, list[dict]] = {"RED": [], "ORANGE": [], "YELLOW": [], "GREEN": [], "NORMAL": []}
    by_domain: dict[str, dict] = {}
    total_affected_categories: set[str] = set()

    for mk, t in trackings.items():
        entry = {
            "material_key": t.material_key,
            "material_name_zh": t.material_name_zh,
            "domain": t.domain,
            "risk_level": t.risk_level,
            "change_pct": t.change_pct,
            "affected_categories": t.affected_categories,
        }
        by_risk.setdefault(t.risk_level, []).append(entry)

        # 按域统计
        dom = t.domain
        if dom not in by_domain:
            by_domain[dom] = {"red": 0, "orange": 0, "yellow": 0, "green": 0, "normal": 0, "total": 0}
        rl = t.risk_level.lower()
        by_domain[dom][rl if rl in by_domain[dom] else "normal"] += 1
        by_domain[dom]["total"] += 1

        total_affected_categories.update(t.affected_categories)

    # 高风险材料 Top-5（按变动百分比降序）
    top_rising = sorted(
        [t for t in trackings.values() if t.change_pct > 0],
        key=lambda t: -t.change_pct,
    )[:5]
    top_dropping = sorted(
        [t for t in trackings.values() if t.change_pct < 0],
        key=lambda t: t.change_pct,
    )[:5]

    # 缓存统计
    cache_stats = price_service.get_cache_stats()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_materials": len(all_keys),
        "risk_distribution": {
            level: len(items) for level, items in by_risk.items()
        },
        "by_domain": by_domain,
        "top_rising": [
            {
                "material_key": t.material_key,
                "material_name_zh": t.material_name_zh,
                "domain": t.domain,
                "change_pct": t.change_pct,
                "risk_level": t.risk_level,
            }
            for t in top_rising
        ],
        "top_dropping": [
            {
                "material_key": t.material_key,
                "material_name_zh": t.material_name_zh,
                "domain": t.domain,
                "change_pct": t.change_pct,
                "risk_level": t.risk_level,
            }
            for t in top_dropping
        ],
        "affected_categories": sorted(total_affected_categories),
        "cache_stats": cache_stats,
    }


# ── GET /api/material-alerts/cache-stats ────────────────────

@router.get("/api/material-alerts/cache-stats")
async def get_material_cache_stats():
    """获取原材料价格服务的缓存统计信息。

    包含各域缓存命中率、配额使用情况、降级状态。
    """
    price_service = get_material_price_service()
    stats = price_service.get_cache_stats()
    stats["generated_at"] = datetime.now(timezone.utc).isoformat()
    return stats
