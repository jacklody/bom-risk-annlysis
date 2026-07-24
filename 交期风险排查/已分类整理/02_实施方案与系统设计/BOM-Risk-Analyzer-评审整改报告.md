# BOM-Risk-Analyzer v3.2 评审与整改报告

> **评审日期**：2026-06-29
> **评审范围**：`BOM-Risk-Analyzer-patch` 全量代码（后端 API / 服务层 / 上游模块 / 前端 / 测试 / 部署脚本）
> **评审角色**：QA 测试验收 + 开发工程师双视角

---

## 一、项目概况

BOM 物料风险预警系统，从 v0.2 演进到 v3.2/v3.3 MVP。核心能力包括：品类识别（高容MLCC）、情报可信度评分、双轨风险引擎（材料传导轨 + 供需信号轨）、行情收件箱、优选库治理、多源实时供应数据（LCSC / Mouser / DigiKey / 观芯台）。

**整体评估**：思路正确、骨架完整，但集成交付约完成 **60%**。核心引擎已实现但未真正参与最终决策，品类体系碎片化，多处逻辑需整改后才能上线生产。

---

## 二、严重问题（必须修复，阻塞上线）

### 2.1 外部 API 访问凭证未受保护 🚨

**文件**：`backend/.env`

该文件包含真实的生产环境第三方 API 访问凭证（供应商搜索 API Key 及 OAuth2 Client Credentials）。虽然 `.gitignore` 排除了 `.env`，但该文件当前存在于项目目录中，存在被意外提交或分发的风险。

**整改要求**：
1. 立即在各第三方平台后台轮换当前凭证
2. 确认凭证未被提交到 git 历史
3. 真实凭证通过环境变量或密钥管理服务注入，不要写入项目目录

---

### 2.2 风险等级体系不一致，导致匹配断裂

**涉及文件**：
- `backend/app/models/bom.py` — `RiskLevel` 枚举仅有 `red / yellow / green / gray`
- `backend/app/services/upstream/dual_track_risk_engine.py` — `_level()` 函数输出 `red / orange / yellow / green / gray`
- `backend/app/api/risk_analysis.py` — `_combine_risk_level()` 只认识 `gray / green / yellow / red`

当双轨引擎返回 `"orange"` 时，`RiskLevel` 枚举和合并函数均无法识别，可能导致 `ValueError` 或结果被静默丢弃。`evaluate_supply_risk()` 返回的 `production_risk_level` 使用 `RiskLevel` 枚举值，但 `BomItem.production_risk_level` 列是 `String(16)`，类型不一致。

**整改要求**：
1. 统一为一个风险等级枚举，增加 `ORANGE = "orange"`
2. `evaluate_supply_risk()` 和 `BomItem.production_risk_level` 列类型统一
3. `_combine_risk_level()` 增加 `orange` 档位的处理

---

### 2.3 双轨风险引擎未接入最终决策 —— 核心设计意图未兑现

**涉及文件**：
- `backend/app/api/risk_analysis.py`（`analyze_bom` 函数）
- `backend/app/services/upstream/risk_context_builder.py`（`build_v32_context` 函数）

当前 `analyze_bom` 中，最终风险等级由三路旧逻辑用 `max()` 拼凑决定。`v32_risk_level`（可能是 `orange`）仅作为 `v32_*` 前缀字段附加到 JSON 响应中，**完全不影响最终风险等级**。这是 v3.2 MVP 最核心的设计意图（材料传导 + 供需信号双轨评估），但实际未兑现。

```python
# 旧逻辑驱动最终决策
level = _combine_risk_level(market_level, supply.production_risk_level)
intel_rank = _risk_rank(intel_result.risk_level)
if intel_rank > _risk_rank(level.value):
    level = RiskLevel(intel_result.risk_level)

# v3.2 双轨引擎只是装饰性附加
v32_context = _build_v32_context(item, events, rd, commonality)
results["items"].append(_item_payload(..., v32_context))
```

