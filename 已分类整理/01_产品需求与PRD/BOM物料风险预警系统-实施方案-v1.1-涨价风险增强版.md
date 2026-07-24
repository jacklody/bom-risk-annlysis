# BOM物料风险预警系统实施方案 v1.1：涨价风险增强版

> 更新日期：2026-06-24  
> 本版补充“供应商涨价/上游成本传导”风险的系统实现方式，并说明与PRD的关系。  
> 输入样例：用户上传的《分立器件供应商涨价对比：扬杰科技 vs 长晶科技》。

---

## 1. PRD 与实施方案的关系

PRD 定义产品应该具备的能力，实施方案定义这些能力怎样落地。对于“涨价风险”来说，两份文档的关系如下：

| PRD中的定义 | 实施方案中的落地 |
|-------------|------------------|
| 用户上传涨价通知后，系统识别受影响BOM | 实现文件上传、文本解析/OCR、结构化抽取、事件入库、BOM匹配任务 |
| 风险提示展示涨幅、生效日、命中物料、成本影响 | 增加数据库字段、风险评分函数、前端表格列、报告导出字段 |
| 支持自动获取和主动触发 | 自动源接入 + 手动上传入口 + 分析任务调度 |
| 提供锁价、备货、替代、报价复核建议 | 规则引擎根据涨幅、窗口、库存、用量生成建议 |

因此，PRD 是“要实现的产品行为”，实施方案是“开发该行为的技术路径”。本次 v1.1 将两份文档的涨价风险口径统一为同一套字段和流程。

---

## 2. 为什么涨价因素必须加入系统

用户上传的案例显示，扬杰科技和长晶科技在 2026年7月1日 对分立器件进行 10%–20% 涨价，且覆盖二极管、TVS/ESD、三极管、MOSFET、IGBT 等高频BOM品类。这个风险与交期、库存、EOL不同，它不一定导致“买不到”，但会直接影响项目成本、报价有效期、备货窗口和替代料优先级。

系统应把涨价事件视为和 EOL、长交期同级的供应链事件。尤其当涨价生效日期临近时，系统需要从“记录信息”变成“触发动作”：扫描历史BOM、定位受影响物料、估算成本影响，并给出锁单或替代建议。

---

## 3. 总体实现架构

```text
涨价信息来源
  ├─ 用户上传：Markdown / PDF / 图片 / Excel / 邮件正文
  ├─ 自动获取：供应商公告 / 邮件监听 / 行业资讯 / 分销商价格快照
  └─ 人工录入：厂商、品类、涨幅、生效日期
        ↓
文本解析与结构化抽取
  ├─ 规则抽取：涨幅、日期、厂商名、品类关键词
  ├─ OCR：图片/PDF扫描件
  └─ LLM辅助：归纳影响范围、上游原因、建议动作
        ↓
人工确认
  ├─ 修正厂商别名
  ├─ 修正品类范围
  ├─ 确认涨幅和生效日期
  └─ 确认事件可信度
        ↓
生成 PriceIncreaseEvent / MarketEvent
        ↓
BOM匹配与风险评分
  ├─ 历史BOM全量扫描
  ├─ 新BOM即时评审
  ├─ 成本影响估算
  └─ 生成风险建议
        ↓
输出
  ├─ 项目风险看板
  ├─ 物料明细表
  ├─ Excel/Markdown报告
  └─ 告警通知
```

---

## 4. 数据获取方案

### 4.1 主动触发：用户上传涨价通知

这是第一优先级，因为供应商涨价函往往最先通过采购、销售或代理商发给企业内部，公开渠道可能滞后。

支持输入：

| 输入类型 | 处理方式 |
|----------|----------|
| Markdown / TXT | 直接解析文本 |
| PDF | 提取文字；扫描件走OCR |
| 图片 | OCR识别文字 |
| Excel / CSV | 按列解析厂商、品类、涨幅、生效日期 |
| 邮件正文 | 提取正文和附件，生成事件 |
| 手工录入 | 用户直接填写结构化字段 |

上传后的系统动作：

1. 解析文本。
2. 抽取结构化字段。
3. 进入“待确认事件”。
4. 用户确认后触发BOM分析。
5. 分析结果写入风险结果表。

