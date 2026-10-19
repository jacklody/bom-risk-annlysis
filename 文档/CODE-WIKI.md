# 交期风险排查项目 Code Wiki

> 本文档为当前仓库的代码知识库，按实际代码结构重新生成。重点覆盖主力版本 `交期风险排查V4` 的前后端架构、核心模块、API、数据源、运行方式、近期修复与维护注意事项。

---

## 1. 项目定位

本项目是一套面向电子制造、BOM 选型评审与交付风险预警的系统，目标是在项目导入、在产交付和供应链监控过程中，把 BOM 物料、供应数据、市场事件、原材料价格、行业链路和人工/LLM 情报整合成可追溯的风险判断。

核心能力包括：

- BOM 文件上传、解析、行级物料识别与风险评估。
- 项目级 BOM 管理、详情查看、报告导出与评审闭环。
- 风险链仪表盘，用图谱展示材料、品类、项目与风险传播链路。
- 原材料价格预警，包括材料列表、趋势查询、缓存统计与聚合摘要。
- 市场事件、情报收件箱、趋势库与人工录入入口。
- 多源供应数据查询，包括 LCSC、Mouser、DigiKey、观芯台等连接器。
- 优选库导入、命中评审与风险建议。
- 飞书 webhook / 机器人相关能力。
- LLM 辅助的信息抽取、风险解释与建议生成。

---

## 2. 当前主力版本

| 版本 | 路径 | 技术形态 | 当前定位 |
|---|---|---|---|
| V4 | `交期风险排查V4/` | Vue 3 + Vite + FastAPI | 当前功能最完整、默认优先维护版本 |
| V5 | `V5版本/bom-risk-review/` | Streamlit 单体 | 轻量 MVP / 快速演示版本 |
| production-v1 | `production-v1/` | 基于 V4 思路改造 | 生产化改造试验版本，包含 P0/P1/P2 风险闭环能力 |

除非用户明确指定其它版本，当前开发、排障、启动与文档说明默认以 `交期风险排查V4` 为准。

---

## 3. 技术栈

### 3.1 后端

路径：`交期风险排查V4/backend`

| 类别 | 技术/库 |
|---|---|
| Web 框架 | FastAPI、Starlette、Uvicorn |
| 数据库 | SQLite，默认 `sqlite:///data/market_risk.db` |
| ORM | SQLAlchemy 2.x，同步 Session |
| 配置 | pydantic-settings、python-dotenv |
| HTTP 客户端 | httpx、requests |
| 文件处理 | python-multipart、aiofiles、openpyxl |
| HTML 解析 | BeautifulSoup4、lxml |
| WebSocket | websockets |
| LLM | OpenAI SDK 兼容接口，默认 DeepSeek |
| 测试 | pytest、pytest-asyncio |

关键依赖文件：`交期风险排查V4/backend/requirements.txt`

### 3.2 前端

路径：`交期风险排查V4/frontend`

| 类别 | 技术/库 |
|---|---|
| 框架 | Vue 3 |
| 构建 | Vite |
| 路由 | vue-router，hash 模式 |
| UI | Element Plus、@element-plus/icons-vue |
| HTTP | axios |
| 单元测试 | Vitest、@vue/test-utils、jsdom |
| E2E | Playwright |

关键依赖文件：`交期风险排查V4/frontend/package.json`

---

## 4. 目录结构总览

```text
交期风险排查/
├── 文档/
│   └── CODE-WIKI.md
├── 交期风险排查V4/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── api/
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   └── knowledge/
│   │   ├── api/v1/
│   │   ├── tests/
│   │   └── requirements.txt
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── api/
│   │   │   ├── components/
│   │   │   ├── router/
│   │   │   └── views/
│   │   ├── package.json
│   │   └── vite.config.js
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── README.md
├── V5版本/
├── production-v1/
├── start-bom-system.ps1
├── 一键启动-BOM交期风险系统.bat
└── start-logs/
```

---

## 5. V4 运行架构

