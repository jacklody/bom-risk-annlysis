"""T2-004: Octopart/Nexar 生命周期数据接入 — 单元测试

覆盖:
  - 正常查询 (GraphQL 成功)
  - API 超时
  - 配额耗尽
  - 缓存命中 (不消耗配额)
  - 降级策略 (fallback DigiKey/Mouser)
  - 生命周期映射 (NRND/EOL/Active/Unknown)
  - 配额管理 (降级阈值)
  - OAuth2 认证失败
  - bom_matcher 风险等级调整
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import httpx

from app.services.sources.base import SourceResult
from app.services.sources.octopart_source import (
    OctopartSource,
    NEXAR_GRAPHQL_URL,
    NEXAR_OAUTH_URL,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_NRND,
    LIFECYCLE_EOL,
    LIFECYCLE_UNKNOWN,
    VALID_LIFECYCLE_STATUSES,
)
from app.models.bom import RiskLevel


# ════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════

@pytest.fixture
def mock_settings_nexar(monkeypatch):
    """启用 Nexar 配置"""
    monkeypatch.setattr("app.config.settings.nexar_enabled", True)
    monkeypatch.setattr("app.config.settings.nexar_client_id", "test_client_id")
    monkeypatch.setattr("app.config.settings.nexar_client_secret", "test_client_secret")
    monkeypatch.setattr("app.config.settings.nexar_access_token", "")
    monkeypatch.setattr("app.config.settings.cache_ttl_seconds", 86400)


@pytest.fixture
def octopart_source(mock_settings_nexar):
    """创建配置好的 OctopartSource 实例"""
    return OctopartSource(
        client_id="test_client_id",
        client_secret="test_client_secret",
        monthly_quota=100,
    )


@pytest.fixture
def octopart_unconfigured(monkeypatch):
    """未配置的 OctopartSource"""
    monkeypatch.setattr("app.config.settings.nexar_enabled", False)
    monkeypatch.setattr("app.config.settings.nexar_client_id", "")
    monkeypatch.setattr("app.config.settings.nexar_client_secret", "")
    monkeypatch.setattr("app.config.settings.cache_ttl_seconds", 86400)
    return OctopartSource(client_id="", client_secret="")


def _make_graphql_response(
    lifecycle_status: str = "Active",
    factory_lead_days: int = None,
    mpn: str = "AK4499EQ",
    manufacturer: str = "AKM",
    rohs: str = "Compliant",
    reach: str = "",
    category: str = "Audio - ADC",
) -> dict:
    """构造模拟 GraphQL 响应"""
    return {
        "data": {
            "supSearchMpn": {
                "results": [
                    {
                        "part": {
                            "mpn": mpn,
                            "manufacturer": {"name": manufacturer} if manufacturer else None,
                            "category": {"name": category, "path": "/ICs/Audio", "parentId": "1"} if category else None,
                            "shortDescription": "High-performance audio ADC",
                            "lifecycleStatus": lifecycle_status,
                            "factoryLeadDays": factory_lead_days,
                            "rohsStatus": rohs,
                            "reachStatus": reach,
                            "url": f"https://octopart.com/{mpn}",
                        }
                    }
                ]
            }
        }
    }


def _mock_httpx_client(
    token_response: dict = None,
    graphql_response: dict = None,
    graphql_status: int = 200,
    token_status: int = 200,
    timeout: bool = False,
):
    """创建模拟的 httpx.AsyncClient"""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False

    # Token response
    token_resp = MagicMock()
    token_resp.status_code = token_status
    token_resp.json.return_value = token_response or {
        "access_token": "test_token_12345",
        "expires_in": 600,
    }
    if token_status >= 400:
        token_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=token_resp
        )
    else:
        token_resp.raise_for_status.return_value = None

    # GraphQL response
    gql_resp = MagicMock()
    gql_resp.status_code = graphql_status
    if graphql_response is not None:
        gql_resp.json.return_value = graphql_response
    if graphql_status >= 400:
        gql_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=gql_resp
        )
    else:
        gql_resp.raise_for_status.return_value = None

    async def post_side_effect(url, **kwargs):
        if "connect/token" in url or "token" in url.lower():
            if timeout:
                raise httpx.TimeoutException("Connection timed out")
            return token_resp
        else:
            if timeout:
                raise httpx.TimeoutException("Connection timed out")
            return gql_resp

    mock_client.post = AsyncMock(side_effect=post_side_effect)
    mock_client.aclose = AsyncMock()

    return mock_client


# ════════════════════════════════════════════════════════════
# 1. 正常查询
# ════════════════════════════════════════════════════════════

class TestNormalQuery:
    """正常 GraphQL 查询测试"""

    @pytest.mark.asyncio
    async def test_query_active_part(self, octopart_source):
        """TC-01: 查询 Active 状态物料"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(
                lifecycle_status="Active",
                factory_lead_days=42,
                mpn="STM32F103C8T6",
                manufacturer="STMicroelectronics",
            )
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("STM32F103C8T6")

        assert result.match_status == "hit"
        assert result.lifecycle_status == LIFECYCLE_ACTIVE
        assert result.mpn_matched == "STM32F103C8T6"
        assert result.manufacturer == "STMicroelectronics"
        assert result.lead_time_days == 42
        assert result.is_available is True
        assert octopart_source.quota_used == 1

    @pytest.mark.asyncio
    async def test_query_nrnd_part(self, octopart_source):
        """TC-02: 查询 NRND 状态物料 (AKM 场景)"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(
                lifecycle_status="Not Recommended for New Designs",
                mpn="AK4499EQ",
                manufacturer="AKM",
                category="Audio - ADC",
            )
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("AK4499EQ")

        assert result.match_status == "hit"
        assert result.lifecycle_status == LIFECYCLE_NRND
        assert result.mpn_matched == "AK4499EQ"
        assert result.is_available is True

    @pytest.mark.asyncio
    async def test_query_eol_part(self, octopart_source):
        """TC-03: 查询 EOL 状态物料"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(
                lifecycle_status="End of Life",
                mpn="LT3080",
                manufacturer="Analog Devices",
            )
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("LT3080")

        assert result.match_status == "hit"
        assert result.lifecycle_status == LIFECYCLE_EOL

    @pytest.mark.asyncio
    async def test_query_returns_compliance_info(self, octopart_source):
        """TC-04: 查询结果包含合规状态"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(
                lifecycle_status="Active",
                rohs="Compliant",
                reach="REACH Compliant",
            )
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("TEST-PART-001")

        assert result.match_status == "hit"
        assert "RoHS:Compliant" in result.raw_summary
        assert "REACH:REACH Compliant" in result.raw_summary

    @pytest.mark.asyncio
    async def test_query_not_found(self, octopart_source):
        """TC-05: 查询不存在的物料"""
        mock_client = _mock_httpx_client(
            graphql_response={"data": {"supSearchMpn": {"results": []}}}
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("NONEXISTENT-PART")

        assert result.match_status == "not_found"
        assert octopart_source.quota_used == 1
        # 未命中也缓存
        assert octopart_source.cache_size == 1


# ════════════════════════════════════════════════════════════
# 2. API 超时
# ════════════════════════════════════════════════════════════

class TestAPITimeout:
    """API 超时场景测试"""

    @pytest.mark.asyncio
    async def test_graphql_timeout(self, octopart_source):
        """TC-06: GraphQL 查询超时"""
        mock_client = _mock_httpx_client(timeout=True)
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("STM32F103C8T6")

        assert result.match_status == "not_found"
        assert octopart_source.quota_used == 1

    @pytest.mark.asyncio
    async def test_oauth_timeout(self, octopart_source):
        """TC-07: OAuth 获取 token 超时"""
        mock_client = _mock_httpx_client(timeout=True)
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()

        result = await octopart_source.query_by_mpn("STM32F103C8T6")

        assert result.match_status == "not_found"
        # token 获取失败但 queries_used 仍加1（实际是API调用失败）
        assert octopart_source.quota_used == 1


# ════════════════════════════════════════════════════════════
# 3. 配额耗尽 & 管理
# ════════════════════════════════════════════════════════════

class TestQuotaManagement:
    """配额管理测试"""

    @pytest.mark.asyncio
    async def test_quota_exhausted(self, octopart_source):
        """TC-08: 配额耗尽时拒绝查询"""
        octopart_source._queries_used = 100

        result = await octopart_source.query_by_mpn("STM32F103C8T6")

        assert result.match_status == "quota_exhausted"
        assert "配额已耗尽" in result.error_reason

    @pytest.mark.asyncio
    async def test_quota_degraded_high_risk_allowed(self, octopart_source):
        """TC-09: 配额<20%时仅查询高风险物料 (red)"""
        octopart_source._queries_used = 85  # 剩余15%

        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response()
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        # 高风险物料 — 允许查询
        result = await octopart_source.query_by_mpn("AK4499EQ", risk_level="red")

        assert result.match_status == "hit"

    @pytest.mark.asyncio
    async def test_quota_degraded_low_risk_blocked(self, octopart_source):
        """TC-10: 配额<20%时拒绝低风险物料"""
        octopart_source._queries_used = 85  # 剩余15%

        result = await octopart_source.query_by_mpn("STM32F103", risk_level="green")

        assert result.match_status == "quota_degraded"
        assert "<20%" in result.error_reason

    @pytest.mark.asyncio
    async def test_quota_degraded_orange_allowed(self, octopart_source):
        """TC-11: 配额<20%时 orange 风险物料允许查询"""
        octopart_source._queries_used = 90  # 剩余10%

        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(lifecycle_status="End of Life")
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("LT3080", risk_level="orange")
        assert result.match_status == "hit"

    def test_quota_info(self, octopart_source):
        """TC-12: 配额查询接口"""
        octopart_source._queries_used = 30
        info = octopart_source.get_quota_info()

        assert info["monthly_quota"] == 100
        assert info["queries_used"] == 30
        assert info["queries_remaining"] == 70
        assert info["usage_percentage"] == 30.0


# ════════════════════════════════════════════════════════════
# 4. 缓存机制
# ════════════════════════════════════════════════════════════

class TestCacheMechanism:
    """缓存命中/过期测试"""

    @pytest.mark.asyncio
    async def test_cache_hit_no_api_call(self, octopart_source):
        """TC-13: 缓存命中时不调用 API"""
        # 先手动写入缓存
        cached_result = SourceResult(
            source="octopart",
            mpn_queried="STM32F103C8T6",
            mpn_matched="STM32F103C8T6",
            lifecycle_status=LIFECYCLE_ACTIVE,
            match_status="hit",
        )
        octopart_source._cache["STM32F103C8T6"] = {
            "result": octopart_source._source_result_to_dict(cached_result),
            "timestamp": time.time(),
        }

        # 查询 — 不应消耗配额
        result = await octopart_source.query_by_mpn("STM32F103C8T6")

        assert result.match_status == "hit"
        assert result.lifecycle_status == LIFECYCLE_ACTIVE
        assert octopart_source.quota_used == 0  # 未调用 API

    @pytest.mark.asyncio
    async def test_cache_expired_triggers_api_call(self, octopart_source):
        """TC-14: 缓存过期后触发 API 调用"""
        # 写入过期缓存
        octopart_source._cache["OLD-PART"] = {
            "result": octopart_source._source_result_to_dict(SourceResult(
                source="octopart", mpn_queried="OLD-PART", match_status="hit",
            )),
            "timestamp": time.time() - 86401,  # 24h+1s 前
        }

        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(mpn="OLD-PART")
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("OLD-PART")

        assert result.match_status == "hit"
        assert octopart_source.quota_used == 1  # 调用了 API

    @pytest.mark.asyncio
    async def test_second_query_same_mpn_no_extra_quota(self, octopart_source):
        """TC-15: 第二次查询同一 MPN 不消耗配额 (缓存验证)"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(mpn="AK4499EQ")
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        # 第一次查询
        result1 = await octopart_source.query_by_mpn("AK4499EQ")
        assert result1.match_status == "hit"
        assert octopart_source.quota_used == 1

        # 第二次查询 — 走缓存
        result2 = await octopart_source.query_by_mpn("AK4499EQ")
        assert result2.match_status == "hit"
        assert octopart_source.quota_used == 1  # 配额不变

    def test_clear_cache(self, octopart_source):
        """TC-16: 清空缓存"""
        octopart_source._cache["PART-A"] = {
            "result": {}, "timestamp": time.time()
        }
        octopart_source._cache["PART-B"] = {
            "result": {}, "timestamp": time.time()
        }
        assert octopart_source.cache_size == 2

        octopart_source.clear_cache()
        assert octopart_source.cache_size == 0