### 4.2 自动触发：系统自行获取

| 数据源 | 实施方式 | 优先级 | 说明 |
|--------|----------|--------|------|
| 分销商价格快照 | 每天/每周记录价格，对比涨幅 | P0 | 最容易落地，能发现实际价格变化 |
| 用户邮箱 | IMAP/企业邮箱API监听供应商通知 | P1 | 能最早捕获内部涨价函 |
| 供应商官网公告 | 定时抓取公告页/RSS | P1 | 官方可信度高，但覆盖有限 |
| 飞书/企业微信/钉钉群文件 | 通过连接器或机器人接收文件 | P2 | 适合企业内部流转场景 |
| 行业资讯网页 | WebSearch/RSS/行业媒体 | P2 | 用于识别行业性涨价潮 |

自动获取不应直接把所有信息判为红色风险。系统应先生成待确认事件，除非来源是已授权供应商通知或用户确认。

---

## 5. 结构化抽取规则

### 5.1 事件字段

| 字段 | 示例 | 抽取方式 |
|------|------|----------|
| event_type | price_increase | 固定类型 |
| affected_brands | 扬杰科技、长晶科技 | 厂商词典 + LLM辅助 |
| affected_categories | 二极管、TVS、MOSFET、IGBT | 品类词典 + 描述匹配 |
| increase_min_pct | 10 | 正则识别 `10%–20%` |
| increase_max_pct | 20 | 正则识别 |
| effective_date | 2026-07-01 | 日期识别 |
| upstream_reason | 晶圆代工涨价、铜锡上涨、封装材料成本攀升 | 关键词抽取 |
| source_type | user_upload | 由入口决定 |
| confidence | 0.8 | 来源和字段完整度决定 |
| review_status | pending / confirmed / rejected | 人工确认状态 |

### 5.2 正则和词典规则

涨幅识别：

```python
r'(\d+(?:\.\d+)?)\s*%\s*[-–~至到]\s*(\d+(?:\.\d+)?)\s*%'
r'涨(?:价|幅).*?(\d+(?:\.\d+)?)\s*%'
r'上调.*?(\d+(?:\.\d+)?)\s*%'
```

日期识别：

```python
r'(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?'
r'(\d{1,2})月(\d{1,2})日(?:起|生效|执行)'
```

厂商别名示例：

| 标准厂商 | 别名 |
|----------|------|
| 扬杰科技 | 扬杰、Yangjie、YJ、扬州扬杰 |
| 长晶科技 | 长晶、CJ、Changjing、长电分立器件 |
| 英飞凌 | Infineon、英飞凌 |
| 德州仪器 | TI、Texas Instruments |

品类词典示例：

| 标准品类 | 关键词 |
|----------|--------|
| Diode | 二极管、整流、快恢复、肖特基、Schottky、Rectifier |
| TVS/ESD | TVS、ESD、保护器件、瞬态抑制 |
| MOSFET | MOS、MOSFET、场效应管、SGT、超结 |
| BJT | 三极管、BJT、晶体管 |
| IGBT | IGBT、功率模块 |

---

## 6. BOM匹配逻辑

### 6.1 匹配层级

| 层级 | 匹配方式 | 风险性质 |
|------|----------|----------|
| L1 | BOM品牌字段命中涨价厂商 | 确定命中 |
| L2 | MPN前缀或型号规则命中厂商 | 高置信命中 |
| L3 | 品类命中且厂商未知 | 波及风险 |
| L4 | 描述文本命中同类器件 | 波及风险 |
| L5 | 替代料中包含涨价厂商 | 替代方案风险 |

### 6.2 风险等级判定

```text
红色：确定命中厂商 + 涨幅≥10% + 生效日≤7天/已生效
红色：确定命中厂商 + 高用量物料 + 单板成本影响≥1%
黄色：确定命中厂商 + 生效日≤30天
黄色：品类波及 + 同类厂商集体涨价
绿色：涨价影响小且已有安全库存或替代料
灰色：字段不完整，仅保存事件，不触发业务动作
```

---

## 7. 成本影响计算

### 7.1 单物料影响

