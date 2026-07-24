# BOM-Risk-Analyzer v3.2 深度评审与整改报告（终版）

> **评审日期**：2026-06-29
> **评审范围**：`BOM-Risk-Analyzer-patch` 全量代码（81 commits，含后端 / 前端 / 测试 / 部署脚本 / 行情知识库）
> **评审方法**：逐模块阅读全部源代码，从 QA 测试验收 + 开发工程师两个独立视角交叉验证

---

## 一、开发进度真实评估

### 1.1 Git 历史还原的开发过程

```
v36-market-events    → 市场事件管理页面
v37-market-events-operations → 事件启用/停用/影响分析
v38-market-trends-validation → 行情趋势与预测验证
v39 → v3.10         → LCSC 供应数据 + 多源并行（Mouser/DigiKey/观芯台）
```

共 **81 次提交**，3 条功能分支已合入 master。开发节奏紧凑，分支管理规范。

### 1.2 各模块完成度真实评估

| 模块 | 完成度 | 说明 |
|---|---|---|
| **A1 高容MLCC识别** | ✅ 95% | 逻辑完整，5 项测试全过，处理了非MLCC误判 |
| **A1 基础品类识别** | ⚠️ 55% | 仅覆盖 9 种品类（pcb/relay/mcu/power_ic/film_capacitor/safety_capacitor/aluminum_electrolytic_capacitor/connector/inductor_transformer + MLCC），大量物料归为 unknown |
| **A3 情报可信度评分** | ✅ 90% | 多维度加权合理，正确处理单一公众号传闻降权 |
| **A4 双轨风险引擎** | ⚠️ 70% | 引擎本身质量高，但产出未接入最终决策链 |
| **A5 依据链生成** | ✅ 85% | 依据链结构完整，处置建议有差异化 |
| **A2 人工事件录入** | ✅ 85% | 前后端完整，可信度模型桥接 |
| **v3.3 行情收件箱** | ✅ 80% | 原文→信号→事件→BOM扫描 全链路通 |
| **优选库治理** | ✅ 80% | Excel导入/品牌标准化/历史索引/选型评审完整 |
| **多源供应数据** | ⚠️ 65% | 4 个数据源接入完成，但数据未充分用于风险评估 |
| **市场行情趋势** | ✅ 80% | 时序统计/品牌品类排名/预测验证/行动队列 |
| **前端整体** | ✅ 80% | 8 个页面、7 套 API 客户端、组件测试 + E2E |

### 1.3 实际可演示 vs 文档宣称

文档（DEMO-V3.2.md）宣称的能力，逐项验证：

| 宣称 | 实际 | 差距 |
|---|---|---|
| "高容MLCC与关键物料品类识别" | ✅ 确实可用 | 无 |
| "双轨引擎：材料传导轨、需求/供应轨" | ⚠️ 引擎计算了但仅作展示 | **引擎产出未参与最终风险决策** |
| "BOM行级 v3.2 字段" | ✅ 7 个字段均有返回 | 但 v32_risk_level 与 risk_level 可能矛盾 |
| "CSV导出包含v3.2字段" | ✅ 前端实现了 CSV 导出 | 19 列，覆盖 v3.2 字段 |
| "人工事件快速录入" | ✅ 完整 | 无 |
| "行情收件箱原文识别" | ✅ 可用（仅手动粘贴） | 无自动抓取 |
| "历史BOM扫描" | ✅ 可用 | 无 |
| "一键启动演示服务" | ⚠️ 脚本存在 | 依赖外部路径和 Python 环境 |

---

## 二、QA 测试验收视角 —— 发现的问题

### 2.1 🔴 阻塞级：前端展示两套矛盾的风险等级

**文件**：`frontend/src/components/RiskDetailTable.vue`

同一个物料在表格中展示 **两列不同的风险等级**：

- 第 4 列"风险"：显示 `risk_level`（来自旧 BOMMatcher 的事件匹配结果）
- 第 6 列"v3.2风险"：显示 `v32_risk_level`（来自双轨引擎）

用户会看到同一颗物料同时有"🟢 安全"（旧引擎）和"🟠 较高"（v3.2 引擎），这是严重的 UX 问题，让人对系统可信度产生怀疑。