```text
浏览器
  │
  │ http://localhost:9000  Vue SPA
  ▼
Vite Dev Server
  │
  │ /api 代理到 http://127.0.0.1:5001
  ▼
FastAPI app.main:app
  │
  ├─ app/api/*                业务 API
  ├─ backend/api/v1/*          v1 API
  ├─ app/services/*            业务服务层
  ├─ app/knowledge/*           规则和知识库
  ├─ app/models/*              SQLAlchemy 模型
  └─ data/market_risk.db       SQLite 数据库
```

当前开发端口：

- 前端：`http://localhost:9000/`
- 后端：`http://127.0.0.1:5001`
- 健康检查：`http://127.0.0.1:5001/api/health`

前端 Vite 代理配置位于 `交期风险排查V4/frontend/vite.config.js`：

```javascript
server: {
  port: 9000,
  proxy: {
    '/api': 'http://127.0.0.1:5001'
  }
}
```

---

## 6. 后端入口与生命周期

入口文件：`交期风险排查V4/backend/app/main.py`

FastAPI 应用定义：

- 应用标题：`BOM风险分析器`
- 版本：`4.1.0`
- 生命周期：`lifespan`

启动生命周期主要做三件事：

1. 调用 `init_db()` 初始化数据库。
2. 初始化 `SupplyDataService`，注册并健康检查供应数据源。
3. 初始化 `MaterialPriceService`，预热原材料价格服务。

健康检查接口：

```text
GET /api/health
```

返回示例：

```json
{"status":"ok","version":"4.1.0"}
```

---

## 7. 后端配置中心

配置文件：`交期风险排查V4/backend/app/config.py`

主要配置分组：

| 分组 | 关键字段 | 说明 |
|---|---|---|
| 数据库 | `database_url`、`data_dir` | 默认 SQLite，数据目录为 `data` |
| LLM | `llm_provider`、`llm_api_key`、`llm_base_url`、`llm_model` | 默认 DeepSeek 兼容 OpenAI SDK |
| 风险阈值 | `min_confidence_threshold`、`cross_validation_sources` | 多源校验与置信度阈值 |
| 供应数据 | `mouser_*`、`lcsc_*`、`digikey_*`、`guanxintai_*` | 供应商库存、交期、价格查询 |
| Nexar/Octopart | `nexar_enabled`、`nexar_client_id` | 默认未启用，占位支持 |
| 芯查查 | `xinchacha_enabled`、`xinchacha_*` | 默认未启用，占位支持 |
| 原材料 | `metals_api_key`、`smm_*`、`mysteel_*`、`lme_enabled` | 金属、稀土、化工等价格源 |
| 灾害事件 | `gdacs_enabled`、`usgs_enabled` | 灾害/地震风险源 |
| CORS | `cors_allowed_origins` | 默认 `*` |

维护注意：

- API Key 不应写入代码或文档正文，应通过 `.env` 或部署环境变量提供。
- SQLite 使用同步 SQLAlchemy Session，API 内不要对 `db.execute()` 使用 `await`。

---

## 8. 数据库与模型层

数据库文件默认位于：`交期风险排查V4/backend/data/market_risk.db`

数据库入口：`交期风险排查V4/backend/app/database.py`

当前模型目录：`交期风险排查V4/backend/app/models`

| 模型文件 | 主要职责 |
|---|---|
| `bom.py` | BOM 项目、BOM 行、上传和解析结果 |
| `event.py` | 市场事件、供应链事件、事件证据 |
| `risk_assessment.py` | 风险评估结果与评分 |
| `watch.py` | 情报监控对象和监控状态 |
| `preferred.py` | 优选库物料、评审命中记录 |
| `material_price.py` | 原材料价格、价格快照、趋势数据 |
| `media_source.py` | 媒体源、来源元数据 |
| `chain_node.py` | 风险链节点 |
| `chain_edge.py` | 风险链边关系 |
| `exposure.py` | BOM 暴露度、受影响范围 |
| `dashboard_notification.py` | 仪表盘通知和提醒 |

---

## 9. API 路由总览

路由注册集中在 `app/main.py`。

### 9.1 app/api 路由