```text
当前单行成本 = 当前单价 × 单板用量
涨价后单行成本 = 当前单价 × (1 + 涨幅) × 单板用量
单行成本增加 = 当前单行成本 × 涨幅
```

### 7.2 项目影响

```text
单板成本增加 = Σ 命中物料单行成本增加
批量成本增加 = 单板成本增加 × 计划生产数量
```

### 7.3 区间涨幅处理

用户上传的扬杰/长晶通知是 10%–20% 这种区间涨幅。系统应同时给出三档影响：

```text
低位：按10%计算
中位：按15%计算
高位：按20%计算
```

如果BOM缺少单价，系统先用实时API价格或历史采购价补齐；仍缺失时，仅展示“命中涨价风险”，不估算金额。

---

## 8. 数据库改造建议

### 8.1 复用现有 MarketEvent

当前项目已有市场事件和BOM匹配框架，建议优先扩展现有 `MarketEvent`，不要新建完全独立系统。

新增字段：

```sql
ALTER TABLE market_events ADD COLUMN increase_min_pct FLOAT;
ALTER TABLE market_events ADD COLUMN increase_max_pct FLOAT;
ALTER TABLE market_events ADD COLUMN effective_date DATETIME;
ALTER TABLE market_events ADD COLUMN upstream_reason TEXT;
ALTER TABLE market_events ADD COLUMN source_type VARCHAR(32);
ALTER TABLE market_events ADD COLUMN source_file TEXT;
ALTER TABLE market_events ADD COLUMN review_status VARCHAR(32) DEFAULT 'pending';
```

`event_type` 枚举增加：

```python
PRICE_INCREASE = "price_increase"
```

### 8.2 BOM结果字段

```sql
ALTER TABLE bom_items ADD COLUMN price_risk_level VARCHAR(16) DEFAULT 'gray';
ALTER TABLE bom_items ADD COLUMN price_risk_reason TEXT;
ALTER TABLE bom_items ADD COLUMN price_increase_pct VARCHAR(32);
ALTER TABLE bom_items ADD COLUMN price_effective_date DATETIME;
ALTER TABLE bom_items ADD COLUMN estimated_cost_delta FLOAT;
ALTER TABLE bom_items ADD COLUMN price_action_suggestion TEXT;
ALTER TABLE bom_items ADD COLUMN matched_price_event_ids VARCHAR(1024);
```

### 8.3 事件附件表

```sql
CREATE TABLE event_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    filename VARCHAR(256),
    file_path TEXT,
    file_type VARCHAR(32),
    extracted_text TEXT,
    uploaded_by VARCHAR(128),
    created_at DATETIME
);
```

---

## 9. 后端服务设计

### 9.1 新增服务

| 服务 | 职责 |
|------|------|
| `PriceNoticeParser` | 解析涨价通知，抽取厂商、品类、涨幅、生效日、原因 |
| `PriceRiskMatcher` | 将涨价事件匹配到BOM物料 |
| `CostImpactCalculator` | 计算单行、单板、批量成本影响 |
| `PriceEventReviewService` | 管理待确认、已确认、已驳回状态 |
| `PriceMonitorScheduler` | 定时抓取价格快照和公告源 |

### 9.2 API设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/price-events/upload` | 上传涨价通知 |
| GET | `/api/price-events/{id}` | 查看解析结果 |
| POST | `/api/price-events/{id}/confirm` | 确认事件并入库 |
| POST | `/api/price-events/{id}/analyze` | 对指定范围触发BOM分析 |
| GET | `/api/price-events/{id}/matches` | 查看命中BOM物料 |
| GET | `/api/price-events/dashboard` | 涨价风险看板 |

### 9.3 主动触发接口流程

```text
POST /api/price-events/upload
→ 返回 extracted_fields + event_id

POST /api/price-events/{event_id}/confirm
→ 写入 confirmed 状态

POST /api/price-events/{event_id}/analyze
body: { scope: 'all_projects' | 'project', project_id?: 1 }
→ 返回命中项目和物料风险结果
```

---

## 10. 前端改造建议

### 10.1 新增页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 涨价事件列表 | `/price-events` | 查看所有涨价事件，按状态和生效日筛选 |
| 上传涨价通知 | `/price-events/upload` | 上传Markdown/PDF/图片/Excel |
| 事件确认页 | `/price-events/:id/review` | 展示抽取结果，允许人工修正 |
| 事件命中结果 | `/price-events/:id/matches` | 查看命中项目、物料和成本影响 |

