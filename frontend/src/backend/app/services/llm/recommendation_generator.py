"""采购/研发/项目管理建议生成服务 (T2-013)。

基于风险评估结果（多因子评分 + 链路推理），生成面向不同角色的可操作建议。

核心流程:
1. 接收风险评估数据（风险等级、因子分数、受影响物料）
2. 可选: 接收链路推理结果（来自 T2-011）
3. 构造 prompt 调用 LLM 生成建议
4. 解析输出为结构化 JSON（三组建议列表 + 总结）
5. LLM 调用失败时降级为模板生成

降级策略:
- recommendation 降级为模板生成:
  根据风险等级和因子分数，从预定义模板库中选择匹配的建议模板，
  填入具体物料信息后输出。模板覆盖采购/研发/项目管理三种角色。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.llm.base import LLMCallResult, LLMServiceBase
from app.services.llm.prompts.recommendation import (
    RECOMMENDATION_OUTPUT_SCHEMA,
    RECOMMENDATION_PM_ACTIONS,
    RECOMMENDATION_PROCUREMENT_ACTIONS,
    RECOMMENDATION_RD_ACTIONS,
    RECOMMENDATION_REQUIRED_FIELDS,
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 降级模板库
# ═══════════════════════════════════════════════════════════════════════════════

# 常见国产替代关系映射
_ALT_MODEL_MAPPING = {
    "STM32": "GD32系列（兆易创新）或AT32系列（雅特力）",
    "MCU": "国产MCU（兆易GD32/雅特力AT32/华大HC32）",
    "MLCC": "国产MLCC（三环集团/风华高科/宇阳科技）",
    "MOSFET": "国产MOSFET（华润微/士兰微/新洁能）",
    "WIFI": "国产WiFi芯片（乐鑫ESP32/博通集成/瑞昱）",
    "BLUETOOTH": "国产蓝牙芯片（泰凌微/炬芯/恒玄）",
    "晶振": "国产晶振（TXC/惠伦/大真空）",
    "连接器": "国产连接器（中航光电/瑞可达/电连技术）",
}


def _get_alt_model_suggestion(material_name: str) -> str:
    """根据物料名称推荐替代型号方向。"""
    name_upper = material_name.upper()
    for key, suggestion in _ALT_MODEL_MAPPING.items():
        if key.upper() in name_upper:
            return suggestion
    return "建议评估国产替代方案，具体型号需研发根据规格书确认"


def _generate_template_recommendations(context: dict[str, Any]) -> dict[str, Any]:
    """模板降级输出：根据风险等级和物料信息生成建议。"""
    risk_level = context.get("risk_level", "yellow")
    affected_materials = context.get("affected_materials", [])
    event = context.get("event", "供应链风险事件")

    # 风险等级 → 参数映射
    params_map = {
        "red":    {"urgency": "high",   "lock_weeks": 12, "safety_weeks": 8,  "buffer_days": 30, "reserve_pct": 8, "verify_weeks": 8},
        "orange": {"urgency": "high",   "lock_weeks": 8,  "safety_weeks": 6,  "buffer_days": 21, "reserve_pct": 5, "verify_weeks": 6},
        "yellow": {"urgency": "medium", "lock_weeks": 4,  "safety_weeks": 4,  "buffer_days": 14, "reserve_pct": 3, "verify_weeks": 4},
        "green":  {"urgency": "low",    "lock_weeks": 2,  "safety_weeks": 2,  "buffer_days": 7,  "reserve_pct": 2, "verify_weeks": 4},
    }
    p = params_map.get(risk_level, params_map["yellow"])

    # 提取物料名称
    material_names = []
    for m in affected_materials[:5]:
        if isinstance(m, dict):
            name = m.get("mpn") or m.get("name") or m.get("category", "未知物料")
        else:
            name = str(m)
        material_names.append(name)
    if not material_names:
        material_names = ["受影响物料"]
    materials_text = "、".join(material_names[:3])

    # ── 采购建议 ──
    procurement_recs = [
        {
            "action_type": "lock_price",
            "material": materials_text,
            "risk_reason": f"事件「{event}」导致行情趋势上行，需防止进一步涨价",
            "detail": f"建议锁定{p['lock_weeks']}周需求量的{materials_text}，与供应商签订固定价格协议",
            "urgency": p["urgency"],
            "estimated_cost_impact": f"可避免后续{p['reserve_pct'] * 2}%的潜在涨价风险",
        },
        {
            "action_type": "safety_stock",
            "material": materials_text,
            "risk_reason": f"事件「{event}」可能导致供应紧张，交期延长",
            "detail": f"将{materials_text}安全库存提升至{p['safety_weeks']}周用量，立即下达备货订单",
            "urgency": p["urgency"],
            "estimated_cost_impact": f"增加约{p['reserve_pct']}%库存成本，但可避免停线风险",
        },
    ]

    # 单源物料额外建议
    single_source = [m for m in affected_materials if isinstance(m, dict) and m.get("is_single_source")]
    if single_source:
        ss_names = [m.get("mpn", "单源物料") for m in single_source[:2]]
        procurement_recs.append({
            "action_type": "alternative_source",
            "material": "、".join(ss_names),
            "risk_reason": f"{'、'.join(ss_names)}为单源供应，断供风险极高",
            "detail": "立即启动替代供应商认证流程，目标在4周内完成合格供应商导入",
            "urgency": "high",
            "estimated_cost_impact": "认证成本约5-10万，但可消除单点故障风险",
        })

    # ── 研发建议 ──
    rd_recs = [
        {
            "action_type": "alt_verification",
            "material": materials_text,
            "risk_reason": f"事件「{event}」影响{materials_text}供应稳定性",
            "detail": f"启动{materials_text}的Pin-to-Pin替代料验证，优先选择国产替代方案",
            "alt_model": _get_alt_model_suggestion(material_names[0]),
            "verification_weeks": p["verify_weeks"],
            "urgency": p["urgency"],
        },
    ]
    if risk_level in ("red", "orange"):
        rd_recs.append({
            "action_type": "cert_presets",
            "material": materials_text,
            "risk_reason": f"{materials_text}品类认证周期长（>6个月），需提前预置",
            "detail": f"对{materials_text}启动替代认证预置，覆盖汽车级/工业级认证",
            "alt_model": "",
            "verification_weeks": p["verify_weeks"] * 2,
            "urgency": p["urgency"],
        })

    # ── 项目管理建议 ──
    pm_recs = [
        {
            "action_type": "schedule_buffer",
            "material": "整体项目",
            "risk_reason": f"事件「{event}」导致关键物料交期不确定性增加",
            "detail": f"在项目关键路径上增加{p['buffer_days']}天交期缓冲",
            "buffer_days": p["buffer_days"],
            "reserve_pct": 0,
            "urgency": p["urgency"],
        },
        {
            "action_type": "milestone_adjust",
            "material": "整体项目",
            "risk_reason": f"{materials_text}交期可能延长，影响EVT/DVT节点",
            "detail": f"建议将依赖{materials_text}的里程碑节点后移{p['buffer_days'] // 2}周",
            "buffer_days": p["buffer_days"] // 2,
            "reserve_pct": 0,
            "urgency": p["urgency"],
        },
        {
            "action_type": "cost_reserve",
            "material": "整体项目",
            "risk_reason": "物料涨价和加急运费可能导致项目成本超支",
            "detail": f"建议在项目预算中增加{p['reserve_pct']}%的成本风险储备",
            "buffer_days": 0,
            "reserve_pct": p["reserve_pct"],
            "urgency": p["urgency"],
        },
    ]

    summary = (
        f"风险事件「{event}」风险等级为{risk_level}，"
        f"建议采购立即执行锁价备货（{p['lock_weeks']}周），"
        f"研发启动替代料验证（{p['verify_weeks']}周），"
        f"项目增加{p['buffer_days']}天缓冲和{p['reserve_pct']}%成本储备。"
    )

    return {
        "procurement_recommendations": procurement_recs,
        "rd_recommendations": rd_recs,
        "pm_recommendations": pm_recs,
        "summary": summary,
        "_degraded": True,
        "_degrade_method": "template",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 主服务类
# ═══════════════════════════════════════════════════════════════════════════════

class RecommendationGenerator(LLMServiceBase):
    """采购/研发/项目管理建议生成服务 (T2-013)。

    Usage::

        generator = RecommendationGenerator()
        result = generator.generate(
            event="台湾台南发生M6.4地震",
            risk_level="red",
            risk_score=85.0,
            affected_materials=[{"mpn": "MT6625", "category": "无线芯片"}],
        )
    """

    SERVICE_NAME = "RecommendationGenerator"
    DEFAULT_MAX_TOKENS = 2500

    def _build_system_prompt(self) -> str:
        return RECOMMENDATION_SYSTEM_PROMPT

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        # 格式化因子明细
        factor_details = context.get("factor_details", "")
        if isinstance(factor_details, dict):
            lines = [f"- {k}: {v.get('raw_score', v.get('score', 'N/A'))}分"
                     if isinstance(v, dict) else f"- {k}: {v}"
                     for k, v in factor_details.items()]
            factor_details = "\n".join(lines) if lines else "暂无因子数据"
        elif not factor_details:
            factor_details = "暂无因子数据"

        # 格式化物料列表
        affected_materials = context.get("affected_materials", [])
        if affected_materials:
            mat_lines = []
            for i, m in enumerate(affected_materials, 1):
                if isinstance(m, dict):
                    mpn = m.get("mpn", m.get("name", "N/A"))
                    cat = m.get("category", "N/A")
                    proj = m.get("project", "")
                    line = f"{i}. {mpn} | 品类: {cat}"
                    if proj:
                        line += f" | 项目: {proj}"
                    mat_lines.append(line)
                else:
                    mat_lines.append(f"{i}. {str(m)}")
            materials_text = "\n".join(mat_lines)
        else:
            materials_text = "暂无具体物料数据"

        # 链路推理结果
        reasoning_result = context.get("reasoning_result", "")
        if isinstance(reasoning_result, dict):
            reasoning_lines = [f"- {k}: {v}" for k, v in reasoning_result.items()
                              if not k.startswith("_")]
            reasoning_result = "\n".join(reasoning_lines)
        elif not reasoning_result:
            reasoning_result = "暂无链路推理结果"

        # 供应链上下文
        supply_context = context.get("supply_context", "")
        if isinstance(supply_context, dict):
            supply_context = "\n".join(f"- {k}: {v}" for k, v in supply_context.items())
        elif not supply_context:
            supply_context = "暂无额外供应链数据"

        return RECOMMENDATION_USER_PROMPT_TEMPLATE.format(
            event=context.get("event", "未知风险事件"),
            risk_level=context.get("risk_level", "unknown"),
            risk_score=context.get("risk_score", "N/A"),
            factor_details=factor_details,
            affected_materials=materials_text,
            reasoning_result=reasoning_result,
            supply_context=supply_context,
        )

    def _validate_output(self, data: dict) -> bool:
        """验证输出包含所有必要字段且建议列表非空。"""
        if not isinstance(data, dict):
            return False
        for field_name in RECOMMENDATION_REQUIRED_FIELDS:
            if field_name not in data:
                return False
        for list_field in ["procurement_recommendations", "rd_recommendations", "pm_recommendations"]:
            value = data.get(list_field)
            if not isinstance(value, list) or len(value) == 0:
                return False
        summary = data.get("summary", "")
        if not summary or not str(summary).strip():
            return False
        return True

    def _fallback(self, context: dict[str, Any]) -> dict:
        return _generate_template_recommendations(context)

    def generate(
        self,
        event: str,
        risk_level: str,
        risk_score: float,
        affected_materials: list[dict[str, Any]],
        factor_details: Any = None,
        reasoning_result: Any = None,
        supply_context: Any = None,
    ) -> LLMCallResult:
        """便捷生成接口。"""
        context = {
            "event": event,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "affected_materials": affected_materials,
            "factor_details": factor_details or "",
            "reasoning_result": reasoning_result or "",
            "supply_context": supply_context or "",
        }
        return self.run(context)