| 模块 | 典型前缀/路径 | 职责 |
|---|---|---|
| `risk_chain.py` | `/api/risk-chain/*` | 风险链仪表盘、材料链路图、项目/材料维度链路 |
| `bom_upload.py` | `/api/bom/*` | BOM 上传、解析、分析入口 |
| `bom_project.py` | `/api/bom/*` | BOM 项目列表、详情、项目级操作 |
| `risk_analysis.py` | `/api/risk/*` | BOM 风险分析、多源供应风险评估 |
| `events.py` | `/api/events/*` | 市场事件管理 |
| `intel_watch.py` | `/api/intel/*` | 情报监控对象和智能扫描 |
| `market_inbox.py` | `/api/market-inbox/*` | 市场情报收件箱、人工提交、审核队列 |
| `preferred_library.py` | `/api/preferred-library/*` | 优选库导入、汇总、BOM 命中评审 |
| `market_trends.py` | `/api/market-trends/*` | 市场趋势数据 |
| `supply.py` | `/api/supply/*` | 供应数据查询 |
| `market_intel.py` | 自带路由前缀 | 市场情报分析 |
| `dashboard.py` | `/api/dashboard/*` | 仪表盘概览、摘要、通知 |
| `material_alerts.py` | `/api/material-alerts/*` | 原材料预警列表、趋势、摘要、缓存统计 |
| `material_ws.py` | WebSocket 路由 | 原材料预警实时推送 |
| `feishu_webhook.py` | `/api/feishu/*` | 飞书 webhook / 机器人集成 |

### 9.2 风险链接口

模块：`app/api/risk_chain.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/risk-chain/dashboard` | 风险链首页仪表盘数据 |
| GET | `/api/risk-chain/material-chain` | 材料链路图数据 |
| GET | `/api/risk-chain/material-chain/by-material` | 按材料查询链路 |
| GET | `/api/risk-chain/material-chain/by-project` | 按项目查询链路 |

### 9.3 原材料预警接口

模块：`app/api/material_alerts.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/material-alerts` | 原材料价格预警列表，支持分页和过滤 |
| GET | `/api/material-alerts/trends/{material_key}` | 单材料历史价格趋势 |
| GET | `/api/material-alerts/summary` | 全品类风险聚合摘要 |
| GET | `/api/material-alerts/cache-stats` | 价格服务缓存/配额统计 |

近期修复：趋势接口已从异步错误调用改为同步 SQLAlchemy Session 调用，并修复价格数组误取时间戳的问题。

### 9.4 市场情报收件箱接口

模块：`app/api/market_inbox.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/market-inbox/` | 情报列表 |
| GET | `/api/market-inbox/{notice_id}` | 情报详情 |
| GET | `/api/market-inbox/review-queue` | 审核队列 |
| POST | `/api/market-inbox/submit` | 人工提交情报 |
| POST | `/api/market-inbox/review/{signal_id}` | 审核处理 |

### 9.5 优选库接口

模块：`app/api/preferred_library.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/preferred-library/import` | 导入优选库 |
| GET | `/api/preferred-library/summary` | 优选库统计摘要 |
| GET | `/api/preferred-library/parts` | 优选物料列表 |
| POST | `/api/preferred-library/review/{bom_project_id}` | 对项目做优选库命中评审 |
| GET | `/api/preferred-library/review/{bom_project_id}` | 获取项目评审结果 |

### 9.6 v1 接口

目录：`交期风险排查V4/backend/api/v1`

| 模块 | 前缀 | 说明 |
|---|---|---|
| `delivery_risk.py` | `/api/v1/delivery-risk` | 交付风险总览、材料、时间线、建议、确认 |
| `project_review.py` | `/api/v1/project-review` | 项目评审摘要、BOM 行、审批、导出 |
| `document_upload.py` | 视模块定义 | 文档上传相关能力 |

---

## 10. 后端服务层

服务目录：`交期风险排查V4/backend/app/services`