**最严重的情况**：旧引擎返回 `green` 但 v3.2 引擎返回 `red`，用户不知道该信哪个。

**验证方式**：上传 demo BOM，观察 STM32F103C8T6（MCU 品类）的两列风险是否一致。

**整改要求**：合并为单列综合风险等级，内部用权重融合，对外只展示一个结论。

---

### 2.2 🔴 阻塞级：后端 RiskLevel 枚举无法处理 "orange"

**文件**：`backend/app/models/bom.py:13-17`

```python
class RiskLevel(str, enum.Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    GRAY = "gray"
```

但 `frontend/src/components/RiskDetailTable.vue:153-158` 已经包含了 `orange`：

```javascript
const levels = [
  { value: 'red', label: '高风险' },
  { value: 'orange', label: '较高' },    // ← 前端有 orange
  { value: 'yellow', label: '关注' },
  ...
]
```

前端预判了 `orange` 等级，但后端枚举不支持。当双轨引擎 `_level()` 返回 `"orange"` 时：
- `_combine_risk_level()` 无法识别 → 风险被降级处理
- `analyze_bom` 中 `level = RiskLevel(combined)` 如果 combined 是 `"orange"` 会抛出 `ValueError`
- 该物料的风险评估结果会丢失

**验证方式**：上传含高容MLCC的BOM，触发双轨引擎返回 orange，检查 JSON 响应是否正常。

**整改要求**：枚举中加入 `ORANGE = "orange"`，`_combine_risk_level` 处理 5 个等级。

---

### 2.3 🟡 功能级：物料风险等级两次分析之间无变更追踪

**文件**：`backend/app/models/bom.py` 定义了 `last_risk_level` 和 `risk_changed_at` 字段，但 `analyze_bom` 中从未写入。

实际效果：
1. 用户上传 BOM → 分析 → 全部 green
2. 一周后行情变化，新增了 MCU 缺货事件
3. 用户重新分析 → 3 颗物料变 red
4. 但 `last_risk_level` 仍为空，`new_risks` 接口失效
5. 用户无法知道"哪些物料的等级变化了"

**验证方式**：分析同一个 BOM 两次，中间插入人工事件，查询 `GET /api/bom/projects/{id}/new-risks`。

**整改要求**：分析前保存 `item.risk_level.value` 到 `last_risk_level`，记录变更时间到 `risk_changed_at`。

---

### 2.4 🟡 功能级：替代料推荐始终为空

**文件**：`backend/app/models/preferred.py:121`

```python
"recommended_alternatives": [],   # 硬编码空数组
```

但在 `PreferredLibraryReviewService._review_item()` 中（review_service.py:58），`recommended_alternatives_json` 确实被写入了真实数据。问题是 `BomSelectionReview.to_dict()` 方法覆盖了它，返回空数组。

**验证方式**：对已有优选库数据的项目执行选型评审，检查返回的 `recommended_alternatives` 是否为空。

**整改要求**：`to_dict()` 中从 `recommended_alternatives_json` 反序列化。

---

### 2.5 🟡 功能级：API 缺少 CSV 导出端点

文档宣称支持 CSV 导出，但实际只在**前端**用 JavaScript 生成 CSV（BomAnalyze.vue:437-470）。后端没有 CSV 导出 API，意味着：
- 无法通过 API 直接下载
- 大批量 BOM（如 500+ 行）前端生成 CSV 可能卡顿
- 无法做自动化报表

**整改要求**：后端增加 `GET /api/risk/report/{id}/csv` 端点。

---

### 2.6 🟢 测试覆盖：核心 API 端点无测试

`backend/app/api/risk_analysis.py` 的 3 个主要端点：
- `POST /analyze/{id}` — **无测试**
- `POST /analyze-all` — **无测试**
- `GET /report/{id}` — **无测试**

当前唯一的集成测试 `test_risk_analysis_v32_integration.py` 只测了 `build_v32_context` 函数，没有测 HTTP 端点。

**整改要求**：用 FastAPI TestClient + mock SupplyDataService 覆盖这 3 个端点。

---

## 三、开发工程师视角 —— 架构与逻辑问题

### 3.1 🚨 架构级：核心引擎产出未接入主决策链

