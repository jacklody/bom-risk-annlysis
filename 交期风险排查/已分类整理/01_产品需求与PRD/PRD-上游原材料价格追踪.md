# PRD：上游原材料价格追踪

**创建日期**：2026-07-01
**版本**：v1.0
**状态**：待开发

---

## 1. 需求背景

### 1.1 触发来源

当前 BOM 交期风险分析系统的双轨引擎（`dual_track_risk_engine.py`）已为原材料传导预留了完整的评估管道：每个品类定义了 `upstream_materials`，配置了 `material` 轨权重（0.25~0.75），并在 `MATERIAL_SIGNAL_WEIGHTS` 中为铜价上涨、银价上涨、铝箔上涨等关键材料定义了信号权重。但材料信号的来源存在根本性缺陷：

- 当前 `_material_signals_for_category()` 从已发布的事件文本描述中提取材料信号
- 这意味着系统只能响应"已经被写成文章"的波动
- 铜价涨 8% 但在媒体发文之前，系统对任何 BOM 行都毫无反应
- 钽粉月涨 12% 直接影响钽电容 45% 的成本结构，但等到行业媒体出文章往往滞后 2-4 周

### 1.2 核心痛点

| 痛点 | 当前状态 | 目标状态 |
|------|---------|---------|
| 信号滞后 | 依赖媒体发文，滞后 1-4 周 | 日级/周级直接从价格平台取数 |
| 覆盖不全 | 仅覆盖有文章的材料（铜/银/铝/硅片） | 覆盖 9 大品类 × 32 种关键原材料 |
| 无历史基线 | 不知道"正常价格"是多少 | 30 日/90 日历史基线对比 |
| 无趋势预警 | 只能响应已发生的波动事件 | 5%/10%/20% 三档阈值自动检测 |
| 材料传导弱 | 仅用布尔信号（涨/不涨），丢失幅度信息 | 百分比价格变动 × 传导系数（成本占比） |

### 1.3 不解决的后果

- PCB 品类占 material 轨权重 75%，但铜箔涨价 20% 时系统无感知，风险评分严重失真
- 钽电容品类极度依赖钽粉（成本占比 45%），钽粉价格剧烈波动时系统无法预警
- MLCC 涉及钛白粉、碳酸钡、稀土、镍、铜五层材料链，其中任一环节涨价都应触发预警，但当前无法做到

---

## 2. 目标

### 2.1 核心目标

建立**从原材料实时价格到元器件风险评分的全自动传导管道**，使双轨引擎的 material 轨从"布尔信号推断"升级为"百分比价格变动 × 传导系数"的精确计算。

### 2.2 量化目标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 材料覆盖品类数 | 4 类（铜/银/铝/硅片，且仅布尔） | 9 品类 × 32 种材料 |
| 价格更新频率 | 依赖媒体（1-4 周） | 有色金属日级，化工周级 |
| 材料预警响应延迟 | 2-4 周 | 24 小时内（日级材料） |
| 材料传导精度 | 布尔（0 或 1） | 连续值（百分比 × 传导系数） |

### 2.3 非目标

- 不替代现有媒体事件采集（材料价格追踪是补充管道，非替代）
- 不实现期货/期权定价模型
- 不对材料价格做预测（仅做当前价格 vs 历史基线的波动检测）
- 不修改前端 UI（Phase 1-3 为纯后端功能，API 端点预留但 Dashboard 展示留到 Phase 4）

---

## 3. 系统架构

### 3.1 整体架构