| 服务文件/目录 | 主要职责 |
|---|---|
| `bom_parser.py` | Excel/表格 BOM 解析 |
| `bom_matcher.py` | BOM 行物料匹配、品类识别 |
| `bom_exposure_engine.py` | BOM 对风险事件/材料涨价的暴露度计算 |
| `supply_data.py` | 多源供应数据编排与聚合 |
| `supply_risk.py` | 库存、交期、价格维度供应风险评分 |
| `material_price_service.py` | 原材料价格查询、缓存、预警判断 |
| `material_tracker.py` | 原材料跟踪逻辑 |
| `media_crawler.py` | 媒体源采集、手动转发与网页抓取策略 |
| `market_intel_engine.py` | 市场情报规则处理与信号生成 |
| `intel_agent.py` | 情报智能体编排 |
| `nlp_extractor.py` | 文本抽取、实体识别、事件结构化 |
| `llm_client.py` | LLM 统一客户端封装 |
| `event_collector.py` | 事件采集与入库 |
| `incremental_scanner.py` | 增量扫描 |
| `chain_query_service.py` | 风险链查询和图谱数据组装 |
| `dashboard_summary.py` | 仪表盘摘要聚合 |
| `dashboard_notification.py` | 仪表盘通知逻辑 |
| `delivery_risk_service.py` | 交付风险服务 |
| `project_review_service.py` | 项目评审服务 |
| `risk_report_export.py` | 风险报告导出 |
| `auto_escalation_engine.py` | 自动提级和告警升级 |
| `sources/` | 外部供应数据源连接器 |
| `upstream/` | 上游风险引擎、材料链推理、证据链 |
| `preferred_library/` | 优选库业务服务 |
| `llm/` | LLM 细分能力模块 |
| `feishu_bot/` | 飞书机器人服务 |

---

## 11. 外部信息源与实现状态

### 11.1 供应数据源

供应数据编排服务：`app/services/supply_data.py`

注册的数据源类包括：

| 数据源 | 类型 | 当前状态 | 说明 |
|---|---|---|---|
| LCSC / 立创商城 | 库存/价格/交期 | 已接入 | 默认启用，常作为无密钥可用源 |
| Mouser | 库存/价格/交期 | 代码已接入 | 依赖 API Key 和健康检查 |
| DigiKey | 库存/价格/交期 | 代码已接入 | 依赖 client id / secret |
| 观芯台 | 行情/供应搜索 | 代码已接入但可能降级 | 健康检查失败时会跳过 |
| Nexar / Octopart | 元器件供应 API | 占位/默认关闭 | 依赖 Nexar 凭证 |
| 芯查查 | 企业/器件信息 | 占位/默认关闭 | 依赖应用凭证 |

聚合逻辑：

- `SupplyDataService.initialize()` 懒加载数据源。
- 每个数据源需通过 `is_configured` 和 `health_check()`。
- `query_one()` 对单个 MPN 查询多源结果。
- `_merge_best()` 合并库存、交期、价格，并提供 best-case / worst-case 视角。

### 11.2 原材料价格源

配置在 `app/config.py`，服务在 `app/services/material_price_service.py` 及 `app/services/sources/materials/`。

| 数据源 | 当前状态 | 说明 |
|---|---|---|
| Metals API | 可配置 | 依赖 `metals_api_key` |
| SMM | 默认关闭 | 依赖 `smm_api_key` 和 `smm_enabled` |
| Mysteel | 默认关闭 | 依赖 `mysteel_api_key` 和 `mysteel_enabled` |
| LME | 可配置 | `lme_enabled` 控制 |
| 稀土/小金属/化工映射 | 规则支持 | 由材料映射与价格服务组合使用 |

### 11.3 灾害与宏观事件源

| 数据源 | 当前状态 | 说明 |
|---|---|---|
| GDACS | 默认启用 | 灾害事件源 |
| USGS Earthquake | 默认启用 | 地震事件源 |

### 11.4 媒体与公众号源

媒体源定义：`app/knowledge/media_sources.py`

