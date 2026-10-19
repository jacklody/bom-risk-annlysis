"""v3.5 依据链构建器 — 层级因果链。

从 v3.2 的扁平节点列表升级为层级因果链：
  原材料(raw_material) → 二级组份(mid_component) → 器件品类(device_category) → BOM物料(bom_item) → 处置建议(action)

每条链节点包含：
  - 名称/信号/来源/数据等级
  - 传导可靠性(verified/high_theory/theory/weak)
  - 转嫁率(pass_through)和滞后时间(lag)
  - 材料暴露系数和成本占比
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.upstream.propagation_rules import CATEGORY_MODEL_WEIGHTS


# ── 品类 → 上游材料层级映射（PRD v3.0 第4节 + 第8节）──

CATEGORY_UPSTREAM_CHAIN: dict[str, dict] = {
    "pcb": {
        "raw_materials": [
            {"name": "铜", "signal_key": "copper_price_up", "data_level": "A", "source": "LME期铜"},
            {"name": "玻纤布", "signal_key": "fiberglass_price_up", "data_level": "B", "source": "行业/供应商报价"},
            {"name": "环氧树脂", "signal_key": "resin_price_up", "data_level": "B", "source": "双酚A/ECH行情"},
        ],
        "mid_components": [
            {"name": "铜箔", "from": "铜", "cost_share": "15-25%"},
            {"name": "覆铜板(CCL)", "from": "铜箔+玻纤布+树脂", "cost_share": "30-40%"},
        ],
        "pass_through": "60%-80%",
        "lag": "1-3个月",
        "reliability": "verified",
    },
    "relay": {
        "raw_materials": [
            {"name": "白银", "signal_key": "silver_price_up", "data_level": "A", "source": "COMEX白银"},
            {"name": "铜", "signal_key": "copper_price_up", "data_level": "A", "source": "LME期铜"},
        ],
        "mid_components": [
            {"name": "银触点(AgSnO₂/AgNi)", "from": "白银", "cost_share": "10-20%"},
            {"name": "铜线圈", "from": "铜→漆包线", "cost_share": "8-15%"},
        ],
        "pass_through": "30%-50%",
        "lag": "2-4个月",
        "reliability": "verified",
    },
    "aluminum_electrolytic_capacitor": {
        "raw_materials": [
            {"name": "高纯铝", "signal_key": "aluminum_price_up", "data_level": "A", "source": "LME铝"},
            {"name": "电解液(乙二醇/有机酸)", "signal_key": "electrolyte_price_up", "data_level": "C", "source": "化工品行情"},
        ],
        "mid_components": [
            {"name": "阳极铝箔", "from": "高纯铝→腐蚀+化成", "cost_share": "25-35%"},
            {"name": "阴极铝箔", "from": "高纯铝", "cost_share": "10-15%"},
        ],
        "pass_through": "40%-60%",
        "lag": "3-6个月",
        "reliability": "high_theory",
    },
    "connector": {
        "raw_materials": [
            {"name": "铜", "signal_key": "copper_price_up", "data_level": "A", "source": "LME期铜"},
            {"name": "金", "signal_key": "gold_price_up", "data_level": "A", "source": "COMEX金"},
            {"name": "锡/镍", "signal_key": "tin_price_up", "data_level": "A", "source": "LME锡/镍"},
            {"name": "工程塑料(LCP/PA)", "signal_key": "engineering_plastics_price_up", "data_level": "C", "source": "化工品行情"},
        ],
        "mid_components": [
            {"name": "铜合金端子", "from": "铜", "cost_share": "10-18%"},
            {"name": "镀金/镀锡层", "from": "金/锡/镍", "cost_share": "5-12%"},
        ],
        "pass_through": "20%-40%",
        "lag": "3-6个月",
        "reliability": "high_theory",
    },
    "inductor_transformer": {
        "raw_materials": [
            {"name": "铜", "signal_key": "copper_price_up", "data_level": "A", "source": "LME期铜"},
            {"name": "磁芯(铁氧体/铁粉芯)", "signal_key": "magnetic_core_price_up", "data_level": "C", "source": "行业报价"},
        ],
        "mid_components": [
            {"name": "漆包线", "from": "铜", "cost_share": "20-30%"},
            {"name": "磁芯", "from": "铁氧体/铁粉芯", "cost_share": "10-18%"},
        ],
        "pass_through": "50%-70%",
        "lag": "2-4个月",
        "reliability": "high_theory",
    },
    "high_cap_mlcc": {
        "raw_materials": [
            {"name": "钛酸钡粉体", "signal_key": "ceramic_powder_pressure", "data_level": "C", "source": "不可稳定获取"},
            {"name": "镍(内电极)", "signal_key": "nickel_price_up", "data_level": "A", "source": "LME镍"},
            {"name": "铜/银钯(端电极)", "signal_key": "copper_price_up", "data_level": "A", "source": "LME铜"},
        ],
        "mid_components": [
            {"name": "陶瓷粉体", "from": "钛酸钡", "cost_share": "5-12%"},
            {"name": "内电极(镍)", "from": "镍", "cost_share": "3-8%"},
        ],
        "pass_through": "10%-30%",
        "lag": "3-6个月",
        "reliability": "theory",
    },
    "mlcc": {
        "raw_materials": [
            {"name": "钛酸钡粉体", "signal_key": "ceramic_powder_pressure", "data_level": "C", "source": "不可稳定获取"},
            {"name": "镍(内电极)", "signal_key": "nickel_price_up", "data_level": "A", "source": "LME镍"},
        ],
        "mid_components": [
            {"name": "陶瓷粉体", "from": "钛酸钡", "cost_share": "5-10%"},
        ],
        "pass_through": "5%-15%",
        "lag": "3-6个月",
        "reliability": "weak",
    },
    "mcu": {
        "raw_materials": [
            {"name": "硅片(8寸/12寸)", "signal_key": "silicon_wafer_price_up", "data_level": "C", "source": "行业报告"},
        ],
        "mid_components": [
            {"name": "晶圆", "from": "硅片+光刻+蚀刻+...", "cost_share": "N/A"},
            {"name": "封装(引线框架+塑封料)", "from": "铜+环氧树脂", "cost_share": "N/A"},
        ],
        "pass_through": "<10%(材料传导不适用)",
        "lag": "N/A",
        "reliability": "weak",
        "note": "IC类材料传导极弱，以供需信号为主",
    },
    "power_ic": {
        "raw_materials": [
            {"name": "硅片(8寸/12寸)", "signal_key": "silicon_wafer_price_up", "data_level": "C", "source": "行业报告"},
        ],
        "mid_components": [
            {"name": "晶圆(BCD/模拟制程)", "from": "硅片", "cost_share": "N/A"},
        ],
        "pass_through": "<10%",
        "lag": "N/A",
        "reliability": "weak",
        "note": "IC类材料传导极弱，以供需信号为主",
    },
    "resistor": {
        "raw_materials": [
            {"name": "氧化铝基板", "signal_key": "aluminum_price_up", "data_level": "B", "source": "行业报价"},
            {"name": "钌(电阻浆料)", "signal_key": "ruthenium_price_up", "data_level": "C", "source": "贵金属行情"},
            {"name": "银/钯(端电极)", "signal_key": "silver_price_up", "data_level": "A", "source": "COMEX银"},
        ],
        "mid_components": [
            {"name": "厚膜浆料", "from": "钌+银钯", "cost_share": "10-18%"},
            {"name": "端电极镀层", "from": "银/钯/镍/锡", "cost_share": "8-15%"},
        ],
        "pass_through": "20%-35%",
        "lag": "3-6个月",
        "reliability": "theory",
    },
    "discrete_diode": {
        "raw_materials": [
            {"name": "硅片", "signal_key": "silicon_wafer_price_up", "data_level": "C", "source": "行业报告"},
            {"name": "铜(引线框架)", "signal_key": "copper_price_up", "data_level": "A", "source": "LME铜"},
        ],
        "mid_components": [
            {"name": "引线框架", "from": "铜", "cost_share": "8-15%"},
            {"name": "塑封料", "from": "环氧树脂", "cost_share": "3-7%"},
        ],
        "pass_through": "15%-30%",
        "lag": "2-4个月",
        "reliability": "high_theory",
    },
    "mosfet": {
        "raw_materials": [
            {"name": "硅片/SiC衬底", "signal_key": "silicon_wafer_price_up", "data_level": "C", "source": "行业报告"},
            {"name": "铜(铜夹/基板)", "signal_key": "copper_price_up", "data_level": "A", "source": "LME铜"},
        ],
        "mid_components": [
            {"name": "晶圆/外延片", "from": "硅片/SiC", "cost_share": "N/A"},
            {"name": "铜夹/引线框架", "from": "铜", "cost_share": "5-12%"},
        ],
        "pass_through": "<15%(供需主导)",
        "lag": "N/A",
        "reliability": "weak",
        "note": "功率器件以供需和产能为主，材料传导为辅",
    },
    "wire_harness": {
        "raw_materials": [
            {"name": "铜", "signal_key": "copper_price_up", "data_level": "A", "source": "LME期铜"},
            {"name": "PVC/TPE", "signal_key": "engineering_plastics_price_up", "data_level": "C", "source": "化工品行情"},
        ],
        "mid_components": [
            {"name": "铜线材", "from": "铜", "cost_share": "30-50%"},
            {"name": "绝缘皮", "from": "PVC/TPE", "cost_share": "10-20%"},
        ],
        "pass_through": "60%-80%",
        "lag": "2-4个月",
        "reliability": "verified",
    },
    "switch": {
        "raw_materials": [
            {"name": "铜(弹片/端子)", "signal_key": "copper_price_up", "data_level": "A", "source": "LME铜"},
            {"name": "银(触点)", "signal_key": "silver_price_up", "data_level": "A", "source": "COMEX银"},
        ],
        "mid_components": [
            {"name": "弹片/触点", "from": "铜+银", "cost_share": "15-25%"},
        ],
        "pass_through": "25%-45%",
        "lag": "3-6个月",
        "reliability": "high_theory",
    },
    "film_capacitor": {
        "raw_materials": [
            {"name": "聚丙烯/聚酯薄膜", "signal_key": "plastic_film_price_up", "data_level": "C", "source": "化工品行情"},
            {"name": "锌/铝(喷金)", "signal_key": "aluminum_price_up", "data_level": "A", "source": "LME铝"},
            {"name": "环氧树脂(灌封)", "signal_key": "resin_price_up", "data_level": "B", "source": "化工品行情"},
        ],
        "mid_components": [
            {"name": "金属化薄膜", "from": "聚丙烯+锌/铝蒸镀", "cost_share": "25-40%"},
            {"name": "灌封树脂", "from": "环氧树脂", "cost_share": "8-15%"},
        ],
        "pass_through": "20%-35%",
        "lag": "3-6个月",
        "reliability": "high_theory",
    },
    "tantalum_capacitor": {
        "raw_materials": [
            {"name": "钽粉/钽丝", "signal_key": "tantalum_price_up", "data_level": "D", "source": "矿产/供应商报价"},
            {"name": "银(阴极)", "signal_key": "silver_price_up", "data_level": "A", "source": "COMEX银"},
        ],
        "mid_components": [
            {"name": "钽阳极", "from": "钽粉→烧结", "cost_share": "30-50%"},
        ],
        "pass_through": "30%-50%",
        "lag": "3-6个月",
        "reliability": "high_theory",
    },
    "varistor_thermistor": {
        "raw_materials": [
            {"name": "氧化锌/氧化铋", "signal_key": "zinc_price_up", "data_level": "C", "source": "行业报价"},
            {"name": "银(电极)", "signal_key": "silver_price_up", "data_level": "A", "source": "COMEX银"},
        ],
        "mid_components": [
            {"name": "陶瓷芯片", "from": "氧化锌+氧化铋→烧结", "cost_share": "15-25%"},
            {"name": "银电极", "from": "银", "cost_share": "8-15%"},
        ],
        "pass_through": "20%-35%",
        "lag": "3-6个月",
        "reliability": "theory",
    },
    "power_module": {
        "raw_materials": [
            {"name": "铜(底板/端子)", "signal_key": "copper_price_up", "data_level": "A", "source": "LME铜"},
            {"name": "氧化铝/氮化铝陶瓷", "signal_key": "aluminum_price_up", "data_level": "C", "source": "行业报价"},
            {"name": "银(烧结)", "signal_key": "silver_price_up", "data_level": "A", "source": "COMEX银"},
        ],
        "mid_components": [
            {"name": "DBC/AMB基板", "from": "铜+陶瓷", "cost_share": "15-25%"},
            {"name": "银烧结层", "from": "银", "cost_share": "5-10%"},
        ],
        "pass_through": "20%-40%",
        "lag": "3-6个月",
        "reliability": "high_theory",
    },
}

# 供需驱动型品类的"材料传导不适用"标记
DEMAND_DRIVEN_NOTE = {
    "mcu": "IC类材料传导极弱（硅片涨价不足以推断MCU涨价），风险判断以供需信号为主：关注交期、库存、产能和行业需求。",
    "power_ic": "IC类材料传导极弱，风险判断以供需信号为主：关注BCD制程产能、封测排产和汽车/工业需求。",
    "mosfet": "功率器件材料传导为辅，供需和产能为主：关注新能源车/光伏/储能订单挤占和SiC衬底产能。",
    "analog_ic": "IC类材料传导极弱，以供需信号为主。",
    "memory": "存储芯片价格周期性强，材料传导极弱。关注DRAM/NAND行业周期和原厂产能策略。",
    "fpga_cpld": "IC类以供需和先进制程产能为主，材料传导不适用。",
    "crystal_oscillator": "晶振以供需和认证为主，材料占比较低。",
    "sensor": "传感器以供需和认证为主，MEMS工艺产能是关键信号。",
}


@dataclass(frozen=True)
class ChainNode:
    """层级链路节点。"""
    layer: str          # raw_material / mid_component / device_category / bom_item
    name: str
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceChainResult:
    """v3.5 层级因果链结果。"""
    risk_level: str
    primary_track: str
    driver_type: str
    total_score: int
    summary: str
    action_suggestion: str
    # 层级链
    upstream_chain: list[dict] = field(default_factory=list)
    # 关联事件
    market_events: list[dict] = field(default_factory=list)
    # 供应快照
    supply_snapshot: dict = field(default_factory=dict)
    # 缓冲因素
    buffer: dict = field(default_factory=dict)
    # AI判断
    ai_judgement: str = ""


def _get_upstream_template(category: str) -> dict:
    """获取品类的上游材料模板。"""
    return CATEGORY_UPSTREAM_CHAIN.get(category, {
        "raw_materials": [],
        "mid_components": [],
        "pass_through": "未知",
        "lag": "未知",
        "reliability": "unknown",
    })


def _build_chain_nodes(
    category: str,
    category_display: str,
    material_signals: dict,
    item_info: dict,
) -> list[dict]:
    """构建层级链节点。"""
    template = _get_upstream_template(category)
    chain = []

    # 层1：原材料
    for rm in template.get("raw_materials", []):
        signal_key = rm.get("signal_key", "")
        has_signal = material_signals.get(signal_key, False)
        node = {
            "layer": "raw_material",
            "name": rm["name"],
            "data_level": rm.get("data_level", "C"),
            "source": rm.get("source", ""),
            "has_alert": bool(has_signal),
            "signal_key": signal_key,
        }
        chain.append(node)

    # 层2：二级组份
    for mc in template.get("mid_components", []):
        node = {
            "layer": "mid_component",
            "name": mc["name"],
            "from": mc.get("from", ""),
            "cost_share": mc.get("cost_share", ""),
        }
        chain.append(node)

    # 层3：器件品类
    model = CATEGORY_MODEL_WEIGHTS.get(category, {})
    chain.append({
        "layer": "device_category",
        "name": category_display,
        "category": category,
        "driver_type": model.get("display", category_display),
        "pass_through": template.get("pass_through", ""),
        "lag": template.get("lag", ""),
        "reliability": template.get("reliability", "unknown"),
        "material_weight": model.get("material", 0),
        "demand_supply_weight": model.get("demand_supply", 0),
    })

    # 层4：BOM物料
    if item_info:
        chain.append({
            "layer": "bom_item",
            "mpn": item_info.get("mpn", ""),
            "brand": item_info.get("brand", ""),
            "project": item_info.get("project_name", ""),
            "project_id": item_info.get("project_id", ""),
            "risk_level": item_info.get("risk_level", ""),
        })

    return chain


def _build_ai_judgement(
    category: str,
    risk_level: str,
    primary_track: str,
    has_market_facts: bool,
    chain_template: dict,
) -> str:
    """生成AI综合判断文本。"""
    parts = []

    # IC类材料传导弱约束说明
    if category in DEMAND_DRIVEN_NOTE and primary_track != "demand_supply" and not has_market_facts:
        parts.append(DEMAND_DRIVEN_NOTE[category])

    # 风险等级判断
    if risk_level in ("red", "orange"):
        parts.append(f"当前为{risk_level}级风险，建议优先处理。")
    elif risk_level == "yellow":
        parts.append("当前为关注级别，建议纳入观察池跟踪变化。")
    elif risk_level == "green":
        parts.append("当前风险较低，保持常规监控即可。")
    else:
        parts.append("信息不足，建议补充品牌、型号、库存和交期数据后再评估。")

    # 双轨说明
    if primary_track == "material":
        parts.append(f"主导轨道为材料传导，传导可靠性为{chain_template.get('reliability', 'unknown')}，预计滞后{chain_template.get('lag', '未知')}。")
    elif primary_track == "demand_supply":
        parts.append("主导轨道为供需信号。")
    elif primary_track == "lifecycle":
        parts.append("物料生命周期异常，建议立即切换替代料。")

    return "；".join(parts)


def _suggest_action(risk_level: str, category_display: str, primary_track: str, category: str) -> str:
    """生成处置建议。"""
    if risk_level in ("red", "orange"):
        if primary_track == "lifecycle":
            return f"立即启动{category_display}替代料评审，确认LTB窗口，停产风险需优先处理。"
        if primary_track == "material":
            return f"关注{category_display}上游材料传导，复核供应商调价窗口和安全库存覆盖周期，建议提前锁价或备货。"
        if primary_track == "demand_supply":
            return f"优先核查{category_display}库存、供应商报价和替代料，必要时提前锁单。确认原厂/代理最新的交期和分配策略。"
        return f"补充{category_display}品牌、型号、库存、交期和供应商证据后再升级预警。"
    if risk_level == "yellow":
        if category in DEMAND_DRIVEN_NOTE:
            return f"将{category_display}纳入观察池，跟踪交期、库存变化。建议准备pin-to-pin替代方案。"
        return f"将{category_display}纳入观察池，跟踪价格、库存和交期变化。"
    if risk_level == "green":
        return f"当前{category_display}风险较低，保持常规监控。"
    return f"当前{category_display}信息不足，建议补充品牌、型号和行情数据。"


def _event_to_dict(event: Any) -> dict:
    """事件对象转字典。"""
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return {
        "id": getattr(event, "id", None),
        "title": getattr(event, "raw_title", None) or getattr(event, "title", ""),
        "source_name": getattr(event, "source_name", ""),
        "brand": getattr(event, "brand", ""),
        "category": getattr(event, "category", ""),
        "event_type": getattr(event, "event_type", ""),
        "severity": getattr(event, "severity", ""),
        "estimated_price_impact_pct": getattr(event, "estimated_price_impact_pct", None),
        "estimated_lead_time_impact_weeks": getattr(event, "estimated_lead_time_impact_weeks", None),
    }


def build_evidence_chain(
    item: Any,
    category_result: Any,
    matched_events: list[Any] | None,
    dual_track_result: Any,
    realtime_data: dict | None,
    buffers: dict | None,
) -> EvidenceChainResult:
    """构建 v3.5 层级因果链。

    与 v3.2 的关键差异：
    - upstream_chain 是按"原材料→组份→器件→BOM"层级的因果链
    - 每层节点包含传导可靠性、转嫁率、滞后时间
    - IC类材料传导弱时自动降权说明
    - ai_judgement 基于品类模型综合生成
    """
    matched_events = matched_events or []
    realtime_data = realtime_data or {}
    buffers = buffers or {}

    category = getattr(category_result, "category", "unknown")
    category_display = getattr(category_result, "display_name", None) or getattr(category_result, "category", "未知品类")
    risk_level = getattr(dual_track_result, "risk_level", "gray")
    primary_track = getattr(dual_track_result, "primary_track", "information_insufficient")
    driver_type = getattr(category_result, "driver_type", "unknown")

    # 构建层级链
    item_info = {
        "mpn": getattr(item, "raw_part_number", "") or getattr(item, "mpn_raw", ""),
        "brand": getattr(item, "raw_brand", "") or getattr(item, "normalized_brand", ""),
        "project_name": getattr(item, "project_name", ""),
        "project_id": getattr(item, "project_id", ""),
        "risk_level": risk_level,
    }

    material_signals = getattr(dual_track_result, "track_scores", {}).get("material", 0)
    upstream_chain = _build_chain_nodes(category, category_display, {"material_signal": material_signals > 0}, item_info)

    # 关联事件
    market_events = [_event_to_dict(evt) for evt in matched_events]

    # 供应快照
    supply_snapshot = {
        "total_stock": realtime_data.get("total_stock", 0),
        "supplier_count": realtime_data.get("supplier_count", 0),
        "lead_time_days": realtime_data.get("lead_time_days"),
        "unit_price": realtime_data.get("unit_price"),
        "lifecycle_status": realtime_data.get("lifecycle_status", "Unknown"),
    }

    # 缓冲
    buffer_info = {
        "safety_stock_days": buffers.get("safety_stock_days", 0),
        "multi_source": buffers.get("multi_source_available", False),
        "supplier_count": buffers.get("supplier_count", 0),
    }

    # AI判断
    chain_template = _get_upstream_template(category)
    has_market_facts = len(matched_events) > 0
    ai_judgement = _build_ai_judgement(category, risk_level, primary_track, has_market_facts, chain_template)

    # 汇总
    if primary_track == "information_insufficient" or risk_level == "gray":
        summary = f"{category_display}信息不足，暂不升级强预警。建议补充品牌、型号、行情事实、库存或交期证据。"
    else:
        summary = f"{category_display}当前为{risk_level}风险，主导轨道为{primary_track}，总评分{getattr(dual_track_result, 'total_score', 0)}分。"

    action = _suggest_action(risk_level, category_display, primary_track, category)

    return EvidenceChainResult(
        risk_level=risk_level,
        primary_track=primary_track,
        driver_type=driver_type,
        total_score=getattr(dual_track_result, "total_score", 0),
        summary=summary,
        action_suggestion=action,
        upstream_chain=upstream_chain,
        market_events=market_events,
        supply_snapshot=supply_snapshot,
        buffer=buffer_info,
        ai_judgement=ai_judgement,
    )