```
                    ┌───────────────────────────────────────────┐
                    │          MaterialPriceService              │  编排层
                    │      (统一调度 + 缓存 + 降级 + 限流)         │
                    └──────────────┬────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌───────────────┐       ┌───────────────────┐      ┌───────────────────┐
│ MetalsGroup   │       │ RareEarthGroup    │      │ ChemicalGroup     │
│ 有色金属组    │       │ 稀土&小金属组      │      │ 化工&非金属组      │
├───────────────┤       ├───────────────────┤      ├───────────────────┤
│ metals-api    │       │ 稀土行业协会       │      │ 生意社 100ppi      │
│ LME爬虫(备)   │       │ 亚洲金属网         │      │ 卓创资讯 sci99     │
│ 长江有色(备)  │       │ 金投网(备)         │      │ 百川盈孚(备)       │
└───────┬───────┘       └─────────┬─────────┘      └─────────┬─────────┘
        │                        │                          │
        ▼                        ▼                          ▼
┌───────────────────────────────────────────────────────────────┐
│                      MaterialTracker                           │
│         (30日/90日历史基线 + 5%/10%/20% 三档阈值判定)          │
└──────────────┬────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│                  material_mapping.py                          │
│      品类 → 材料列表 → 数据源组 → 传导系数(成本占比)           │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │  risk_context_builder.py (改造)   │
    │  material_signals ← Tracker 取数  │
    └──────────────┬───────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────┐
    │  dual_track_risk_engine.py       │
    │  material_track ← 真实价格信号    │
    └──────────────┬───────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────┐
    │  MarketEvent                     │
    │  event_type = "material_price"   │
    └──────────────────────────────────┘
```

### 3.2 与原系统的关系

新模块是**补充管道**，不修改现有采集/分析流程：

- `category_classifier.py` — 不修改（`upstream_materials` 已定义，新模块的 `material_mapping.py` 是独立映射层）
- `propagation_rules.py` — 不修改（`MATERIAL_SIGNAL_WEIGHTS` 已定义）
- `dual_track_risk_engine.py` — 不修改（material track 评估逻辑已就绪，只改变输入信号的具体数值）
- **唯一需要改造的入口**：`risk_context_builder.py` 的 `_material_signals_for_category()` — 从"从事件文本取布尔信号"改为"从 MaterialTracker 取百分比变动 + 传导系数"

---

## 4. 功能规格

### 4.1 功能总览

| # | 模块 | 功能描述 |
|---|------|---------|
| F1 | MaterialMapping | 定义品类 → 材料 → 数据源 → 传导系数的完整映射字典。每个材料条目包含：英文 key、中文名、所属数据域、成本占比（传导系数）、主数据源、备数据源、更新频率。覆盖 9 品类 × 32 材料。 |
| F2 | MaterialPrice 模型 | SQLAlchemy 持久化模型，存储单条材料价格记录。字段包括：material_key、price_value、price_unit、source_name、fetch_timestamp。支持价格历史查询和基线计算。 |
| F3 | MaterialPriceSource 数据源组 | 三个独立的数据源组（MetalsGroup/RareEarthGroup/ChemicalGroup），每组含主源 + 备源。所有源实现统一的 `MaterialPriceSource` 抽象基类，对外暴露 `fetch_prices(material_keys) -> dict` 接口。主源失败自动降级到备源。 |
| F4 | MaterialPriceService 编排层 | 统一调度三个数据域，管理缓存（TTL 可配置）、限流（60 次/月 free API 配额保护）、降级（主源→备源→缓存 stale 数据）。对外暴露 `get_prices(material_keys) -> dict`。 |
| F5 | MaterialTracker 追踪器 | 查询 30 日/90 日历史基线，计算每个材料的当前价格与基线的百分比变化。按 5%/10%/20% 三档阈值判定风险等级，稀土材料使用 1.6× 传导系数放大器。 |
| F6 | RiskContextBuilder 集成 | 改造 `_material_signals_for_category()`：不再从 market_facts 提取布尔信号，改为调用 MaterialTracker 获取价格变动百分比，乘以传导系数后返回连续值信号。 |
| F7 | Event 采集 | 当 MaterialTracker 检测到材料价格波动超过 ORANGE 阈值（≥10%），自动生成 event_type="material_price" 的 MarketEvent 记录，写入 market_events 表。 |
| F8 | Material Alerts API | 新增 `GET /api/material-alerts` 端点，返回当前所有材料的价格状态（正常/预警/告警），包括价格变动百分比、阈值档位、影响品类列表。 |

### F1：MaterialMapping 映射字典

**文件**：`app/knowledge/material_mapping.py`

**数据结构**：

