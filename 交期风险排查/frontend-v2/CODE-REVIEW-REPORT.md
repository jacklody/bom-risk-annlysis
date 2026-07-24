# BOM交期风险系统 — 代码评审报告

> 评审日期：2026-07-07
> 评审范围：后端全部服务 + 前端全部页面 + 数据流全链路
> 对照基准：PRD v1.0 → v3.2 全部需求文档

---

## 一、总评

现有系统实现了 PRD 约 **40%** 的核心设计。后端架构方向正确（双轨引擎、品类分类、依据链），但大部分模块停留在**简化版/MVP阶段**，距离PRD设计的完整能力差距较大。前端我新建的 v2 版本比原版有很大提升，但仍有大量硬编码模板数据。

**最大问题**：后端和前端之间的数据断层——后端返回的是扁平统计数据，前端需要的却是结构化的链路数据。结果就是前端大量使用硬编码默认值，看起来在跑但实际数据没流通。

---

## 二、严重问题（P0 — 阻碍核心功能）

### 2.1 品类分类器覆盖率不足

**文件**：`category_classifier.py`

**问题**：只覆盖了 9 个品类（PCB/继电器/MCU/电源芯片/薄膜电容/安规电容/铝电解/连接器/电感变压器+MLCC），PRD v3.2 要求覆盖 20-30 个品类。

**缺失的品类**：
- 电阻类（贴片电阻/精密电阻/合金采样电阻）— 完全未识别
- 功率器件（MOSFET/IGBT/SiC）— 完全未识别
- 分立器件（二极管/TVS/ESD/三极管）— 完全未识别
- 存储芯片（DRAM/NAND/NOR Flash）— 完全未识别
- 模拟芯片/运放/比较器 — 完全未识别
- FPGA/CPLD — 完全未识别
- 晶振/振荡器 — 完全未识别
- 线束/端子 — 完全未识别
- 开关 — 完全未识别
- 功率模块 — 完全未识别

**影响**：一半以上的BOM物料会落入 `unknown` 品类，双轨引擎退化为默认权重（material 0.4, demand_supply 0.6），风险评分失去品类差异化。

### 2.2 上游材料跟踪是"空壳"

**文件**：`risk_context_builder.py`（`_material_signals_for_category` 函数）

**问题链路**：
1. `settings.material_tracking_enabled = True`（已开启）
2. `_material_tracker` 在 main.py lifespan 中被设为 `None`（占位）
3. Metals API 的 `METALS_API_KEY` 为空（.env 未配置）
4. 回到 fallback 路径 → 仅用 market_facts 的布尔标志（`price_up_confirmed`）
5. 也就是说：**铜涨12%这个数字永远不会进入评分系统**

```python
# 实际执行的代码路径（退化到布尔判断）
if category == "pcb":
    return {"copper_foil_price_up": bool(market_facts.get("price_up_confirmed"))}
# 问题：bool(True) = 1 → 权重32分 → 不区分涨1%和涨30%
```

**PRD 期望**：铜价↑12% × 暴露系数 × 转嫁率60%-80% × 滞后1-3月 → 动态评分

**目前实际**：铜相关的任意事件 → 固定+32分

### 2.3 双轨引擎缺少传导可靠性校准

**文件**：`dual_track_risk_engine.py` + `propagation_rules.py`

**PRD v3.1/v3.2 设计的完整评分模型**：
```
风险分 = 本体信号×w1 + 材料传导×w2×(转嫁率)×(可靠性系数)×(证据强度) + 供需×w3 + 缓冲 - 贸易政策
```

**目前实际实现**：
```python
material_weighted = round(material_raw * model["material"])  # 只乘了一个固定权重
demand_weighted = round(demand_raw * model["demand_supply"])
total = material_weighted + demand_weighted - buffer
```

**缺失的关键机制**：
- ❌ 无转嫁率（pass-through rate）：PRD 设计的 PCB 60%-80% vs MLCC 10%-30%
- ❌ 无滞后时间：PRD 设计的 PCB 1-3月 vs 铝电解 3-6月
- ❌ 无传导可靠性系数：已验证传导1.0 vs 弱关联0.2
- ❌ 无证据强度分级：涨价函1.0 vs 公众号0.2
- ❌ 无信息不足状态区分：全零信号时返回 gray 但没区分"真安全"vs"没数据"
- ❌ 无贸易政策维度（关税/出口管制/制裁）
- ❌ 无行业订单冲击维度（汽车/AI/光伏挤占）

### 2.4 前端 RiskDashboard 硬编码了假数据

**文件**：`frontend-v2/src/views/RiskDashboard.vue`