这是整个系统最根本的问题。当前 `analyze_bom` 的风险决策流程：

```
                        ┌─ BOMMatcher.match_item()      → market_level    ┐
BOM物料 ──→ ──→ ──→ ──→├─ evaluate_supply_risk()        → supply_level    ──→ max() → 最终风险
                        ├─ MarketIntelEngine.match_item() → intel_level     ┘
                        └─ build_v32_context()            → v32_level (仅供展示，不参与决策)
```

`build_v32_context` 投入了大量工程资源（品类分类器 + 双轨引擎 + 依据链），产出 `v32_risk_level`、`v32_primary_track`、`v32_evidence_chain` 等结构化结果，但这些只作为 JSON 的装饰性字段附加到响应中。最终风险等级由前面三路旧逻辑用 `max()` 拼凑。

**这是最可惜的一笔工程投入**。双轨引擎的材料传导/供需信号分离设计、IC 类材料传导弱约束、缓冲因子等精心设计的逻辑——全部没有进入决策主链路。

**整改方案**：
```python
# 目标：以 v32 双轨引擎为基础，其余为加权修正
v32_weight = 0.5
event_weight = 0.25
intel_weight = 0.15
supply_weight = 0.10

v32_rank = _risk_rank(v32_context["v32_risk_level"])
market_rank = _risk_rank(market_level.value)
supply_rank = _risk_rank(supply.production_risk_level)
intel_rank = _risk_rank(intel_result.risk_level)

weighted = v32_rank * v32_weight + market_rank * event_weight + \
           intel_rank * intel_weight + supply_rank * supply_weight
```

---

### 3.2 🚨 架构级：品类分类体系碎片化（5 套互不兼容）

| 分类系统 | 品类数量 | 命名风格 | 消费方 |
|---|---|---|---|
| `category_tree.py` | ~30 节点 | `MCU/微控制器`（中英混合） | BOMMatcher 事件波及 |
| `category_classifier.py` | 9 种规则 | `mcu`（小写下划线） | 双轨引擎 |
| `market_intel.py` CATEGORY_MARKET_RISK | 15 个品类 | `mcu` | MarketIntelEngine |
| `supply_risk.py` _LONG_LEAD_CATEGORY_WEEKS | 12 种品类 | `MCU`（大写） | supply_risk 评估 |
| `market_notice_parser.py` _extract_category() | 内联 70 行 | `mcu` | 行情收件箱 |

**最严重的后果**：`category_classifier` 识别出 `film_capacitor`（薄膜电容），但 `CATEGORY_MARKET_RISK` 中没有这个 key → 行情情报引擎返回空 → 物料静默失去行情情报覆盖。

**传播链条**：分类器覆盖率不足 → 更多物料归为 `unknown` → 双轨引擎使用默认权重 → 风险评估失真 → 用户对系统失去信任。

**整改方案**：
1. 以 `category_classifier.py` 为唯一品类分类入口，扩展覆盖到 20+ 品类
2. CATEGORY_MARKET_RISK 补齐所有分类器能输出的品类
3. _LONG_LEAD_CATEGORY_WEEKS 的键名对齐 v3.2 品类名
4. category_tree 增加 v3.2 品类节点
5. market_notice_parser 复用 category_classifier

---

### 3.3 🔴 逻辑级：事件匹配引擎的三个设计缺陷

**文件**：`backend/app/services/bom_matcher.py`

**缺陷 1 — 短路返回**（L62-69）：品牌+品类精确匹配命中后立即 `return RED`，后续所有信号被丢弃。例如物料同时命中"涨价"和"EOL停产"，用户只看到 RED 但不知道存在 EOL。

**缺陷 2 — 品牌空值惩罚**（L112-115）：`_match_brand` 在品牌为空时直接返回 False。实际 BOM 中品牌为空是常态（约占 30-50%），这些物料永远只能走到 YELLOW。

**缺陷 3 — 事后补丁模式**：`match_item` 不用 v3.2 分类器，靠 `_merge_v32_events` 事后补救。对每个 item 的每个 active event 都调用一次 `classify_component_category`，复杂度 O(n×m)，其中 n=物料数，m=活跃事件数。