```python
# 单个材料条目
MATERIAL_ENTRY = TypedDict({
    "key": str,           # 材料唯一标识，如 "cu_cathode"
    "name_zh": str,       # 中文名，如 "电解铜"
    "domain": str,        # 数据域: "metals" | "rare_earth" | "chemical"
    "cost_ratio": float,  # 成本占比，即传导系数 (0.0~1.0)
    "primary_source": str, # 主数据源标识
    "backup_source": str,  # 备数据源标识
    "fetch_frequency": str, # "daily" | "weekly" | "monthly"
    "is_rare_earth": bool,  # 是否为稀土材料（触发 1.6× 放大器）
})

# 品类→材料映射
CATEGORY_MATERIAL_MAP: dict[str, list[MATERIAL_ENTRY]]
```

**业务规则**：
- 同一材料可被多个品类引用（如电解铜同时用于继电器、PCB、连接器、电感、MLCC 端头）
- 稀土材料 `is_rare_earth=True` 时，传导计算自动乘以 1.6 放大因子
- 铜箔（PCB 用）在铝锭基础上乘以 1.12 的加工溢价系数

### F2：MaterialPrice 模型

**文件**：`app/models/material_price.py`

**数据库表**：`material_prices`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| material_key | String(64) | 材料标识，如 "cu_cathode" |
| price_value | Float | 价格数值 |
| price_unit | String(32) | 价格单位，如 "元/吨"、"元/克" |
| source_name | String(128) | 数据来源，如 "metals_api" |
| fetch_timestamp | DateTime | 数据采集时间 |
| created_at | DateTime | 记录创建时间 |

**索引**：`(material_key, fetch_timestamp)` 复合索引，用于基线查询和历史价格检索。

### F3：数据源组设计

**文件**：`app/services/sources/materials/`

**抽象基类** (`base.py`)：

```python
class MaterialPriceSource(ABC):
    source_name: str
    
    @abstractmethod
    async def fetch_prices(self, material_keys: list[str]) -> dict[str, float | None]:
        """返回 {material_key: price_value}，单个失败返回 None"""
        ...
    
    async def is_available(self) -> bool:
        """检查数据源是否可用"""
        ...
```

**三个实现组**：

| 组 | 文件 | 主源 | 备源 | 覆盖材料数 | 数据成本 |
|----|------|------|------|-----------|---------|
| MetalsGroup | `metals_api_source.py` | metals-api.com GET /latest | 长江有色 HTML 解析 | 6 (Cu/Al/Ag/Sn/Ni/Zn) | ¥0 |
| RareEarthGroup | `rare_earth_source.py` + `small_metal_source.py` | 稀土行业协会 HTML + 亚洲金属网 HTML | 金投网 HTML | 7 (稀土类 + 钽类 + 钛白粉/碳酸钡) | ¥0 |
| ChemicalGroup | `chemical_source.py` | 生意社 100ppi HTML | 卓创资讯 HTML | 6 (环氧树脂/玻纤布/电解液/PP/PET/PA66) | ¥0 |

**数据源可用性约束**：
- metals-api.com 免费层：60 次/月请求配额，一次 GET 可查多种金属
- 稀土行业协会 (ac-rei.org.cn)：页面结构稳定，日级更新，HTML 解析
- 亚洲金属网 (asianmetal.cn)：小金属品种最全，免费可见基础价格
- 生意社 (100ppi.com)：化工品价格指数日级更新

### F4：MaterialPriceService 编排层

**文件**：`app/services/material_price_service.py`

**核心职责**：
1. 按数据域分组调度：有色金属日级，稀土日-周级，化工周级
2. 缓存管理：以 material_key 为粒度缓存价格，TTL 按域区分（金属 12h，化工 24h）
3. 降级策略：主源超时/失败 → 备源 → stale 缓存（标注 degraded=True）
4. 配额保护：metals-api 60次/月，按日分配预算，超配额暂停当日请求
5. 并发控制：三域并行请求，每域内串行（先主后备）

**对外接口**：

```python
class MaterialPriceService:
    async def get_prices(self, material_keys: list[str]) -> dict[str, dict]:
        """返回 {material_key: {price, unit, source, timestamp, stale}}"""
    
    async def refresh_all(self) -> dict:
        """强制刷新全部材料价格"""
    
    def get_cache_stats(self) -> dict:
        """返回缓存命中率、各源状态"""
```

### F5：MaterialTracker 追踪器

**文件**：`app/services/material_tracker.py`

**核心逻辑**：

1. 查询每个材料过去 30 日和 90 日的价格记录（从 `material_prices` 表）
2. 计算 30 日均价作为短期基线，90 日均价作为长期基线
3. 最新价格 vs 30 日基线计算百分比变化
4. 按三档阈值判定风险等级