**整改要求**：
1. 将双轨引擎的 `v32_risk_level` 纳入最终风险决策
2. 统一等级体系后设计融合权重（建议：双轨引擎 0.4 + 行情事件 0.3 + 行情情报 0.2 + 供应链 0.1），替代简单的 `max()`
3. 至少让 `v32_risk_level` 的 `red` 能触发最终 `red`，`orange` 至少触发 `yellow`

---

## 三、高优先级问题（本迭代必须修复）

### 3.1 四套风险引擎并行但品类体系互不兼容

系统中存在 **四套独立的品类分类逻辑**，同一物料在不同系统中被分类为不同品类：

| 系统 | 高容MLCC表示 | MCU表示 | 节点数 | 用途 |
|---|---|---|---|---|
| `category_tree.py` | 无此分类 | `MCU/微控制器` | ~30 | 事件波及匹配 |
| `category_classifier.py` | `high_cap_mlcc` | `mcu` | 9种规则 | 双轨引擎 |
| `market_intel.py` | `high_cap_mlcc` | `mcu` | 15个品类 | 行情情报 |
| `supply_risk.py` | 不识别 | `MCU`（大写） | 12种长交期品类 | 供应链评估 |
| `market_notice_parser.py` | `high_cap_mlcc` | `mcu` | 内联~70行 | 行情收件箱 |

**直接后果**：
- 物料被 v3.2 分类器识别为 `high_cap_mlcc`，但 `BOMMatcher` 用 `category_tree` 匹配事件时找不到对应节点，靠 `_merge_v32_events()` 事后补丁桥接
- `film_capacitor`（薄膜电容）被 `category_classifier` 正确识别，但 `MarketIntelEngine` 的 `CATEGORY_MARKET_RISK` 无对应条目，行情情报静默丢失
- `category_classifier` 只覆盖 9 种品类规则，大量物料归为 `unknown`，后续所有风险评估都不可用

**整改要求**：
1. 以 `category_classifier.py` 的输出为唯一品类标准，扩展其覆盖范围（当前仅9种→目标20+种）
2. `category_tree.py` 增加 v3.2 品类节点（high_cap_mlcc, power_ic, film_capacitor 等）
3. `market_intel.py` 的 `CATEGORY_MARKET_RISK` 补齐所有 `category_classifier` 能输出的品类
4. `market_notice_parser._extract_category()` 改为复用 `category_classifier.classify_component_category()`
5. `supply_risk.py` 的 `_LONG_LEAD_CATEGORY_WEEKS` 键名对齐 v3.2 品类名

---

### 3.2 API 端点无异常处理，外部依赖故障会直接 500

**文件**：`backend/app/api/risk_analysis.py`

`analyze_bom()` 和 `analyze_all_projects()` 中调用 `supply_svc.query_batch(mpns)` 没有任何 try/except。网络超时、DNS 失败等都会导致整个请求 500 且不写数据库。

**整改要求**：用 try/except 包裹外部调用，失败时降级为仅事件匹配模式，确保核心 BOM 分析不中断。

---

### 3.3 全局单例模式在异步/多 Worker 下有状态污染风险

**涉及文件**：
- `backend/app/api/risk_analysis.py:27` — `_supply_data_svc`
- `backend/app/api/supply.py:8` — `_service`

两个模块各自创建独立的 `SupplyDataService` 全局实例。`uvicorn --workers > 1` 时 HTTP 连接池重复创建，关闭时可能遗漏 `shutdown()`。

**整改要求**：使用 FastAPI `lifespan` 事件创建单例，存入 `app.state`。

---

### 3.4 供应链实时数据未充分用于风险评估

`build_v32_context()` 对实时数据的利用仅使用了 `total_stock == 0` 和 `lead_time_days` 两项：

```python
def _body_signals(realtime_data, market_facts):
    return {
        "stock_down": bool(total_stock == 0),   # 仅判断是否为零
        "lead_time_weeks": lead_time_weeks,      # 仅传入交期
    }
```

