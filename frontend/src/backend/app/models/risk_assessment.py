"""
多因子风险评估结果模型 (T2-001)

定义七因子加权风险评分的数据结构，包括：
- MultiFactorScore: 单个因子的评分详情
- MultiFactorRiskResult: 完整的多因子风险评估结果
- RiskLevel: 五级风险等级枚举

兼容 Phase 1 DualTrackRiskResult 的字段子集，确保下游可平滑迁移。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    """五级风险等级映射"""
    RED = "red"          # >=80分: 已影响交付/成本
    ORANGE = "orange"    # >=60分: 高概率影响
    YELLOW = "yellow"    # >=35分: 早期信号
    GREEN = "green"      # >0分: 风险可控
    GRAY = "gray"        # 数据不足: 不允许显示为正常


RISK_LEVEL_THRESHOLDS: list[tuple[int, RiskLevel]] = [
    (80, RiskLevel.RED),
    (60, RiskLevel.ORANGE),
    (35, RiskLevel.YELLOW),
    (1, RiskLevel.GREEN),
]

RISK_LEVEL_LABELS: dict[str, str] = {
    "red": "极高风险",
    "orange": "高风险",
    "yellow": "中风险",
    "green": "低风险",
    "gray": "数据不足",
}


def score_to_risk_level(score: float, has_sufficient_data: bool) -> RiskLevel:
    """
    将数值分数映射到五级风险等级。

    Args:
        score: 总风险分 (0-100)
        has_sufficient_data: 是否有足够数据支撑评分

    Returns:
        RiskLevel 枚举值
    """
    if not has_sufficient_data:
        return RiskLevel.GRAY
    for threshold, level in RISK_LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.GRAY


@dataclass(frozen=True)
class FactorScore:
    """
    单个风险因子的评分详情。

    Attributes:
        name: 因子标识名 (e.g. 'market_trend')
        display_name: 因子中文显示名 (e.g. '行情趋势分')
        raw_score: 原始评分 (0-100)
        weight: 权重 (0-1)
        weighted_score: 加权后得分
        evidence: 评分依据列表
        confidence: 该因子自身的数据置信度 (0.0-1.0)
    """
    name: str
    display_name: str
    raw_score: float
    weight: float
    weighted_score: float
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass(frozen=True)
class MultiFactorRiskResult:
    """
    七因子加权风险评估的完整结果。

    保留与 Phase 1 DualTrackRiskResult 的兼容性字段：
    - category, risk_level, total_score, reason, evidence
    新增多因子专属字段：
    - factors: 各因子评分详情
    - confidence_coefficient: 数据置信度调整系数 (0.8-1.2)
    - primary_factor: 最高风险因子名
    - legacy_track_scores: 兼容 Phase 1 的双轨分数

    Attributes:
        category: 物料品类标识
        risk_level: 五级风险等级 (red/orange/yellow/green/gray)
        total_score: 最终总风险分 (0-100)
        base_score: 置信度系数调整前的基础分
        confidence_coefficient: 数据置信度调整系数 (0.8-1.2)
        factors: 七因子评分详情字典
        primary_factor: 贡献最大的因子名
        reason: 风险判定原因说明
        evidence: 所有因子证据汇总
        legacy_track_scores: 兼容Phase1的双轨分数 {material, demand_supply}
    """
    category: str
    risk_level: str
    total_score: float
    base_score: float
    confidence_coefficient: float
    factors: dict[str, FactorScore]
    primary_factor: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    legacy_track_scores: dict[str, float] = field(default_factory=dict)

    # ── 兼容 Phase 1 DualTrackRiskResult 的字段别名 ──
    @property
    def primary_track(self) -> str:
        """兼容Phase1: 返回主风险轨/因子"""
        return self.primary_factor

    @property
    def track_scores(self) -> dict[str, float]:
        """兼容Phase1: 返回轨分数"""
        return self.legacy_track_scores

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，便于API返回"""
        return {
            "category": self.category,
            "risk_level": self.risk_level,
            "total_score": round(self.total_score, 1),
            "base_score": round(self.base_score, 1),
            "confidence_coefficient": self.confidence_coefficient,
            "primary_factor": self.primary_factor,
            "reason": self.reason,
            "evidence": self.evidence,
            "factors": {
                name: {
                    "display_name": f.display_name,
                    "raw_score": round(f.raw_score, 1),
                    "weight": f.weight,
                    "weighted_score": round(f.weighted_score, 2),
                    "evidence": f.evidence,
                    "confidence": f.confidence,
                }
                for name, f in self.factors.items()
            },
            "legacy_track_scores": self.legacy_track_scores,
        }