**阈值规则**：

| 波动幅度 (vs 30日基线) | 风险等级 | material_track 加分 | 系统行为 |
|----------------------|---------|-------------------|---------|
| 涨幅 5%~10% | YELLOW | +10 | Dashboard 提示 |
| 涨幅 10%~20% | ORANGE | +20 | 生成 MarketEvent，触发品类风险重算 |
| 涨幅 ≥20% | RED | +35 | 生成 MarketEvent，告警推送 |
| 跌幅 ≥10% | GREEN | -15 | 提示采购窗口 |

**稀土放大器**：
```python
RARE_EARTH_AMPLIFIER = 1.6
# 仅应用于传导系数，不改变价格变动百分比本身
adjusted_cost_ratio = base_cost_ratio * RARE_EARTH_AMPLIFIER
```

**传导演算示例（MLCC）**：

```
MLCC 材料风险分 = Σ( material_i_price_change% × cost_ratio_i ) × model_weight

假设当前价格变动：
  TiO₂   +12%  × 0.12 = 1.44
  BaCO₃  +8%   × 0.10 = 0.80
  Dy₂O₃  -3%   × 0.08 × 1.6(稀土放大) = -0.38
  Y₂O₃   +2%   × 0.05 × 1.6(稀土放大) = 0.16
  Ni粉   +15%  × 0.15 = 2.25
  Cu端头 +10%  × 0.08 = 0.80

  合计 = 5.07%

MLCC 风险分 = 5.07 × 0.35(model_weight) = 1.77
→ < 5 阈值，不触发预警
```

### F6：RiskContextBuilder 集成

**改造文件**：`app/services/upstream/risk_context_builder.py`

**改造内容**：重写 `_material_signals_for_category()` 方法

**改造前**：
```python
def _material_signals_for_category(category, market_facts):
    # 从 market_facts 提取布尔信号
    if category == "pcb":
        return {"copper_foil_price_up": bool(market_facts.get("price_up_confirmed"))}
    return {}
```

**改造后**：
```python
def _material_signals_for_category(category, material_tracker):
    # 从 MaterialTracker 获取连续值信号
    materials = get_materials_for_category(category)  # 从 material_mapping 取
    signals = {}
    for m in materials:
        tracking = material_tracker.get_tracking(m.key)
        if tracking and tracking.risk_level != "NORMAL":
            # 传回百分比变动和调整后的传导系数
            signals[f"{m.key}_change_pct"] = tracking.change_pct
            signals[f"{m.key}_risk"] = tracking.risk_level
            signals[f"{m.key}_score"] = tracking.change_pct * tracking.adjusted_cost_ratio
    return signals
```

**关键约束**：
- MaterialTracker 是可选依赖：如果价格数据不可用（所有源均失败），退化回原来的布尔信号逻辑
- 改造不影响 demand_supply 轨的信号采集
- `build_v32_context()` 函数签名不变，内部从 `market_facts` 改为从 tracker 取材料信号

### F7：Event 采集

**改造文件**：
- `app/models/event.py`：EventType 枚举添加 `MATERIAL_PRICE = "material_price"`
- `app/services/event_collector.py`：新增材料价格事件采集逻辑

**触发条件**：MaterialTracker 检测到任意材料价格波动超过 ORANGE 阈值（≥10%）

**MarketEvent 字段赋值规则**：

| 字段 | 取值 | 来源 |
|------|------|------|
| event_type | `material_price` | 固定值 |
| severity | 按阈值：ORANGE→medium, RED→high | MaterialTracker |
| source_name | 数据源名称，如 "metals_api" | MaterialPriceSource |
| category | 受影响的元器件品类列表（逗号分隔） | material_mapping 反向查找 |
| estimated_price_impact_pct | 材料价格变动百分比 | MaterialTracker |
| raw_text | 格式化摘要："{材料名} {涨/跌}{百分比}%，影响品类：{品类列表}" | 自动生成 |
| confidence | 0.85（API 直采数据置信度固定） | 固定值 |

**去重规则**：同一 material_key + 同一天内已有一条 material_price 事件（is_active=1），则仅更新 `cross_validated` 计数，不新增事件。

