"""BOMMatcher v2.0 全量收集模式测试

验证：
- 不再短路：同时收集精确命中 + 品类波及事件
- 精确命中 = RED，波及命中 = YELLOW
- 去重：同一事件不重复出现
- 评分：精确命中全权重，波及命中 0.6 权重
"""

import pytest
from app.services.bom_matcher import BOMMatcher
from app.models.bom import RiskLevel


# ── Fake 类 ──────────────────────────────────────────────

class FakeEventType:
    value = "supply_disruption"


class FakeSeverity:
    value = "high"


class FakeEvent:
    """模拟 MarketEvent，支持品牌/品类/严重性/置信度/交叉验证配置"""

    def __init__(self, event_id, brand, category, severity="high", confidence=0.8, cross_validated=2):
        self.id = event_id
        self.brand = brand
        self.category = category
        self.event_type = FakeEventType()
        self.severity = FakeSeverity() if severity == "high" else _FakeSeverity(severity)
        self.confidence = confidence
        self.cross_validated = cross_validated

    def to_dict(self):
        return {"id": self.id, "brand": self.brand, "category": self.category}


class _FakeSeverity:
    def __init__(self, value):
        self.value = value


class FakeItem:
    """模拟 BomItem"""

    def __init__(self, normalized_brand=None, normalized_category=None, raw_category=None):
        self.normalized_brand = normalized_brand
        self.normalized_category = normalized_category
        self.raw_category = raw_category


# ── 辅助 ───────────────────────────────────────────────────

def make_events(*specs):
    """快捷构造事件列表，每个 spec 为 (id, brand, category[, severity, confidence, cross_validated])"""
    return [FakeEvent(*s) for s in specs]


def make_item(brand=None, cat=None):
    return FakeItem(normalized_brand=brand, normalized_category=cat, raw_category=cat)


# ── 基础匹配 ──────────────────────────────────────────────

class TestBasicMatching:

    def test_no_events_returns_green(self):
        matcher = BOMMatcher([])
        level, score, events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.GREEN
        assert score == 0.0
        assert events == []

    def test_both_brand_and_category_missing_returns_gray(self):
        matcher = BOMMatcher(make_events((1, "TDK", "MLCC高容")))
        level, score, events, reason = matcher.match_item(make_item(None, None))
        assert level == RiskLevel.GRAY
        assert score == 0.0
        assert events == []
        assert "信息均缺失" in reason

    def test_exact_brand_category_match_returns_red(self):
        matcher = BOMMatcher(make_events((1, "TDK", "MLCC高容")))
        level, score, events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.RED
        assert score > 0
        assert len(events) == 1
        assert events[0].id == 1
        assert "精确命中" in reason

    def test_category_spread_only_returns_yellow(self):
        """MLCC高容的兄弟品类 MLCC中低压 应被波及命中"""
        matcher = BOMMatcher(make_events((1, "TDK", "MLCC中低压")))
        level, score, events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.YELLOW
        assert score > 0
        assert len(events) == 1
        assert events[0].id == 1
        assert "品类波及" in reason

    def test_unrelated_category_returns_green(self):
        matcher = BOMMatcher(make_events((1, "TDK", "USB连接器")))
        level, score, events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.GREEN
        assert score == 0.0
        assert events == []

    def test_different_brand_same_category_returns_yellow_spread(self):
        """不同品牌但同品类事件，通过品类波及（祖先品类匹配）命中，这是合理的行为：
           同品类事件即使品牌不同，也反映整个品类受压力。"""
        matcher = BOMMatcher(make_events((1, "TI", "MLCC高容")))
        level, score, events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.YELLOW
        assert len(events) == 1
        assert "品类波及" in reason


# ── v2.0 全量收集（不短路） ──────────────────────────────