# ════════════════════════════════════════════════════════════
# 5. 降级策略
# ════════════════════════════════════════════════════════════

class TestDegradation:
    """降级策略测试"""

    def test_should_degrade_when_unconfigured(self, octopart_unconfigured):
        """TC-17: 未配置时降级"""
        assert octopart_unconfigured.should_degrade_to_existing_sources() is True

    def test_should_degrade_when_quota_exhausted(self, octopart_source):
        """TC-18: 配额耗尽时降级"""
        octopart_source._queries_used = 100
        assert octopart_source.should_degrade_to_existing_sources() is True

    def test_should_not_degrade_when_available(self, octopart_source):
        """TC-19: 可用时不降级"""
        octopart_source._queries_used = 50
        assert octopart_source.should_degrade_to_existing_sources() is False

    @pytest.mark.asyncio
    async def test_unconfigured_returns_not_configured(self, octopart_unconfigured):
        """TC-20: 未配置时返回 not_configured"""
        result = await octopart_unconfigured.query_by_mpn("STM32F103C8T6")
        assert result.match_status == "not_configured"
        assert "未配置" in result.error_reason


# ════════════════════════════════════════════════════════════
# 6. 生命周期映射
# ════════════════════════════════════════════════════════════

class TestLifecycleMapping:
    """生命周期状态归一化映射测试"""

    def test_active_variants(self):
        """TC-21: Active 各种写法归一化"""
        assert OctopartSource.normalize_lifecycle_status("Active") == LIFECYCLE_ACTIVE
        assert OctopartSource.normalize_lifecycle_status("In Production") == LIFECYCLE_ACTIVE
        assert OctopartSource.normalize_lifecycle_status("Mass Production") == LIFECYCLE_ACTIVE
        assert OctopartSource.normalize_lifecycle_status("production") == LIFECYCLE_ACTIVE
        assert OctopartSource.normalize_lifecycle_status("ACTIVE") == LIFECYCLE_ACTIVE

    def test_nrnd_variants(self):
        """TC-22: NRND 各种写法归一化"""
        assert OctopartSource.normalize_lifecycle_status("NRND") == LIFECYCLE_NRND
        assert OctopartSource.normalize_lifecycle_status("Not Recommended for New Designs") == LIFECYCLE_NRND
        assert OctopartSource.normalize_lifecycle_status("Not Recommended") == LIFECYCLE_NRND
        assert OctopartSource.normalize_lifecycle_status("nrnd") == LIFECYCLE_NRND

    def test_eol_variants(self):
        """TC-23: EOL 各种写法归一化"""
        assert OctopartSource.normalize_lifecycle_status("EOL") == LIFECYCLE_EOL
        assert OctopartSource.normalize_lifecycle_status("End of Life") == LIFECYCLE_EOL
        assert OctopartSource.normalize_lifecycle_status("Obsolete") == LIFECYCLE_EOL
        assert OctopartSource.normalize_lifecycle_status("Discontinued") == LIFECYCLE_EOL
        assert OctopartSource.normalize_lifecycle_status("Last Time Buy") == LIFECYCLE_EOL
        assert OctopartSource.normalize_lifecycle_status("eol") == LIFECYCLE_EOL

    def test_unknown_variants(self):
        """TC-24: Unknown / 空值归一化"""
        assert OctopartSource.normalize_lifecycle_status("") == LIFECYCLE_UNKNOWN
        assert OctopartSource.normalize_lifecycle_status(None) == LIFECYCLE_UNKNOWN
        assert OctopartSource.normalize_lifecycle_status("Something Weird") == LIFECYCLE_UNKNOWN

    def test_valid_statuses_completeness(self):
        """TC-25: 生命周期常量完整性"""
        assert VALID_LIFECYCLE_STATUSES == {
            LIFECYCLE_ACTIVE, LIFECYCLE_NRND, LIFECYCLE_EOL, LIFECYCLE_UNKNOWN
        }