**整改方案**：
```python
def match_item(self, item):
    # 1. 先用 v3.2 分类器确定物料品类
    v32_cat = classify_component_category(desc, manufacturer).category
    
    # 2. 收集所有匹配事件（不短路）
    matched = []
    for event in self.events:
        if self._category_overlap(v32_cat, event.category):
            matched.append(event)
    
    # 3. 综合评分
    return self._score_from_events(matched, v32_cat)
```

---

### 3.4 🔴 逻辑级：BOMMatcher 和 MarketIntelEngine 是同一件事的两套实现

`BOMMatcher.match_item()` 和 `MarketIntelEngine.match_item()` 都在做"事件/情报匹配物料"这件事，但用了完全不同的数据和算法：

| | BOMMatcher | MarketIntelEngine |
|---|---|---|
| 数据源 | MarketEvent 表（动态） | MARKET_INTEL_ENTRIES（静态） |
| 匹配方式 | 品牌+品类精确/波及 | 品类映射+品牌优先级 |
| 风险等级 | RED/YELLOW/GREEN | red/yellow/green/gray |
| 使用位置 | analyze_bom（每次都调用） | analyze_bom（每次都调用） |

两者在 `analyze_bom` 中被**先后调用**，结果用 `max()` 粗暴合并。实际上 MarketIntelEngine 是 BOMMatcher 的一个特殊数据源的适配器——它应该作为 BOMMatcher 的一个"知识库源"存在，而不是并行的独立引擎。

---

### 3.5 🟡 数据级：多源聚合"取最优"策略对风险评估有害

**文件**：`backend/app/services/supply_data.py:105-106`

```python
merged.total_stock = max(...)       # 所有命中源中取库存最大
merged.lead_time_days = min(...)    # 所有命中源中取交期最短
merged.unit_price = min(...)        # 所有命中源中取单价最低
```

从采购视角这是对的（采购关心最好的可得性），但从风险评估视角这是错的：

| 场景 | DigiKey | LCSC | 聚合结果 | 风险评估应关注 |
|---|---|---|---|---|
| 库存 | 0 | 5000 | 5000（充足） | 0（DigiKey缺货反映原厂配额） |
| 交期 | 84天 | 7天 | 7天（良好） | 84天（反映产能紧张） |
| 价格 | ¥12 | ¥8 | ¥8（合理） | ¥12（反映涨价趋势） |

**整改方案**：聚合结果同时保留 best_case 和 worst_case，风险评估使用 worst_case。

---

### 3.6 🟡 数据级：行情知识库无时效性机制

**文件**：`backend/app/knowledge/market_intel.py`

`MARKET_INTEL_ENTRIES` 是一个 Python 列表，硬编码了 26 条行情情报，全部基于某个时间点的市场状况。没有：

- `effective_date` / `expiry_date` — 情报有效期
- 时间衰减函数 — 过期情报自动降权
- 更新机制 — 唯一更新方式是改代码 + Git commit

`event_collector.py:302-303` 的去重逻辑还会让旧事件越来越强：

```python
if not existing.cross_validated:
    existing.cross_validated = 1
else:
    existing.cross_validated += 1   # 无限累加，没有上限
```

---

### 3.7 🟡 工程级：analyze_bom 和 analyze_all_projects 有约 150 行重复代码

两个函数的区别仅在于：
- `analyze_bom`：单个项目 → 详细输出（含 v32 上下文 + 逐项 JSON payload）
- `analyze_all_projects`：所有项目 → 汇总输出（不含 v32 上下文）

核心循环逻辑（事件匹配 → 实时数据查询 → 风险评估 → 等级合并 → 写库）完全相同，约 150 行代码逐字重复。这是典型的"先复制再修改"的开发模式，后续每次改逻辑都要改两处。

---

## 四、亮点（做得好的地方）

1. **MLCC 分类器**（mlcc_classifier.py）：设计精巧，用正则+关键词+术语黑名单，准确区分高容MLCC/普通MLCC/非MLCC电容（铝电解/钽电容/薄膜电容），5 项测试覆盖了关键边界

2. **情报可信度评分**（intelligence_scoring.py）：三维度加权（来源35%+字段35%+交叉验证20%）+ 单一公众号传闻特殊处理，逻辑清晰，业务规则正确