以下从 API 获取的维度**完全没有进入双轨引擎**：
- `supplier_count` — 可用于评估供应集中度风险
- `lifecycle_status` — EOL/Obsolete 应直接触发高风险
- `unit_price` — 价格异常波动是重要信号

**整改要求**：
1. `supplier_count` 映射为缓冲因子（≥3 → buffer +15，=1 → buffer -10）
2. `lifecycle_status` 作为独立风险维度：`EOL/Obsolete` → 直接 `red`，`NRND` → `orange`
3. `unit_price` 纳入供需信号轨（需建立价格历史基准，可暂时跳过）

---

### 3.5 行情知识库是静态数据，无时效性衰减

**文件**：`backend/app/knowledge/market_intel.py`

`MARKET_INTEL_ENTRIES` 是硬编码的特定季度行情数据（2026 Q2）。行情变化后旧情报继续发警报，新风险无法自动感知。且同一事件反复采集时 `cross_validated` 无限递增（见 `event_collector.py:302-303`），旧事件反而越来越"权威"。

**整改要求**：
1. 为 `MarketIntelEntry` 增加 `effective_date` 和 `expiry_date` 字段
2. 超期情报自动降权（如每超过 30 天置信度 × 0.9）
3. `cross_validated` 增加上限（如 max=5），防止无限增长

---

### 3.6 风险变更历史从未被写入

**文件**：`backend/app/models/bom.py`、`backend/app/api/risk_analysis.py`

Model 定义了 `last_risk_level` 和 `risk_changed_at` 字段，但**整个代码库没有任何地方写入它们**。每次分析直接覆盖 `risk_level` 和 `risk_reason`，变更历史全部丢失。

**整改要求**：在分析前保存旧状态：
```python
if item.risk_level and item.risk_level.value != level.value:
    item.last_risk_level = item.risk_level.value
    item.risk_changed_at = datetime.now(timezone.utc)
```

---

## 四、中优先级问题（建议本迭代修复）

### 4.1 大量代码重复

| 重复功能 | 出现位置（≥2处） | 行数估计 |
|---|---|---|
| `_is_standard_package()` | `api/risk_analysis.py:537`、`services/supply_risk.py:341` | ~15行×2 |
| `_event_matches_v32_category` | `api/risk_analysis.py:85`、`services/upstream/market_inbox_service.py:239` | ~15行×2 |
| 风险等级合并逻辑 | `api/risk_analysis.py:218-223`、`api/market_intel.py:163-170` | ~10行×2 |
| `_merge_v32_events` / `_merge_v33_category_events` | `api/risk_analysis.py:101`、`market_inbox_service.py:220` | ~15行×2 |
| `analyze_bom` 和 `analyze_all_projects` 核心循环 | `api/risk_analysis.py` | ~150行重复 |
| 实时数据到 BomItem 字段填充 | `api/risk_analysis.py:_apply_supply_fields`、`services/supply_data.py:apply_to_bom_item` | ~20行×2 |

**整改要求**：抽取公共模块 `backend/app/utils/` 或 `backend/app/services/shared/`，消除以上重复。

---

### 4.2 多处访问私有方法

| 调用位置 | 行号 |
|---|---|
| `api/events.py` `forward_article` → `collector._save_event()` | L183 |
| `api/events.py` `trigger_media_crawl` → `collector._save_event()` | L241 |
| `api/events.py` `add_manual_event` → `collector._save_event()` | L274 |
| `services/upstream/market_inbox_service.py` `submit_notice` | L63 |
| `services/upstream/market_inbox_service.py` `review_signal` | L284 |

**整改要求**：`EventCollector` 提供公共的 `save_event(event_data, min_confidence=None)` 方法。

---

### 4.3 数据库迁移脆弱

**文件**：`backend/app/database.py`

`_migrate_bom_item_supply_columns()` 使用原生 SQL `ALTER TABLE ADD COLUMN`。SQLite 不支持 `IF NOT EXISTS` 语法，重复运行可能报错。

**整改要求**：引入 Alembic 做正式迁移管理，或创建 `_migrations` 记录表防止重复执行。