### 10.2 现有页面改造

| 页面 | 改造点 |
|------|--------|
| BOM分析结果页 | 增加涨价风险列、生效日期、成本影响、建议动作 |
| 项目详情页 | 增加项目级涨价影响汇总 |
| 市场事件页 | 支持 `price_increase` 类型和结构化字段 |
| 风险仪表盘 | 增加“即将生效涨价事件”和“成本影响TOP项目” |

---

## 11. 开发阶段建议

### 阶段一：主动上传触发（优先做）

周期：3–5天。

交付：

1. Markdown/TXT涨价通知上传。
2. 正则解析厂商、涨幅、生效日期、品类。
3. 人工确认页。
4. 匹配历史BOM。
5. 风险结果新增涨价列。

这一步已经能处理用户上传的扬杰/长晶案例。

### 阶段二：成本影响估算

周期：3–5天。

交付：

1. 读取BOM单价和数量。
2. 无单价时调用实时API或历史采购价。
3. 输出低/中/高三档成本影响。
4. Excel报告增加涨价影响汇总。

### 阶段三：自动获取

周期：1–2周。

交付：

1. 分销商价格快照。
2. 官网公告或邮件监听。
3. 待确认事件队列。
4. 自动触发历史BOM巡检。

### 阶段四：替代与决策建议

周期：2–4周。

交付：

1. 对红色涨价物料推荐替代。
2. 对7天内生效事件生成锁单清单。
3. 对项目生成报价复核建议。
4. 记录已处理动作。

---

## 12. 对现有代码补丁的影响

此前 v0.3 补丁已经加入 LCSC/Mouser 实时库存、价格、交期和生命周期字段。涨价增强可以继续沿用该结构：

| 现有模块 | 可复用点 | 需要新增 |
|----------|----------|----------|
| `MarketEvent` | 市场事件模型 | `price_increase`类型和涨价字段 |
| `BOMMatcher` | 品牌/品类匹配 | 涨价事件专用匹配规则 |
| `supply_risk.py` | 综合风险评分 | `score_price_increase()` |
| `risk_analysis.py` | 分析入口 | 触发指定事件分析的API |
| 前端风险表格 | 明细展示 | 涨价风险列和成本影响列 |
| `SupplyDataService` | 实时价格查询 | 价格快照存储和历史对比 |

---

## 13. 用户上传案例的系统处理示例

输入：`分立器件涨价对比_扬杰vs长晶_20260624.md`

系统抽取结果：

```json
{
  "event_type": "price_increase",
  "affected_brands": ["扬杰科技", "长晶科技"],
  "affected_categories": ["整流二极管", "快恢复二极管", "肖特基二极管", "稳压管", "TVS/ESD", "三极管", "MOSFET", "IGBT"],
  "increase_min_pct": 10,
  "increase_max_pct": 20,
  "effective_date": "2026-07-01",
  "upstream_reason": "晶圆代工涨价、铜锡等原材料上涨、封装材料成本上升",
  "source_type": "user_upload",
  "review_status": "pending"
}
```

系统输出风险提示：

```text
命中涨价事件：扬杰科技/长晶科技分立器件涨价10%–20%，2026-07-01生效。
该物料属于TVS/ESD保护器件，品牌为长晶科技，确认命中。
预计单行成本增加：当前单价 × 用量 × 10%–20%。
建议：生效日前确认库存和在途订单；如生产计划明确，优先锁价备货；同时检查是否存在第二供应商。
```

---

## 14. 实施优先级结论

短期不建议先做复杂的自动爬虫。最有效的路径是：先支持用户上传涨价函并主动触发BOM识别，再补价格快照和自动监控。

推荐顺序：

1. 涨价通知上传解析。
2. 人工确认。
3. 历史BOM/新BOM匹配。
4. 成本影响估算。
5. 报告导出和项目看板。
6. 自动价格快照。
7. 邮件/公告/群文件自动监听。

这样能最快把你已经收到的供应商涨价通知转成系统内可追踪、可量化、可处理的风险事件。