# ════════════════════════════════════════════════════════════
# 7. BOM Matcher 生命周期风险调整
# ════════════════════════════════════════════════════════════

class TestBOMMatcherLifecycleAdjust:
    """bom_matcher 生命周期风险等级调整测试"""

    def _make_matcher(
        self, lifecycle: str = LIFECYCLE_ACTIVE, has_octopart: bool = True
    ):
        """创建带 mock octopart 的 BOMMatcher"""
        from app.services.bom_matcher import BOMMatcher

        if has_octopart:
            octopart = MagicMock(spec=OctopartSource)
            octopart.is_configured = True
            cached = SourceResult(
                source="octopart",
                mpn_queried="TEST-MPN",
                lifecycle_status=lifecycle,
                match_status="hit",
            )
            octopart._cache_get = MagicMock(return_value=cached)
            octopart.clean_mpn = MagicMock(side_effect=lambda x: x)
            matcher = BOMMatcher(active_events=[], octopart_source=octopart)
        else:
            matcher = BOMMatcher(active_events=[])

        return matcher

    def test_active_no_adjustment(self):
        """TC-26: Active 状态不调整风险等级"""
        matcher = self._make_matcher(lifecycle=LIFECYCLE_ACTIVE)
        level, reason = matcher.adjust_risk_by_lifecycle(
            "TEST-PART", RiskLevel.GREEN, "无风险"
        )
        assert level == RiskLevel.GREEN
        assert "生命周期" not in reason

    def test_nrnd_raises_to_yellow(self):
        """TC-27: NRND 提升至黄色"""
        matcher = self._make_matcher(lifecycle=LIFECYCLE_NRND)
        level, reason = matcher.adjust_risk_by_lifecycle(
            "AK4499EQ", RiskLevel.GREEN, "无风险"
        )
        assert level == RiskLevel.YELLOW
        assert "NRND" in reason

    def test_nrnd_already_red_stays_red(self):
        """TC-28: NRND 但已经是红色 — 保持红色"""
        matcher = self._make_matcher(lifecycle=LIFECYCLE_NRND)
        level, reason = matcher.adjust_risk_by_lifecycle(
            "AK4499EQ", RiskLevel.RED, "已命中严重事件"
        )
        assert level == RiskLevel.RED

    def test_eol_raises_to_orange(self):
        """TC-29: EOL 提升至橙色"""
        matcher = self._make_matcher(lifecycle=LIFECYCLE_EOL)
        level, reason = matcher.adjust_risk_by_lifecycle(
            "LT3080", RiskLevel.GREEN, "无风险"
        )
        assert level == RiskLevel.ORANGE
        assert "EOL" in reason

    def test_eol_with_existing_orange_raises_to_red(self):
        """TC-30: EOL + 已有橙色事件 → 提升为红色 (无替代料场景)"""
        matcher = self._make_matcher(lifecycle=LIFECYCLE_EOL)
        level, reason = matcher.adjust_risk_by_lifecycle(
            "AK4499EQ", RiskLevel.ORANGE, "品类波及事件"
        )
        assert level == RiskLevel.RED
        assert "EOL" in reason

    def test_unknown_sets_gray(self):
        """TC-31: Unknown 状态设为灰色并提示数据不足"""
        matcher = self._make_matcher(lifecycle=LIFECYCLE_UNKNOWN)
        level, reason = matcher.adjust_risk_by_lifecycle(
            "TEST-PART", RiskLevel.GREEN, "无风险"
        )
        assert level == RiskLevel.GRAY
        assert "数据不足" in reason

    def test_no_lifecycle_source_defaults_active(self):
        """TC-32: 无生命周期数据源时默认不调整"""
        matcher = self._make_matcher(has_octopart=False)
        level, reason = matcher.adjust_risk_by_lifecycle(
            "TEST-PART", RiskLevel.RED, "事件命中"
        )
        assert level == RiskLevel.RED  # 保持不变

    def test_raise_to_at_least_green_to_yellow(self):
        """TC-33: _raise_to_at_least GREEN → YELLOW"""
        from app.services.bom_matcher import BOMMatcher
        result = BOMMatcher._raise_to_at_least(RiskLevel.GREEN, RiskLevel.YELLOW)
        assert result == RiskLevel.YELLOW

    def test_raise_to_at_least_red_stays_red(self):
        """TC-34: _raise_to_at_least RED 不低于 YELLOW"""
        from app.services.bom_matcher import BOMMatcher
        result = BOMMatcher._raise_to_at_least(RiskLevel.RED, RiskLevel.YELLOW)
        assert result == RiskLevel.RED

    def test_raise_to_at_least_gray_to_yellow(self):
        """TC-35: _raise_to_at_least GRAY → YELLOW"""
        from app.services.bom_matcher import BOMMatcher
        result = BOMMatcher._raise_to_at_least(RiskLevel.GRAY, RiskLevel.YELLOW)
        assert result == RiskLevel.YELLOW