```javascript
// 这段数据是写死的，不从后端读取
const materialChains = ref([
  { key: 'pcb', material: '铜(↑12%)', materialAlert: true, ... },
  { key: 'relay', material: '银(↑18%)', materialAlert: true, ... },
  ...
])
const demandSignals = ref([
  { key: 'mlcc', category: '高容MLCC', title: '涨价缺货...', ... },
  ...
])
```

**问题**：不管实际有没有数据，仪表盘永远显示这7条固定信息。"铜↑12%"不反映真实铜价，"银↑18%"也不反映真实银价。后端 `/api/dashboard/summary` 返回的 `category_risks` 只有扁平统计，根本没有结构化的双轨链数据。

---

## 三、中等问题（P1 — 影响数据质量和用户体验）

### 3.1 依据链缺少上游材料拆解

**文件**：`evidence_chain_builder.py`

**当前输出**（JSON链）：
```json
[
  {"type": "category", "title": "品类识别", "upstream_materials": ["copper_foil", "fiberglass_cloth"]},
  {"type": "market_event", "title": "命中行情事件"},
  {"type": "dual_track", "title": "双轨风险评分"},
  {"type": "supply_snapshot", "title": "实时供应快照"},
  {"type": "buffer", "title": "缓冲因素"}
]
```

**PRD 期望的输出**（PRD v3.0 第14节）：
```json
[
  {"type": "raw_material", "name": "铜", "price_change": "+12%", "source": "LME"},
  {"type": "mid_component", "name": "铜箔", "from": "铜", "cost_share": "25%"},
  {"type": "device_category", "name": "PCB", "pass_through": "60%-80%", "lag": "1-3月"},
  {"type": "bom_item", "mpn": "PCB-4L-FR4", "risk": "orange"},
  {"type": "action", "suggestion": "提前锁价"}
]
```

**关键差异**：目前依据链是**扁平列表**，缺少**层层递进的因果关系**。用户看不出"铜怎么一步步变成PCB风险"。

### 3.2 行情收件箱信号抽取是纯正则，不是LLM

**文件**：`market_notice_parser.py`

PRD 从 v1.1 开始就提到"LLM结构化抽取"，但从代码来看，`parse_market_notice` 是纯规则引擎（正则+关键词匹配）。对于"TDK高容MLCC缺货涨价"这种标准文本效果OK，但对复杂文本（多品牌/多品类/区间涨幅/条件生效）会漏抽。

### 3.3 预测验证闭环几乎未实现

PRD v3.1 第13节设计了完整的预测验证机制：
- 每次预警记录预测对象、风险类型、时间窗口
- 到期自动比对实际价格/交期/库存
- 按品类/传导链统计命中率
- 反向修正权重

**当前状态**：`prediction_validation_records` 表有 14 条记录，但只是手工标记的复盘记录，没有自动到期验证、没有命中率统计、没有权重反馈。

### 3.4 材料链路页全部是模板数据

**文件**：`MaterialChain.vue`

7个品类、3种材料的详细链路数据全部硬编码。虽然后端API连上时部分字段（itemCount/projectCount）会被覆盖，但核心的链路关系、材料价格、AI判断、处置建议都是前端写死的，不是后端生成的。

### 3.5 重复API和不一致的命名

**文件**：`market_intel.py` vs `market_trends.py` vs `events.py`

三个文件都提供了事件相关的API，但各自的数据格式和字段名不完全一致：
- `events.py` → `/api/events/` — 主事件CRUD
- `market_trends.py` → `/api/market-trends/` — 趋势聚合
- `market_intel.py` → `/api/market-intel/` — 情报匹配

有些功能重叠（例如事件列表查询），前端需要同时调三个API才能拼出完整数据。

---

## 四、轻微问题（P2 — 影响扩展性和维护性）

### 4.1 品类权重是硬编码字典

```python
CATEGORY_MODEL_WEIGHTS = {
    "high_cap_mlcc": {"material": 0.35, "demand_supply": 0.65, "display": "高容MLCC"},
    ...
}
```

PRD v3.1 设计了 `category_risk_models` 数据库表，使权重可通过预测验证动态调整。目前硬编码意味着：调整权重需要改代码重新部署。

### 4.2 前端大文件

`IntelligenceCenter.vue` 超过 600 行（模板+逻辑+样式混在一起），`MaterialChain.vue` 超过 500 行。随着功能增长，应该拆分为子组件。

### 4.3 无API版本管理

所有API端点无版本前缀（如 `/api/v1/`），未来API变更时无法同时支持新旧版本。

### 4.4 SQLite 单文件数据库

29个项目 + 2632条物料 + 80事件后数据库已 2.4MB，仍在SQLite的舒适区。但如果数据量增长10倍（比如历史项目积累到200+），SQLite的并发写入会成为瓶颈。