| 来源 | 类型 | 策略 | 当前状态 |
|---|---|---|---|
| 芯师爷 | 微信公众号 | `manual_forward` | 等待人工转发 |
| 半导体行业观察 | 微信公众号 | `manual_forward` | 等待人工转发 |
| 满天芯 | 微信公众号 | `manual_forward` | 等待人工转发 |
| 芯智讯 | 微信公众号 | `manual_forward` | 等待人工转发 |
| 国际电子商情 | 网站 | `http_html` | 当前禁用 |
| 电子工程世界 EEWorld | 网站 | `http_html` | 当前禁用 |
| 立创商城 / JLCSearch | 网站/API | `api_json` | 启用 |
| 观芯台行情搜索 | 网站搜索 | `keyword_search` | 启用 |

维护结论：微信公众号没有稳定公开 API，当前按“人工转发到系统/收件箱”实现，不应在文档或代码中承诺自动抓取公众号原文。

---

## 12. 知识库模块

目录：`交期风险排查V4/backend/app/knowledge`

| 文件 | 作用 |
|---|---|
| `brand_category_map.py` | 品牌与品类映射 |
| `category_material_mapping.py` | 品类到上游材料映射 |
| `category_tree.py` | 电子物料品类树 |
| `event_templates.py` | 市场事件模板 |
| `industry_chain.py` | 行业链知识 |
| `market_intel.py` | 市场情报规则/知识 |
| `material_mapping.py` | 原材料 key、领域、名称映射 |
| `media_sources.py` | 媒体源/公众号/网站源注册表 |
| `part_number_prefix.py` | MPN 前缀识别知识 |
| `risk_chain_library.py` | 风险链库与传播关系 |

---

## 13. 前端结构

前端根目录：`交期风险排查V4/frontend`

### 13.1 路由

路由文件：`src/router/index.js`

| 路径 | 页面 | 说明 |
|---|---|---|
| `/` | `RiskChainDashboard.vue` | 默认首页，风险链仪表盘 |
| `/analyze` | `BomAnalyze.vue` | BOM 分析入口 |
| `/dashboard` | `RiskDashboard.vue` | 风险总览仪表盘 |
| `/projects` | `BomProjects.vue` | BOM 项目列表 |
| `/projects/:id` | `BomProjectDetail.vue` | 项目详情 |
| `/events` | `MarketEvents.vue` | 市场事件 |
| `/market-trends` | `MarketTrends.vue` | 市场趋势 |
| `/market-inbox` | `MarketInbox.vue` | 市场情报收件箱 |
| `/preferred-library` | `PreferredLibrary.vue` | 优选库 |
| `/watch` | `IntelWatch.vue` | 情报监控 |
| `/materials` | `MaterialWatch.vue` | 原材料价格预警 |

### 13.2 主要页面

| 页面文件 | 主要职责 |
|---|---|
| `RiskChainDashboard.vue` | 风险链首页，承载材料传播链路和聚合卡片 |
| `MaterialWatch.vue` | 原材料预警列表、趋势抽屉、摘要和缓存统计 |
| `BomAnalyze.vue` | BOM 上传和分析流程 |
| `BomProjects.vue` | BOM 项目管理 |
| `BomProjectDetail.vue` | 项目详情、行级风险、报告信息 |
| `MarketEvents.vue` | 市场事件列表和详情 |
| `MarketInbox.vue` | 外部情报提交与审核 |
| `MarketTrends.vue` | 趋势类信息展示 |
| `PreferredLibrary.vue` | 优选库导入、查询和项目评审 |
| `IntelWatch.vue` | 情报监控对象管理 |
| `RiskDashboard.vue` | 风险统计和综合仪表盘 |
| `DeliveryRisk.vue` | 交付风险视图 |
| `ProjectReview.vue` | 项目评审视图 |

### 13.3 主要组件

| 组件 | 说明 |
|---|---|
| `IndustryChainGraph.vue` | 风险链/材料链图谱组件，已支持真正全屏查看 |
| `BomUploader.vue` | BOM 上传组件 |
| `BomImpactPanel.vue` | BOM 影响面板 |
| `MaterialPrice.vue` | 材料价格展示组件 |
| `RiskSignalFlow.vue` | 风险信号流展示 |
| `RiskSummary.vue` | 风险摘要 |
| `RiskDetailTable.vue` | 风险明细表 |
| `ManualEventQuickAdd.vue` | 人工快速录入事件 |
| `MarketEventDetailDrawer.vue` | 市场事件详情抽屉 |
| `DocumentUpload.vue` | 文档上传 |
| `ProgressSteps.vue` | 流程步骤展示 |
| `V32EvidencePanel.vue` | 证据链展示 |