3. **双轨引擎的 IC 类传导弱约束**（dual_track_risk_engine.py:131-141）：MCU/电源IC 仅有硅片涨价时总分限制 ≤34 且不以材料轨为主导——这是一条正确的领域知识编码

4. **LCSC 数据源实现**（sources/lcsc.py）：事件循环感知的 client 管理、速率限制、完善的错误处理、详细的状态返回——代码质量最高的模块

5. **前端 RiskDetailTable**：交互设计合理，v3.2 风险用 popover 展示依据链、单行供应数据刷新、关联事件浮层——信息密度和可用性平衡得好

6. **E2E 测试**（v32-demo-loop.spec.js）：用真实 BOM 文件 + Playwright 自动完成上传→人工事件→重分析→页面验证的完整闭环，是有效的冒烟测试

7. **优选库选型评审**（review_service.py）：品牌标准化 + MPN 标准化 + 历史索引 + 交期联动禁限 + 替代料推荐——一条完整的治理链路

8. **81 次 commit + 版本化分支**：开发过程有规范的分支管理，master/v36/v37/v38 清晰可追溯

---

## 五、整改优先级与工作量估算

| 优先级 | 编号 | 问题 | 工作量 | 依赖 |
|---|---|---|---|---|
| **P0 立即** | 2.2 | 后端 RiskLevel 枚举加入 orange | 0.5h | 无 |
| **P0 立即** | 2.1 | 合并前端两列风险等级为单列 | 1h | P0-2.2 |
| **P0 本迭代** | 3.1 | 双轨引擎产出接入最终决策链 | 3h | P0-2.2 |
| **P0 本迭代** | 3.2 | 统一品类分类体系（5→1） | 4h | 无 |
| **P1 本迭代** | 2.3 | 风险变更追踪（写入 last_risk_level） | 1h | 无 |
| **P1 本迭代** | 3.3 | 事件匹配引擎三项修复 | 3h | P0-3.2 |
| **P1 本迭代** | 3.4 | 合并 BOMMatcher + MarketIntelEngine | 3h | P0-3.2 |
| **P1 本迭代** | 3.7 | 消除 analyze_bom/analyze_all 重复 | 2h | P0-3.1 |
| **P1 本迭代** | 2.5 | 后端增加 CSV 导出端点 | 1h | 无 |
| **P1 本迭代** | 2.4 | 修复替代料推荐空数组 | 0.5h | 无 |
| **P2 下迭代** | 3.5 | 多源聚合增加 worst_case 视图 | 2h | 无 |
| **P2 下迭代** | 3.6 | 行情知识库时效性衰减 | 2h | 无 |
| **P2 下迭代** | 2.6 | 补充 API 端点测试 | 3h | P0-3.1 |

**总计**：P0（含立即+本迭代）约 18h，P1（本迭代）约 10.5h，P2（下迭代）约 7h。

---

## 六、总结

从开发工程师角度看，这是一个**领域知识扎实、架构思路清晰、但集成交付被时间压力压缩到约 60%** 的项目。最核心的问题是：投入最大精力设计实现的双轨风险引擎没有接入最终决策链路，变成了一个"看起来很厉害但实际不干活"的装饰模块。品类分类体系的碎片化是第二个根本问题，它导致各模块之间"语言不通"，靠事后补丁桥接。

从 QA 测试角度看，系统**可演示但不可上线**。最阻塞的问题是前端展示两套矛盾的风险等级（损害信任）、后端无法正确处理 `orange` 等级（导致潜在崩溃）、以及缺乏风险变更追踪（无法论证系统价值）。

**一句话总结**：骨架搭得很好，肉也切好了，但还没炒成一盘菜。P0 整改完成后可以达到"可上线"水平，P1 完成后可以达到"可交付"水平。

---

> **评审人**：Claude (QA 测试验收 + 开发工程师双视角)
> **目标项目**：`D:\1项目清单\交期风险排查\BOM-Risk-Analyzer-patch`
> **评审耗时**：完整通读全部源代码（后端 50+ 文件、前端 30+ 文件、测试 19 文件、文档 10+ 文件）