---

## 五、对比PRD各版本的实现度

| PRD模块 | 设计文档 | 实现状态 | 完成度 |
|---------|---------|---------|:---:|
| BOM上传解析 | v1.0 M1 | ✅ 已完成 | 90% |
| 多源供应查询(LCSC/Mouser/DigiKey) | v1.0 M2 | ✅ 已完成 | 85% |
| 型号标准化 | v1.0 F1.2 | ✅ 已完成 | 80% |
| 涨价事件管理 | v1.1 M4 | ⚠️ 基本可用 | 60% |
| 品类分类(20-30个) | v3.0 | ❌ 仅9个 | 30% |
| 上游组份拆解(规格书解析) | v3.0 §4-5 | ❌ 未实现 | 5% |
| 双轨风险引擎 | v3.2 §8 | ⚠️ 简化版 | 50% |
| 传导可靠性校准 | v3.1 §5 | ❌ 未实现 | 10% |
| 转嫁率/滞后时间 | v3.1 §6 | ❌ 未实现 | 0% |
| 供需平衡模型 | v3.1 §7 | ⚠️ 简化版 | 40% |
| 贸易政策风险 | v3.1 §11 | ❌ 未实现 | 0% |
| 预测验证闭环 | v3.1 §13 | ❌ 仅数据表 | 15% |
| 公众号情报池 | v3.2 §6 | ❌ 仅手动转发 | 20% |
| 行情事实优先(MLCC等) | v3.2 §5 | ✅ 已实现 | 80% |
| 前端依据链展示 | v3.0 §10 | ⚠️ 扁平列表 | 40% |
| 上游材料网络视图 | v3.0 §10.2 | ⚠️ 模板数据 | 30% |

---

## 六、优先修复建议（按性价比排序）

### 🔴 第一优先级（本周，高影响低成本）

| # | 问题 | 修复方式 | 影响 |
|---|------|---------|------|
| 1 | 品类分类器只覆盖9个 | 在 `_CATEGORY_RULES` 中补充 MOSFET/二极管/电阻/存储/晶振等15+品类关键词 | 让50%+的unknown物料有正确的品类和双轨权重 |
| 2 | Metals API未配置 | 注册 metals-api.com → 填 `METALS_API_KEY` → 铜银铝价格自动流入 `_material_signals_from_tracker` | 材料传导轨从"布尔标志"变为"真实涨跌幅×权重" |
| 3 | 前端仪表盘硬编码数据 | 后端新增 `/api/dashboard/dual-track` 端点返回结构化的双轨链路数据 | 仪表盘显示实时数据而非假数据 |

### 🟡 第二优先级（两周，中影响中成本）

| # | 问题 | 修复方式 |
|---|------|---------|
| 4 | 依据链无层级因果 | 改造 `evidence_chain_builder`，按"原材料→组份→器件→BOM→建议"层级输出 |
| 5 | 无传导可靠性/转嫁率 | 创建 `propagation_rules` 数据库表，从品类模板读取参数 |
| 6 | 材料链路页数据断层 | 后端新增 `/api/risk-analysis/material-chain` 返回结构化链路JSON |

### 🟢 第三优先级（一月，长期架构改进）

| # | 问题 | 修复方式 |
|---|------|---------|
| 7 | 预测验证闭环 | 实现自动到期验证，统计品类/传导链命中率 |
| 8 | LLM信号抽取 | 接入LLM替代纯正则，处理复杂文本 |
| 9 | API去重和版本化 | 合并 market_trends/market_intel 重叠端点 |
| 10 | 规格书解析 | 对高风险高用量物料自动下载规格书提取材料线索 |

---

## 七、架构评分

| 维度 | 评分 | 说明 |
|------|:---:|------|
| 架构方向 | ⭐⭐⭐⭐ | 双轨设计、品类分层、依据链思路正确 |
| 实现完整度 | ⭐⭐ | PRD设计的60%功能未实现或为简化版 |
| 数据真实性 | ⭐⭐ | 3个API在线但材料/产能/政策数据缺失 |
| 前后端一致性 | ⭐⭐ | 前端展示的数据结构后端不提供 |
| 代码质量 | ⭐⭐⭐ | 结构清晰、命名规范、有测试；部分硬编码 |
| 可扩展性 | ⭐⭐⭐ | 数据源可插拔、品类模板可扩展；权重硬编码 |
| 文档 | ⭐⭐⭐⭐ | PRD文档详尽，代码注释充分 |

**总评**：方向正确，骨架搭好了，但**血肉不足**。现在是"能跑起来的Demo"而非"可依赖的风险雷达"。最大的差距在：品类覆盖、材料数据真实性、传导模型精度、前后端数据打通。