class TestFullCollectionNoShortCircuit:

    def test_both_exact_and_spread_collected(self):
        """精确命中 + 波及命中 同时存在：应返回 RED，事件数 = 2"""
        events = make_events(
            (1, "TDK", "MLCC高容"),      # 精确命中
            (2, "TDK", "MLCC中低压"),    # 波及命中（兄弟品类）
            (3, "TI", "MCU/微控制器"),   # 不相关
        )
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))

        # 应返回 RED（有精确命中）
        assert level == RiskLevel.RED
        # 应包含 2 个事件：直接命中 + 波及
        assert len(result_events) == 2
        event_ids = {e.id for e in result_events}
        assert 1 in event_ids  # 精确命中
        assert 2 in event_ids  # 波及命中
        assert 3 not in event_ids  # 不相关
        # 原因应同时包含两部分
        assert "精确命中" in reason
        assert "品类波及" in reason

    def test_only_spread_when_no_exact_match(self):
        """无精确命中，仅波及：YELLOW"""
        events = make_events(
            (1, "TDK", "MLCC中低压"),    # 波及
            (2, "TI", "LDO"),            # 波及（DC-DC的兄弟品类）
        )
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))

        assert level == RiskLevel.YELLOW
        assert len(result_events) == 1
        assert result_events[0].id == 1

    def test_spread_via_ancestor_category(self):
        """通过祖先品类波及：事件品类 MLCC（父级）应波及 MLCC高容"""
        events = make_events((1, "TDK", "MLCC"))
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))

        assert level == RiskLevel.YELLOW
        assert len(result_events) == 1

    def test_dedup_exact_event_not_repeated_in_spread(self):
        """精确命中的事件不应再出现在波及列表中"""
        events = make_events((1, "TDK", "MLCC高容"))
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))

        assert len(result_events) == 1
        assert result_events[0].id == 1
        # 原因中不应有"品类波及"
        assert "品类波及" not in reason

    def test_multiple_exact_matches_all_collected(self):
        """多个精确命中事件全部收集"""
        events = make_events(
            (1, "TDK", "MLCC高容"),
            (2, "TDK", "MLCC高容"),
            (3, "TDK", "MLCC高容"),
        )
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))

        assert level == RiskLevel.RED
        assert len(result_events) == 3
        assert "精确命中 3条" in reason

    def test_brand_with_slash_matches_exact(self):
        """品牌含 '/' 如 ST/意法半导体 → 精确匹配"""
        item = make_item("ST", "MCU/微控制器")
        events = make_events((1, "ST", "MCU/微控制器"))
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(item)

        assert level == RiskLevel.RED
        assert len(result_events) == 1


# ── 评分计算 ─────────────────────────────────────────────

class TestRiskScoring:

    def test_exact_score_full_weight(self):
        """精确命中：severity=high, confidence=0.8, cross_validated=2 → 75*0.8*1.2=72"""
        events = make_events((1, "TDK", "MLCC高容", "high", 0.8, 2))
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert score == 72.0

    def test_spread_score_weighted_0_6(self):
        """波及命中：severity=high → 75*0.8*1.2*0.6=43.2"""
        events = make_events((1, "TDK", "MLCC中低压", "high", 0.8, 2))
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert score == 43.2

    def test_combined_score_takes_max_of_exact_and_spread(self):
        """精确(72) > 波及(43.2) → 最终取 72"""
        events = make_events(
            (1, "TDK", "MLCC高容", "high", 0.8, 2),     # 精确: 72
            (2, "TDK", "MLCC中低压", "high", 0.8, 2),    # 波及: 43.2
        )
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.RED
        assert score == 72.0

    def test_spread_score_can_exceed_exact_when_no_exact_match(self):
        """无精确命中时，波及评分直接使用"""
        events = make_events(
            (1, "TDK", "MLCC中低压", "high", 0.8, 2),    # 波及: 43.2
        )
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert score == 43.2

    def test_critical_severity_score(self):
        """critical 严重性：100 * 1.0 * 1.3 = 130 → capped at 100"""
        events = make_events((1, "TDK", "MLCC高容", "critical", 1.0, 3))
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert score == 100.0  # capped

    def test_multiple_events_max_score(self):
        """多个事件时取最高评分"""
        events = make_events(
            (1, "TDK", "MLCC高容", "low", 0.5, 0),       # 25*0.5*1.0 = 12.5
            (2, "TDK", "MLCC高容", "high", 1.0, 3),      # 75*1.0*1.3 = 97.5
            (3, "TDK", "MLCC高容", "medium", 0.8, 1),    # 50*0.8*1.1 = 44
        )
        matcher = BOMMatcher(events)
        level, score, result_events, reason = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert len(result_events) == 3
        assert score == 97.5


# ── 品牌匹配 ─────────────────────────────────────────────

class TestBrandMatching:

    def test_exact_case_insensitive_brand_match(self):
        events = make_events((1, "tdk", "MLCC高容"))
        matcher = BOMMatcher(events)
        level, score, result_events, _ = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.RED

    def test_different_brand_same_category_spreads_via_ancestor(self):
        """同类事件（muRata MLCC高容）通过祖先品类路径波及 TDK MLCC高容：
           虽然品牌不匹配，但同品类事件对供应链有指示意义。"""
        events = make_events((1, "muRata", "MLCC高容"))
        matcher = BOMMatcher(events)
        level, score, result_events, _ = matcher.match_item(make_item("TDK", "MLCC高容"))
        assert level == RiskLevel.YELLOW
        assert len(result_events) == 1

    def test_standardized_brand_matches_alias(self):
        """normalize_brand 将 '村田' 标准化为 '村田/Murata'，event brand='Murata' 应匹配"""
        item = make_item("村田", "MLCC高容")
        events = make_events((1, "Murata", "MLCC高容"))
        matcher = BOMMatcher(events)
        level, score, result_events, _ = matcher.match_item(item)
        assert level == RiskLevel.RED