### F8：Material Alerts API

**文件**：`app/api/material_alerts.py`

**端点**：`GET /api/material-alerts`

**请求参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| risk_level | string | 否 | - | 过滤：yellow/orange/red |
| domain | string | 否 | - | 过滤：metals/rare_earth/chemical |
| category | string | 否 | - | 过滤品类：pcb/relay/mlcc 等 |

**响应格式**：

```json
{
  "alerts": [
    {
      "material_key": "cu_cathode",
      "material_name_zh": "电解铜",
      "domain": "metals",
      "current_price": 78200.0,
      "price_unit": "元/吨",
      "baseline_30d": 72500.0,
      "change_pct": 7.86,
      "risk_level": "YELLOW",
      "affected_categories": ["relay", "pcb", "connector", "inductor_transformer", "mlcc"],
      "last_updated": "2026-07-01T09:00:00Z",
      "source": "metals_api"
    }
  ],
  "summary": {
    "total_materials": 32,
    "alerts_active": 3,
    "red": 0,
    "orange": 1,
    "yellow": 2,
    "green": 1
  }
}
```

---

## 5. 材料映射详表

### 5.1 有色金属域（metals-api.com 免费）

| material_key | 中文名 | 符号 | 涉及品类 | 传导系数 | 主源 | 频率 |
|-------------|--------|------|---------|---------|------|------|
| cu_cathode | 电解铜 | Cu | relay/pcb/connector/inductor/mlcc | 0.05~0.15 | metals-api | 日 |
| cu_foil | 铜箔(PCB) | Cu×1.12 | pcb | 0.15 | metals-api | 日 |
| cu_ball | 铜球(填孔) | Cu | pcb | 0.05 | metals-api | 日 |
| cu_terminal | 铜(端头) | Cu | mlcc | 0.08 | metals-api | 日 |
| al_ingot | 铝锭 A00 | Al | aluminum_heat_sink | 0.40 | metals-api | 日 |
| al_foil_anode | 高纯铝箔(阳极) | Al×1.08 | aluminum_electrolytic_capacitor | 0.20 | metals-api | 日 |
| al_foil_cathode | 铝箔(阴极) | Al | aluminum_electrolytic_capacitor | 0.10 | metals-api | 日 |
| al_metallization | 铝(金属化层) | Al | film_capacitor | 0.03 | metals-api | 日 |
| ag_ingot | 白银 | Ag | relay/tantalum_capacitor | 0.08~0.15 | metals-api | 日 |
| ag_paste | 银浆 | Ag | tantalum_capacitor | 0.08 | metals-api | 日 |
| tin | 锡(焊料) | Sn | connector | 0.05 | metals-api | 日 |
| nickel_powder | 镍粉(电极) | Ni | mlcc | 0.15 | metals-api | 日 |
| ni_plating | 镍(镀层) | Ni | connector | 0.03 | metals-api | 日 |
| zinc | 锌(金属化层) | Zn | film_capacitor | 0.05 | metals-api | 日 |

### 5.2 稀土 & 小金属域

| material_key | 中文名 | 涉及品类 | 传导系数 | 稀土? | 主源 | 频率 |
|-------------|--------|---------|---------|-------|------|------|
| titanium_dioxide | 钛白粉 TiO₂ | mlcc | 0.12 | 否 | 生意社 | 周 |
| barium_carbonate | 碳酸钡 BaCO₃ | mlcc | 0.10 | 否 | 百川盈孚 | 周 |
| dysprosium_oxide | 氧化镝 Dy₂O₃ | mlcc/inductor | 0.06~0.08 | **是** | 稀土行业协会 | 日 |
| yttrium_oxide | 氧化钇 Y₂O₃ | mlcc | 0.05 | **是** | 稀土行业协会 | 日 |
| prnd_oxide | 氧化镨钕 | inductor | 0.08 | **是** | 稀土行业协会 | 日 |
| tantalum_powder | 钽粉 | tantalum_capacitor | 0.45 | 否 | 亚洲金属网 | 周 |
| tantalum_wire | 钽丝 | tantalum_capacitor | 0.10 | 否 | 亚洲金属网 | 周 |
| manganese_dioxide | 二氧化锰 | tantalum_capacitor | 0.05 | 否 | 生意社 | 周 |