### 13.4 前端 API 客户端

目录：`src/api`

| 文件 | 对应后端能力 |
|---|---|
| `client.js` | axios 基础实例 |
| `bom.js` | BOM 上传、分析、项目相关接口 |
| `dashboard.js` | 仪表盘接口 |
| `events.js` | 市场事件接口 |
| `intelWatch.js` | 情报监控接口 |
| `marketInbox.js` | 市场情报收件箱接口 |
| `marketTrends.js` | 市场趋势接口 |
| `materialAlerts.js` | 原材料预警接口 |
| `preferredLibrary.js` | 优选库接口 |
| `riskChain.js` | 风险链接口 |
| `riskChainService.js` | 风险链数据适配/服务封装 |
| `supply.js` | 供应数据接口 |

---

## 14. 近期已完成修复

### 14.1 风险链图谱真正全屏

文件：`frontend/src/components/IndustryChainGraph.vue`

问题：原全屏按钮只复位或局部最大化，不能进入浏览器真正全屏，材料传播链路难以看清。

修复要点：

- 使用 Browser Fullscreen API：`requestFullscreen()` / `exitFullscreen()`。
- 增加 `fullscreenchange` 状态同步。
- 增加不支持 Fullscreen API 时的 fixed 覆盖层兜底。
- 将“复位视图”和“真正全屏”拆成两个按钮。
- 全屏状态下提升图谱容器、标题、节点文字和控制按钮可读性。

### 14.2 原材料趋势按钮报错

文件：`backend/app/api/material_alerts.py`

问题：`材料链路库 → 原材料预警明细 → 趋势` 点击后提示“加载趋势失败”，后端趋势接口返回 500。

根因：

- 数据库是同步 SQLAlchemy Session，但接口内曾对 `db.execute()` 使用 `await`。
- 趋势统计中把查询结果元组的时间戳误当成价格值。
- SQLite 时间可能为 naive datetime，与 UTC aware datetime 比较存在风险。

修复要点：

- 改为 `result = db.execute(stmt)`。
- 价格数组改为从 `(price, ts, source)` 的 `price` 字段提取。
- 跳过空价格并转换为 `float`。
- 对 naive datetime 补齐 UTC 时区再比较。

验证结果：

- `GET /api/material-alerts/trends/cu_cathode?days=90` 返回 200。
- `GET /api/material-alerts?limit=3` 返回 200。
- `GET /api/health` 返回 200。
- 前端 `/#/materials` 页面可访问。
- 前端 `npm run build` 已通过。

---

## 15. 启动方式

### 15.1 启动后端

在 PowerShell 中进入后端目录：

```powershell
cd "d:\1项目清单\交期风险排查\交期风险排查V4\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 5001
```

验证：

```powershell
Invoke-WebRequest http://127.0.0.1:5001/api/health
```

### 15.2 启动前端

在 PowerShell 中进入前端目录：

```powershell
cd "d:\1项目清单\交期风险排查\交期风险排查V4\frontend"
npm run dev
```

访问：

```text
http://localhost:9000/
```

### 15.3 常用页面

| 页面 | URL |
|---|---|
| 风险链首页 | `http://localhost:9000/` |
| BOM 分析 | `http://localhost:9000/#/analyze` |
| 项目列表 | `http://localhost:9000/#/projects` |
| 市场事件 | `http://localhost:9000/#/events` |
| 情报收件箱 | `http://localhost:9000/#/market-inbox` |
| 优选库 | `http://localhost:9000/#/preferred-library` |
| 情报监控 | `http://localhost:9000/#/watch` |
| 原材料预警 | `http://localhost:9000/#/materials` |

---

## 16. 测试与校验

### 16.1 前端

```powershell
cd "d:\1项目清单\交期风险排查\交期风险排查V4\frontend"
npm run build
npm run test
npm run test:e2e
```