# ════════════════════════════════════════════════════════════
# 8. OAuth2 认证
# ════════════════════════════════════════════════════════════

class TestOAuth2:
    """OAuth2 认证测试"""

    @pytest.mark.asyncio
    async def test_oauth_success(self, octopart_source):
        """TC-36: OAuth2 获取 token 成功"""
        mock_client = _mock_httpx_client()
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()

        token = await octopart_source._get_token()
        assert token == "test_token_12345"
        assert octopart_source._token_expiry > time.monotonic()

    @pytest.mark.asyncio
    async def test_oauth_cached_token(self, octopart_source):
        """TC-37: 缓存的 token 不会重复获取"""
        octopart_source._token = "cached_token"
        octopart_source._token_expiry = time.monotonic() + 600

        token = await octopart_source._get_token()
        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_oauth_failure(self, octopart_source):
        """TC-38: OAuth 失败返回 None"""
        mock_client = _mock_httpx_client(token_status=401)
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()

        token = await octopart_source._get_token()
        assert token is None


# ════════════════════════════════════════════════════════════
# 9. Health Check
# ════════════════════════════════════════════════════════════

class TestHealthCheck:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, octopart_source):
        """TC-39: health_check 正常"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response()
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self, octopart_unconfigured):
        """TC-40: 未配置时 health_check 返回 False"""
        result = await octopart_unconfigured.health_check()
        assert result is False


# ════════════════════════════════════════════════════════════
# 10. 边缘场景
# ════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边缘场景测试"""

    @pytest.mark.asyncio
    async def test_empty_mpn(self, octopart_source):
        """TC-41: 空 MPN 查询"""
        result = await octopart_source.query_by_mpn("  ")
        assert result.match_status == "missing_mpn"

    @pytest.mark.asyncio
    async def test_mpn_with_packaging_suffix(self, octopart_source):
        """TC-42: 带包装后缀的 MPN 会被 clean_mpn 处理"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(mpn="STM32F103C8T6")
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("STM32F103C8T6-T/R")
        assert result.match_status == "hit"
        # clean_mpn 去除了 -T/R 后缀

    @pytest.mark.asyncio
    async def test_factory_lead_days_null(self, octopart_source):
        """TC-43: factoryLeadDays 为 null"""
        mock_client = _mock_httpx_client(
            graphql_response=_make_graphql_response(factory_lead_days=None)
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("TEST-PART")
        assert result.lead_time_days is None

    @pytest.mark.asyncio
    async def test_graphql_parse_error(self, octopart_source):
        """TC-44: GraphQL 响应格式异常"""
        mock_client = _mock_httpx_client(
            graphql_response={"data": None}
        )
        octopart_source._client = mock_client
        octopart_source._client_loop = asyncio.get_running_loop()
        octopart_source._token = "test_token"
        octopart_source._token_expiry = time.monotonic() + 600

        result = await octopart_source.query_by_mpn("TEST-PART")
        assert result.match_status == "not_found"

    def test_source_name(self, octopart_source):
        """TC-45: source_name 属性"""
        assert octopart_source.source_name == "octopart"

    def test_is_configured_true(self, octopart_source):
        """TC-46: 配置正确时 is_configured 为 True"""
        assert octopart_source.is_configured is True

    def test_is_configured_false_when_disabled(self, octopart_unconfigured):
        """TC-47: 未启用时 is_configured 为 False"""
        assert octopart_unconfigured.is_configured is False