### 5.3 化工 & 非金属域

| material_key | 中文名 | 涉及品类 | 传导系数 | 主源 | 频率 |
|-------------|--------|---------|---------|------|------|
| epoxy_resin | 环氧树脂 E-51 | pcb | 0.08 | 生意社 | 周 |
| glass_fiber_cloth | 玻纤布 7628 | pcb | 0.10 | 卓创资讯 | 周 |
| electrolyte | 电解液(铝电容用) | aluminum_electrolytic_capacitor | 0.10 | 卓创资讯 | 周 |
| electrolytic_paper | 电解纸 | aluminum_electrolytic_capacitor | 0.05 | 产业在线 | 月 |
| polypropylene | 聚丙烯 PP-T30S | film_capacitor | 0.25 | 生意社 | 周 |
| polyester_film | 聚酯切片 PET | film_capacitor | 0.20 | 生意社 | 周 |
| engineering_plastics | 工程塑料 PA66 | relay/connector | 0.10 | 生意社 | 周 |
| ferrite_core | 铁氧体磁芯 | inductor | 0.15 | 生意社 | 周 |
| enameled_cu_wire | 漆包铜线 | inductor | 0.20 | metals-api×1.05 | 日 |

---

## 6. 品类到材料传导汇总

| 品类 | model_weight | 材料数 | 传导系数合计 | 数据域覆盖 |
|------|-------------|--------|------------|-----------|
| relay 继电器 | 0.70 | 3 | 0.30 | 有色金属 + 化工 |
| pcb PCB/线路板 | 0.75 | 4 | 0.38 | 有色金属 + 化工 |
| mlcc MLCC | 0.35 | 6 | 0.58 | 有色金属 + 稀土 + 化工 |
| aluminum_electrolytic_capacitor | 0.72 | 4 | 0.45 | 有色金属 + 化工 |
| tantalum_capacitor 钽电容 | 0.35 | 4 | 0.68 | 稀土&小金属 + 有色金属 |
| film_capacitor 薄膜电容 | 0.72 | 4 | 0.53 | 化工 + 有色金属 |
| aluminum_heat_sink 铝散热器 | 0.70 | 1 | 0.40 | 有色金属 |
| connector 连接器 | 0.70 | 3 | 0.20 | 有色金属 |
| inductor_transformer 电感 | 0.40 | 3 | 0.41 | 有色金属 + 稀土 |

---

## 7. 实施计划

### Phase 1 — 有色金属域上线（P0，约 500 行）

**覆盖品类**：继电器 / PCB / 铝散热器 / 连接器 / 电感 / 铝电解电容(铝箔部分) / MLCC(镍+铜部分)
**数据成本**：¥0

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1.1 | `app/models/material_price.py` | MaterialPrice SQLAlchemy 模型 + 数据库迁移注册 |
| 1.2 | `app/knowledge/material_mapping.py` | 全部 32 材料映射字典（一次性完成，后续 Phase 仅扩展数据源） |
| 1.3 | `app/services/sources/materials/__init__.py` + `base.py` | 抽象基类 MaterialPriceSource |
| 1.4 | `app/services/sources/materials/metals_api_source.py` | metals-api.com 免费 API 对接 |
| 1.5 | `app/services/material_price_service.py` | 编排层（三域架构 + 缓存 + 降级） |
| 1.6 | `app/services/material_tracker.py` | 30日/90日基线 + 三档阈值判定 + 稀土放大器 |
| 1.7 | `app/services/upstream/risk_context_builder.py` | 改造 _material_signals_for_category() |
| 1.8 | `app/models/event.py` | EventType 添加 MATERIAL_PRICE |
| 1.9 | `app/services/event_collector.py` | material_price 事件采集 |
| 1.10 | `app/config.py` | 新增材料 API 配置项 |
| 1.11 | `app/main.py` | lifespan 管理 MaterialPriceService 生命周期 |
| 1.12 | 测试文件 | test_material_mapping.py (15), test_material_tracker.py (14), test_material_price_service.py (10) |

### Phase 2 — 稀土 & 小金属域上线（P1，约 350 行）

**覆盖品类**：MLCC(完整材料链) / 钽电容 / 电感(高性能磁芯)
**数据成本**：¥0