其中 `npm run build` 是当前最常用的前端构建校验。

### 16.2 后端

```powershell
cd "d:\1项目清单\交期风险排查\交期风险排查V4\backend"
pytest
```

### 16.3 接口冒烟

```powershell
Invoke-WebRequest http://127.0.0.1:5001/api/health
Invoke-WebRequest http://127.0.0.1:5001/api/risk-chain/dashboard
Invoke-WebRequest "http://127.0.0.1:5001/api/material-alerts?limit=3"
Invoke-WebRequest "http://127.0.0.1:5001/api/material-alerts/trends/cu_cathode?days=90"
```

---

## 17. 维护约定

- 当前默认维护版本是 `交期风险排查V4`。
- 前端开发端口是 `9000`，后端开发端口是 `5001`。
- Vite `/api` 代理必须指向 `http://127.0.0.1:5001`。
- 后端数据库 Session 是同步 SQLAlchemy Session，不要在普通接口中 `await db.execute()`。
- 外部 API Key 不得写入仓库，不得在日志中输出。
- 微信公众号来源当前按人工转发处理，不承诺自动抓取。
- 数据源健康检查失败时应降级跳过，而不是阻断系统启动。
- 修改前端后至少运行 `npm run build`。
- 修改后端业务逻辑后至少运行相关接口冒烟或 `pytest`。
- 若要继续使用项目真理源文件，应先确认或重建根目录 `PROJECT_CONTEXT_SNAPSHOT.md`，因为本次扫描未在项目根目录找到该文件。

---

## 18. 快速定位索引

| 需求 | 优先查看文件 |
|---|---|
| 后端启动、路由注册 | `交期风险排查V4/backend/app/main.py` |
| 配置和 API Key | `交期风险排查V4/backend/app/config.py` |
| 数据库 Session | `交期风险排查V4/backend/app/database.py` |
| 原材料预警接口 | `交期风险排查V4/backend/app/api/material_alerts.py` |
| 材料价格服务 | `交期风险排查V4/backend/app/services/material_price_service.py` |
| 风险链接口 | `交期风险排查V4/backend/app/api/risk_chain.py` |
| 风险链图谱组件 | `交期风险排查V4/frontend/src/components/IndustryChainGraph.vue` |
| 前端路由 | `交期风险排查V4/frontend/src/router/index.js` |
| 前端代理和测试配置 | `交期风险排查V4/frontend/vite.config.js` |
| 原材料页面 | `交期风险排查V4/frontend/src/views/MaterialWatch.vue` |
| 原材料前端 API | `交期风险排查V4/frontend/src/api/materialAlerts.js` |
| 供应数据编排 | `交期风险排查V4/backend/app/services/supply_data.py` |
| 供应数据源连接器 | `交期风险排查V4/backend/app/services/sources/` |
| 媒体/公众号源注册 | `交期风险排查V4/backend/app/knowledge/media_sources.py` |
| 品类到材料映射 | `交期风险排查V4/backend/app/knowledge/category_material_mapping.py` |
| 材料 key 映射 | `交期风险排查V4/backend/app/knowledge/material_mapping.py` |
| 优选库页面 | `交期风险排查V4/frontend/src/views/PreferredLibrary.vue` |
| 优选库后端 | `交期风险排查V4/backend/app/api/preferred_library.py` |

---

## 19. 当前已知注意事项

1. `PROJECT_CONTEXT_SNAPSHOT.md` 曾被要求作为项目真理源文件，但本次在项目根目录未扫描到该文件，需要后续确认是否重建。
2. 观芯台等网页/搜索类源可能因站点变化或反爬策略健康检查失败，系统应允许降级。
3. Nexar、芯查查、部分原材料商业数据源默认关闭，需要凭证后才能启用。
4. 媒体网站中部分 JS 渲染或结构不稳定来源当前禁用，不应作为稳定自动采集源。
5. 如果后端不是以 reload 模式启动，修改 Python 文件后必须手动重启 Uvicorn。
6. 文档中的端口以当前 V4 配置为准：前端 `9000`，后端 `5001`。