---

### 4.4 事件匹配引擎的逻辑缺陷

**文件**：`backend/app/services/bom_matcher.py`

- **短路返回**（L62-69）：规则1命中后立即返回 RED。物料同时匹配"涨价"和"EOL停产"时，EOL 信号被吞掉
- **品牌空值惩罚**（L112-115）：品牌为空时 `_match_brand` 直接返回 False，物料永远只能走到 YELLOW，即使品类正经历严重缺货
- **依赖事后补丁**：不使用 v3.2 分类器，需 `_merge_v32_events` 补救，对每个 item-event 对重复调用 `classify_component_category`，复杂度 O(n×m)

**整改要求**：
1. 改为收集所有匹配事件后再综合评分，不短路
2. 品牌为空但品类精确且有 critical 事件时，适度提高等级
3. 内置 v3.2 品类分类，消除 `_merge_v32_events` 补丁

---

### 4.5 多源数据聚合策略可能低估风险

**文件**：`backend/app/services/supply_data.py:105-106`

```python
merged.total_stock = max(...)         # 库存取最大 — 掩盖短缺风险
merged.lead_time_days = min(...)      # 交期取最短 — 掩盖长交期预警
merged.unit_price = min(...)          # 单价取最低 — 掩盖涨价信号
```

"取最优"对采购决策合理，但对风险评估会低估风险。DigiKey 显示 0 库存 84 天，LCSC 显示 5000 库存 7 天 → 聚合为"供应充足"，但 DigiKey 数据可能反映原厂配额削减。

**整改要求**：聚合结果同时输出 `best_case` 和 `worst_case`，风险评估使用 worst_case。

---

### 4.6 SupplyDataService 构造时即初始化所有源

**文件**：`backend/app/services/supply_data.py:50-57`

`__init__` 无条件创建 4 个数据源对象，即使某些源未配置凭证。

**整改要求**：懒加载 —— 在 `initialize()` 中按配置创建已启用的源。

---

### 4.7 测试覆盖不足

当前 18 个测试文件覆盖偏算法层，缺失：

| 缺失类型 | 说明 |
|---|---|
| API 契约测试 | 验证 `/api/risk/analyze/{id}` 返回的 JSON schema |
| 数据源 mock 测试 | 用 mock 响应验证 `_merge_best` 聚合逻辑 |
| 端到端场景 | 上传 BOM → 采集 → 分析 → 验证风险等级的完整链路 |
| `supply_risk.py` 独立测试 | 当前无该模块的专属测试文件 |
| `market_notice_parser.py` 边界测试 | 空文本、纯英文、HTML 标签文本等场景 |

**整改要求**：至少为 `supply_risk.py`（EOL/交期/库存/品牌 4 个维度）和 `analyze_bom` 端点补充测试。

---

## 五、低优先级问题（可后续迭代）

| 编号 | 问题 | 文件 | 建议 |
|---|---|---|---|
| 5.1 | 部署脚本硬编码文件列表 | `deploy-v3.2-mvp.ps1` L186-204 | 改为通配复制 |
| 5.2 | 版本号滞后 | `main.py:19` `version="0.2.0"` | 更新为 `"3.2.0"` |
| 5.3 | CORS 全开 | `main.py:23` `allow_origins=["*"]` | 从配置读取 |
| 5.4 | 前端 dist 膨胀 | `frontend/dist/` 多版本产物堆积 | 构建前清理 |
| 5.5 | 品牌列表硬编码 | `market_notice_parser.py:45-74` | 从 `brand_category_map.py` 动态生成 |
| 5.6 | 字符串拼接构造原因 | 多处 `f"{r1}；{r2}"` | 改为 `list[str]` + join |
| 5.7 | 类型注解不完整 | 多处 `dict` 替代 `TypedDict` | 定义关键数据结构 |

---

## 六、功能缺失清单（建议后续版本补充）