| 步骤 | 文件 | 内容 |
|------|------|------|
| 2.1 | `app/services/sources/materials/rare_earth_source.py` | 稀土行业协会 HTML 解析（氧化镨钕/氧化镝/氧化钇） |
| 2.2 | `app/services/sources/materials/small_metal_source.py` | 亚洲金属网/金投网 HTML 解析（钽粉/钽丝/碳酸钡） |
| 2.3 | MaterialPriceService 更新 | 注册 RareEarthGroup 和 SmallMetalGroup |
| 2.4 | 测试文件 | test_rare_earth_parser.py (6), test_material_integration.py (8) |

### Phase 3 — 化工 & 非金属域上线（P2，约 300 行）

**覆盖品类**：PCB(完整) / 铝电解电容(完整) / 薄膜电容
**数据成本**：¥0

| 步骤 | 文件 | 内容 |
|------|------|------|
| 3.1 | `app/services/sources/materials/chemical_source.py` | 生意社 + 卓创 HTML 解析（6 种化工品） |
| 3.2 | `app/api/material_alerts.py` | Material Alerts API 端点 |
| 3.3 | MaterialPriceService 更新 | 注册 ChemicalGroup |
| 3.4 | 测试文件 | test_chemical_parser.py (6), 全量回归测试 |

### Phase 4 — 可选增强（P3）

- 配置 SMM / 卓创 / Mysteel 付费 API
- Dashboard "原材料异动" 监控面板
- 每周自动汇总材料价格变动周报

---

## 8. 配置项

```bash
# ── 有色金属域 ──
METALS_API_KEY=                    # metals-api.com 免费注册获取

# ── 稀土域 ──
RE_ASSOCIATION_URL=https://www.ac-rei.org.cn
ASIAN_METAL_BASE_URL=https://www.asianmetal.cn

# ── 化工域 ──
CHEM_100PPI_BASE=https://www.100ppi.com
CHEM_SCI99_BASE=https://www.sci99.com

# ── 可选付费 ──
SMM_API_KEY=
SCI99_API_KEY=
MYSTEEL_API_KEY=

# ── 通用参数 ──
MATERIAL_FETCH_INTERVAL_H=12       # 采集间隔(小时)
MATERIAL_WARNING_PCT=5.0           # YELLOW 阈值
MATERIAL_ALERT_PCT=10.0            # ORANGE 阈值
MATERIAL_CRITICAL_PCT=20.0         # RED 阈值
RARE_EARTH_AMPLIFIER=1.6           # 稀土传导系数放大因子
```

---

## 9. 验收标准

### 9.1 Phase 1 验收

- [ ] `material_mapping.py` 覆盖全部 32 种材料的映射字典，各字段无遗漏
- [ ] `MaterialPrice` 模型可正确创建表，价格写入/查询无异常
- [ ] `MetalsAPISource` 成功调用 metals-api.com 获取 Cu/Al/Ag/Sn/Ni/Zn 价格
- [ ] 主源失败时自动降级到备源，备源也失败时返回 stale 缓存并标注 degraded
- [ ] `MaterialTracker` 正确计算 30 日基线并触发三档阈值判定
- [ ] 稀土材料（氧化镝/氧化钇/氧化镨钕）传导系数自动乘以 1.6
- [ ] `risk_context_builder.py` 改造后，铜价涨 10% 时 PCB 品类的 material_track 加分 ≥20
- [ ] `event_type=material_price` 的事件正确写入 market_events 表
- [ ] 当所有材料源不可用时，系统退化回原布尔信号逻辑，不报错
- [ ] 全部 39 个测试用例通过

### 9.2 Phase 2 验收

- [ ] 稀土行业协会页面解析正确提取氧化镨钕/氧化镝/氧化钇日度价格
- [ ] 亚洲金属网/金投网正确提取钽粉/钽丝价格
- [ ] 钽粉涨 12% 时 tantalum_capacitor 品类的 material_track 加分 ≥20

### 9.3 Phase 3 验收

- [ ] 生意社/卓创页面正确提取 6 种化工品价格
- [ ] `GET /api/material-alerts` 返回正确格式的预警列表
- [ ] 全量回归测试：改造后的风险评分与原评分偏差在合理范围内（新材料信号是增量，不破坏原有逻辑）