| 功能 | 当前状态 | 优先级 |
|---|---|---|
| 预测验证闭环（预测→验证→反馈置信度） | ❌ 仅有命中/未命中检查 | P1 |
| 误报率/命中率统计面板 | ❌ 未实现 | P1 |
| 风险变更通知（邮件/飞书/钉钉） | ❌ 无推送机制 | P1 |
| 替代料推荐 | ❌ `recommended_alternatives_json` 始终返回 `[]` | P2 |
| 行情情报自动过期 | ❌ 知识库为静态数据 | P2 |
| CSV 导出端点 | ❌ API 中无 CSV 导出 | P2 |
| 身份认证/多租户 | ❌ 所有项目对所有人可见 | P3 |
| 数据缓存层 | ❌ 配置项存在但未实现 | P2 |
| 历史 BOM 分析版本记录 | ❌ 每次覆盖上一次结果 | P2 |
| `category_classifier` 品类覆盖 | ❌ 仅 9 种，大量归为 unknown | P1 |

---

## 七、整改优先级汇总

| 编号 | 问题 | 严重程度 | 建议完成时间 |
|---|---|---|---|
| 2.1 | 外部 API 凭证未受保护 | 🚨 严重 | **立即** |
| 2.2 | 风险等级体系不一致 | 🚨 严重 | **立即** |
| 2.3 | 双轨引擎未接入最终决策 | 🚨 严重 | 本迭代 |
| 3.1 | 品类体系碎片化 | 🔴 高 | 本迭代 |
| 3.2 | API 无异常处理 | 🔴 高 | 本迭代 |
| 3.3 | 全局单例状态污染 | 🔴 高 | 本迭代 |
| 3.4 | 实时数据未充分使用 | 🔴 高 | 本迭代 |
| 3.5 | 行情知识库无时效性 | 🔴 高 | 本迭代 |
| 3.6 | 风险变更历史未写入 | 🔴 高 | 本迭代 |
| 4.1 | 代码重复（6处） | 🟡 中 | 本迭代 |
| 4.2 | 访问私有方法（5处） | 🟡 中 | 本迭代 |
| 4.3 | 数据库迁移脆弱 | 🟡 中 | 本迭代 |
| 4.4 | 事件匹配引擎逻辑缺陷 | 🟡 中 | 本迭代 |
| 4.5 | 多源聚合低估风险 | 🟡 中 | 本迭代 |
| 4.6 | 数据源初始化浪费 | 🟡 中 | 本迭代 |
| 4.7 | 测试覆盖不足 | 🟡 中 | 本迭代 |
| 5.1~5.7 | 低优先级问题（7项） | 🟢 低 | 后续迭代 |
| 六 | 功能缺失（10项） | 📋 新需求 | 后续版本 |

---

## 八、架构优化路线图（建议）

```
Phase 1（本迭代，约 5-7 人天）
├── 2.1 凭证轮换 + 安全整改
├── 2.2 风险等级体系统一（增加 ORANGE，对齐所有模块）
├── 2.3 双轨引擎接入最终决策链路
├── 3.1 统一品类分类器（以 category_classifier 为标准，扩展覆盖）
├── 3.2 API 异常处理加固
├── 3.6 风险变更追踪（写入 last_risk_level / risk_changed_at）
└── 4.1 抽取重复代码到共享模块

Phase 2（下一迭代，约 3-5 人天）
├── 3.3 FastAPI lifespan 单例重构
├── 3.4 实时数据充分接入双轨引擎
├── 3.5 行情知识库时效性机制
├── 4.4 事件匹配引擎修复（消除短路、消除事后补丁）
├── 4.5 多源聚合增加 worst-case 视图
├── 4.7 补充 API 层和 supply_risk 测试
└── 5.1~5.7 低优先级问题处理

Phase 3（后续版本）
└── 六 功能缺失清单逐项实现（预测验证、通知、替代料推荐等）
```

---

> **评审人**：Claude (QA + 开发双视角)
> **目标项目**：`D:\1项目清单\交期风险排查\BOM-Risk-Analyzer-patch`
