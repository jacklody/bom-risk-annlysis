# BOM 选型评审及交付风险预警系统 — Code Wiki

> 本文档为「交期风险排查」项目仓库的结构化代码知识库，覆盖项目整体架构、各版本/模块职责、关键类与函数、依赖关系及运行方式。

---

## 目录

- [一、项目总览](#一项目总览)
- [二、技术栈与依赖](#二技术栈与依赖)
- [三、仓库目录结构](#三仓库目录结构)
- [四、整体架构](#四整体架构)
- [五、后端架构（交期风险排查V4）](#五后端架构交期风险排查v4)
  - [5.1 应用入口与生命周期](#51-应用入口与生命周期)
  - [5.2 配置管理](#52-配置管理)
  - [5.3 数据库与数据模型](#53-数据库与数据模型)
  - [5.4 API 路由层](#54-api-路由层)
  - [5.5 核心服务层](#55-核心服务层)
  - [5.6 上游风险引擎（upstream）](#56-上游风险引擎upstream)
  - [5.7 LLM 服务](#57-llm-服务)
  - [5.8 供应数据源（sources）](#58-供应数据源sources)
  - [5.9 原材料价格源（sources/materials）](#59-原材料价格源sourcesmaterials)
  - [5.10 优选库服务](#510-优选库服务)
  - [5.11 飞书机器人](#511-飞书机器人)
  - [5.12 知识库（knowledge）](#512-知识库knowledge)
- [六、前端架构（交期风险排查V4）](#六前端架构交期风险排查v4)
- [七、V5 Streamlit 轻量版](#七v5-streamlit-轻量版)
- [八、启动与运行方式](#八启动与运行方式)
- [九、测试体系](#九测试体系)
- [十、工程约定与硬约束](#十工程约定与硬约束)
- [十一、production-v1 改造版](#十一production-v1-改造版)
  - [11.1 改造背景与范围](#111-改造背景与范围)
  - [11.2 P0 核心业务逻辑改造](#112-p0-核心业务逻辑改造)
  - [11.3 P1 稳定性基础设施](#113-p1-稳定性基础设施)
  - [11.4 P2 风险闭环](#114-p2-风险闭环)
  - [11.5 P2 API 路由清单](#115-p2-api-路由清单)
  - [11.6 数据库迁移注册表](#116-数据库迁移注册表)
  - [11.7 测试与验证](#117-测试与验证)

---

## 一、项目总览

本项目是一套面向 EMS（电子制造服务）行业的 **BOM 选型评审 + 交付风险预警系统**，核心目标：

1. **新项目选型评审**：在 BOM 导入阶段识别物料生命周期、供应紧张、价格异动等风险，给出选型决策建议。
2. **老项目交付风险把控**：对在产项目的物料交付风险进行实时监控与预警，提供分角色处置建议。

系统融合 **市场行情事件（涨价/缺货/EOL）**、**供应链实时数据（库存/交期/价格）**、**上游原材料价格（有色金属/稀土/化工）**、**政策合规与自然灾害**等多源信号，通过双轨/多因子风险引擎输出行级风险评分与证据链。

### 版本演进

| 版本 | 路径 | 架构 | 定位 |
|------|------|------|------|
| **V4（主力）** | `交期风险排查V4/` | Vue 3 + FastAPI 前后端分离 | 全链路风险预警系统，功能最完整 |
| **V5（轻量 MVP）** | `V5版本/bom-risk-review/` | Streamlit 单体 | 独立轻量化重写，聚焦核心 BOM 评审闭环 |
| **production-v1（改造版）** | `production-v1/` | 基于 V4 后端改造 + Vue 3 前端 | 按专家诊断路线图落地的 P0/P1/P2 改造版，向后兼容 V4 数据库 |

> 本文以 **V4** 为主进行架构说明，V5 在第七节单独说明，**production-v1 改造版**在第十一节单独说明。

---

## 二、技术栈与依赖

### 后端（V4）

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.138+ / Starlette / Uvicorn |
| 数据层 | SQLAlchemy 2.0 + SQLite（默认 `data/market_risk.db`） |
| 数据校验 | Pydantic 2 / pydantic-settings |
| HTTP 客户端 | httpx / requests |
| HTML 解析 | BeautifulSoup4 + lxml |
| 文件处理 | python-multipart / aiofiles / openpyxl |
| 实时通信 | websockets（WebSocket 价格预警推送） |
| LLM | OpenAI SDK 兼容（DeepSeek `deepseek-chat`/`deepseek-reasoner`） |
| 测试 | pytest + pytest-asyncio |

依赖清单：`交期风险排查V4/backend/requirements.txt`

### 前端（V4）

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3.5 |
| 路由 | vue-router 4.5（hash 模式） |
| UI 库 | Element Plus 2.9 + @element-plus/icons-vue |
| HTTP | axios |
| 构建 | Vite 6 |
| 测试 | Vitest + @vue/test-utils + Playwright（E2E） |

依赖清单：`交期风险排查V4/frontend/package.json`

### V5

`streamlit` + `pandas` + `openpyxl` + `plotly` + `pytest`

---

## 三、仓库目录结构

```
交期风险排查/
├── 交期风险排查V4/                     # 主力版本（前后端分离）
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py                # FastAPI 入口 + 生命周期 + 路由注册
│   │   │   ├── config.py              # Pydantic Settings 配置中心
│   │   │   ├── database.py            # SQLAlchemy 引擎 + 迁移
│   │   │   ├── api/                   # 15 个路由模块 + v1 子路由
│   │   │   ├── models/                # 11 个 SQLAlchemy 模型
│   │   │   ├── services/              # 核心业务服务
│   │   │   │   ├── upstream/          # 上游风险引擎（分类/双轨/多因子/证据链）
│   │   │   │   ├── sources/           # 供应数据源（Mouser/LCSC/DigiKey/...）
│   │   │   │   │   └── materials/     # 原材料价格源（SMM/LME/Mysteel/...）
│   │   │   │   ├── llm/               # LLM 服务（推理/解析/建议）
│   │   │   │   ├── preferred_library/ # 优选库服务
│   │   │   │   └── feishu_bot/        # 飞书机器人
│   │   │   └── knowledge/             # 知识库（品牌/品类/产业链/事件模板）
│   │   ├── api/v1/                    # 新版 v1 接口（交付风险/项目评审）
│   │   ├── tests/                     # 后端测试
│   │   └── requirements.txt
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── api/                   # 10+ 个 axios API 客户端模块
│   │   │   ├── views/                 # 13 个页面视图
│   │   │   ├── components/            # 8 个可复用组件
│   │   │   └── router/index.js        # 11 条路由
│   │   ├── vite.config.js
│   │   └── package.json
│   ├── docker-compose.yml / Dockerfile
│   ├── deploy.ps1 / deploy-v3.2-mvp.ps1
│   └── *.md                            # 规划/部署/验收文档
├── V5版本/bom-risk-review/             # Streamlit 轻量版
│   ├── app.py
│   ├── src/                            # 10 个模块
│   └── tests/
├── production-v1/                      # 改造版（P0/P1/P2 落地）
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py                  # FastAPI 入口（注册 7 个 P2 路由组）
│   │   │   ├── database.py              # 迁移注册表（含 P2 列迁移）
│   │   │   ├── observability.py         # P1 结构化日志 + Prometheus
│   │   │   ├── api/                     # P0/P1/P2 路由模块
│   │   │   │   ├── risk_matches.py      # P0 事件-BOM 命中查询
│   │   │   │   ├── risk_lifecycle.py    # P2 风险闭环（19 条路由）
│   │   │   │   └── health.py            # P1 增强健康检查 + /metrics
│   │   │   ├── models/
│   │   │   │   ├── risk_match.py        # P0+P2 模型（命中/动作/替代料/枚举）
│   │   │   │   └── source_health.py     # P1 数据源健康记录
│   │   │   └── services/
│   │   │       ├── part_matcher.py      # P0 L1-L3 MPN 匹配
│   │   │       ├── bom_matcher.py       # P0 5 级匹配重构
│   │   │       ├── circuit_breaker.py   # P1 熔断器
│   │   │       ├── source_health_service.py  # P1 数据源健康监控
│   │   │       ├── risk_lifecycle_service.py # P2 闭环服务
│   │   │       └── alternative_part_service.py # P2 替代料验证
│   │   └── tests/test_production_v1.py  # 71 项测试（P0+P1+P2）
│   └── frontend/                       # Vue 3 前端（同 V4）
├── start-bom-system.ps1               # 一键启动脚本
├── 一键启动-BOM交期风险系统.bat
├── start-logs/                         # 启动日志
└── *.md / *.xlsx / *.zip              # 规划、测试报告、部署包
```

---

## 四、整体架构

### 4.1 V4 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                       浏览器（前端 SPA）                       │
│              Vue 3 + Element Plus + vue-router               │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTP /api  (Vite 代理 9000→8000)
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI 应用层 (main.py)                   │
│   生命周期：init_db → SupplyDataService → MaterialPriceService │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  API 路由层   │    │   模型层     │    │   知识库     │
│  (app/api)   │    │ (app/models) │    │(app/knowledge)│
└──────┬───────┘    └──────┬───────┘    └─────────────┘
       │                   │
       ▼                   │
┌──────────────────────────────────────┐
│            核心服务层 (services)        │
│  BOM 解析/匹配/暴露度 | 供应风险评估     │
│  事件采集/情报智能体 | 仪表盘/通知       │
│  交付风险/项目评审 | 原材料价格追踪      │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│       上游风险引擎 (upstream)           │
│  品类分类 → 双轨引擎 → 多因子引擎       │
│  → 证据链 → 情报评分 → 自动提级          │
└──────┬───────────────────────────────┘
       │
       ├──────────────┬─────────────┐
       ▼              ▼             ▼
┌────────────┐ ┌───────────┐ ┌───────────┐
│ LLM 服务    │ │ 供应数据源  │ │ 材料价格源  │
│(DeepSeek)  │ │(Mouser等) │ │(SMM/LME等)│
└────────────┘ └───────────┘ └───────────┘
       │              │             │
       └──────────────┴─────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  SQLite 数据库 │
            └───────────────┘
```

### 4.2 核心数据流

1. **BOM 导入**：Excel/CSV → `bom_parser` 解析 → 品牌归一化 → 入库 `bom_items`
2. **风险分析**：`bom_matcher` 精确匹配+品类波及 → `risk_context_builder` 构建上下文 → `dual_track`/`multi_factor` 引擎评分 → `evidence_chain_builder` 证据链 → 落库风险结果
3. **供应刷新**：`SupplyDataService` 并行调用多源 API → `AggregatedResult` 聚合 → 更新 `bom_items` 实时字段 + 写 `SourceHealthRecord`
4. **情报采集**：`event_collector`/`media_crawler` 抓取 → `nlp_extractor` 关键词+LLM 双路提取 → `intelligence_scoring` 评分 → `MarketEvent` 入库 → 扫描历史 BOM 影响

---

## 五、后端架构（交期风险排查V4）

### 5.1 应用入口与生命周期

文件：[backend/app/main.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/main.py)

- **FastAPI 应用**：`title="BOM风险分析器"`, `version="4.1.0"`
- **CORS 中间件**：基于 `settings.cors_allowed_origins` 配置
- **`lifespan` 异步上下文管理器**（启动/关闭钩子）：
  - 启动：`init_db()` → 初始化 `SupplyDataService` → 初始化 `MaterialPriceService`（预取基础金属价格）
  - 关闭：优雅关闭 `SupplyDataService` 与 `MaterialPriceService` 连接
- **路由注册**：15 个路由模块 + 2 个 v1 子路由
- **静态前端托管**：若 `frontend/dist` 存在，挂载 `/assets` 并提供 SPA fallback（非 `/api` 请求返回 `index.html`）
- **健康检查**：`GET /api/health` → `{"status":"ok","version":"4.1.0"}`

### 5.2 配置管理

文件：[backend/app/config.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/config.py)

`Settings(BaseSettings)` 通过 `.env` 文件加载，主要配置分组：

| 分组 | 关键字段 |
|------|---------|
| 基础 | `database_url`、`data_dir`、`cors_allowed_origins` |
| LLM | `llm_provider`、`llm_api_key`、`llm_base_url`、`llm_model`、`llm_temperature`(0.3)、`llm_timeout`(30s) |
| 风险引擎 | `min_confidence_threshold`(0.6)、`cross_validation_sources`(2) |
| 供应源 API | `mouser_*`、`lcsc_*`、`digikey_*`、`guanxintai_*`、`nexar_*`、`xinchacha_*` |
| 查询 | `api_query_timeout`(10s)、`api_batch_concurrency`(5)、`cache_ttl_seconds`(86400) |
| 原材料 | `metals_api_key`、`material_fetch_interval_h`(12)、`material_warning_pct`(5)、`material_alert_pct`(10)、`material_critical_pct`(20)、`rare_earth_amplifier`(1.6) |
| P1 数据源 | `smm_*`、`mysteel_*`、`lme_*` |
| 飞书 | `feishu_app_id`、`feishu_app_secret`、`feishu_verification_token` |
| 邮件通知 | `notification_email_*` |
| GDACS 灾害 | `gdacs_enabled`、`gdacs_*`（4h 采集，Orange/Red 级别） |
| USGS 地震 | `usgs_enabled`、`usgs_*`（2h 采集，M≥5.0，直击 200km/间接 500km） |

### 5.3 数据库与数据模型

文件：[backend/app/database.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/database.py)

- **引擎**：SQLite（`check_same_thread=False`），`SessionLocal` 会话工厂
- **`get_db()`**：FastAPI 依赖注入，请求级 session（自动关闭）
- **`init_db()`**：建表 + `_ensure_migration_tracking()` 轻量迁移
- **迁移注册表** `_MIGRATION_KEYS`：5 个迁移项（bom_item_supply_v2v3、extracted_market_signals_review、dashboard_notification_provider、bom_project_orange、material_prices_v3_4），通过 `app_config` 表追踪执行状态

#### 数据模型（`app/models/`）

| 模型文件 | 表名 | 职责 |
|---------|------|------|
| [bom.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/models/bom.py) | `bom_projects`、`bom_items` | BOM 项目与物料行（含风险等级枚举 RED/ORANGE/YELLOW/GREEN/GRAY、行情风险字段、供应链 v2/v3 实时字段） |
| [event.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/models/event.py) | `market_events`、`raw_market_notices`、`extracted_market_signals`、`prediction_validation_records` | 市场事件、原始通知、抽取信号、预测验证记录 |
| [preferred.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/models/preferred.py) | `preferred_parts` | 优选库标准物料（品牌/型号/封装/优选等级/成本） |
| [material_price.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/models/material_price.py) | `material_prices` | 原材料价格快照（material_key + 时间戳索引） |
| [watch.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/models/watch.py) | `watch_commands` | 情报监控指令（自然语言→解析→生成事件） |
| exposure.py | `exposure_*` | BOM 暴露度评估结果 |
| risk_assessment.py | `risk_assessments` | 风险评估记录 |
| chain_node.py / chain_edge.py | `chain_*` | 产业链图谱节点与边 |
| media_source.py | `media_sources` | 媒体数据源配置 |
| dashboard_notification.py | `dashboard_notification_records` | 通知发送记录（含 provider/retry/delivered_at） |

### 5.4 API 路由层

入口在 [main.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/main.py#L82-L102) 注册。所有路由文件位于 `app/api/`。

#### BOM 与项目

| 路由文件 | 前缀 | 关键端点 |
|---------|------|---------|
| [bom_upload.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/bom_upload.py) | `/api/bom` | `POST /upload`（单文件解析）、`POST /upload-batch`（批量）、`GET /lists`（批次列表） |
| [bom_project.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/bom_project.py) | `/api/bom` | 项目 CRUD、`GET /{id}/risks`、`POST /{id}/rescan-all`、事件影响查询 |
| [risk_analysis.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/risk_analysis.py) | `/api/risk` | `POST /analyze/{upload_id}`、`POST /analyze-all`、`GET /report/{id}`、HTML/XLSX 导出 |

#### 事件与情报

| 路由文件 | 前缀 | 关键端点 |
|---------|------|---------|
| [events.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/events.py) | `/api/events` | 事件列表/详情、`POST /collect`、`POST /manual`、`PATCH /{id}/status`、`GET /{id}/impact`、媒体源采集 |
| [intel_watch.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/intel_watch.py) | `/api/intel` | `POST /watch`（创建关注指令）、`GET /watch/history`、`GET /watch/{cmd_id}` |
| [market_inbox.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/market_inbox.py) | `/api/market-inbox` | `POST /submit`、`GET /`、`POST /review/{signalId}`、`GET /review-queue` |
| [market_intel.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/market_intel.py) | `/api/market-intel` | `/seed`、`/match`、`/brand-risk`、`/category-risk`、`/events` |
| [market_trends.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/market_trends.py) | `/api/market-trends` | `/summary`、`/timeline`、`/validation`、`/actions` |

#### 供应与材料

| 路由文件 | 前缀 | 关键端点 |
|---------|------|---------|
| [supply.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/supply.py) | `/api/supply` | `GET /query`、`POST /items/{id}/refresh`、`POST /projects/{id}/refresh`、`GET /sources/status`、`GET /sources/health`、`POST /sources/{name}/toggle` |
| [material_alerts.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/material_alerts.py) | `/api/material-alerts` | `GET /`、`/trends/{materialKey}`、`/summary`、`/cache-stats` |
| [material_ws.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/material_ws.py) | WebSocket `/api/material-alerts/ws` | 实时价格预警推送 |

#### 仪表盘、通知与链路

| 路由文件 | 前缀 | 关键端点 |
|---------|------|---------|
| [dashboard.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/dashboard.py) | `/api/dashboard` | `/summary`、`/dual-track`、`/notification` |
| [risk_chain.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/risk_chain.py) | `/api/risk-chain` | `/dashboard`、`/material-chain`、`/by-material`、`/by-project` |
| [feishu_webhook.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/feishu_webhook.py) | `/api/feishu` | `POST /webhook`、`GET /status` |
| [preferred_library.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/api/preferred_library.py) | `/api/preferred-library` | `POST /import`、`GET /summary`、`GET /parts`、`POST /review/{projectId}` |

#### v1 新版接口

| 路由文件 | 前缀 | 关键端点 |
|---------|------|---------|
| [api/v1/delivery_risk.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/api/v1/delivery_risk.py) | `/api/v1/delivery-risk` | `/overview`、`/materials`、`/timeline`、`/recommendations`、`/ack` |
| [api/v1/project_review.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/api/v1/project_review.py) | `/api/v1/project-review` | `/summary`、`/bom-items`、`/approve`、`/export` |

### 5.5 核心服务层

服务位于 `app/services/`，按职能分组：

#### BOM 处理链

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [bom_parser.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/bom_parser.py) | `parse_bom_file()`、`normalize_item()`、`smart_normalize_brand()` | BOM 文件解析、行归一化、品牌名称归一化 |
| [bom_matcher.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/bom_matcher.py) | `BOMMatcher` | Phase1 精确匹配 + Phase2 品类波及 + 生命周期调整 |
| [bom_exposure_engine.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/bom_exposure_engine.py) | `BomExposureEngine` | 四因子暴露度（用量 30% + 项目 30% + 关键度 20% + 集中度 20%） |

#### 供应风险评估

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [supply_data.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/supply_data.py) | `SupplyDataService`、`AggregatedResult` | 多源并行查询 + 聚合；refresh 端点写 `SourceHealthRecord`，query 端点不写；输出含 `source_details`（每源状态/库存/价格/错误原因） |
| [supply_risk.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/supply_risk.py) | `evaluate_supply_risk()` | 8 维度供应风险评估 |

#### 报告与仪表盘

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [risk_report_export.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/risk_report_export.py) | — | HTML/XLSX 风险报告渲染 |
| [dashboard_summary.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/dashboard_summary.py) | `build_dashboard_summary()` | 仪表盘汇总数据构建 |
| [dashboard_notification.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/dashboard_notification.py) | — | 通知预览/发送/历史（邮件/飞书/企业微信/人工） |

#### 交付风险与项目评审

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [delivery_risk_service.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/delivery_risk_service.py) | `DeliveryRiskService` | 老项目交付风险聚合服务 |
| [project_review_service.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/project_review_service.py) | `ProjectReviewService` | 新项目选型评审（命中匹配 + 历史使用 + 交期联动 + 选型决策） |

#### 事件采集与情报

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [event_collector.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/event_collector.py) | `EventCollector` | 多源事件采集，含 `_save_event` 内部接口 |
| [intel_agent.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/intel_agent.py) | `IntelAgent` | 关注指令智能体（自然语言→解析→匹配→生成事件） |
| [market_intel_engine.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/market_intel_engine.py) | `MarketIntelEngine` | 行情情报匹配引擎 |
| [incremental_scanner.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/incremental_scanner.py) | `IncrementalScanner` | 增量扫描 |
| [media_crawler.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/media_crawler.py) | `IndustryMediaCrawler` | 行业媒体爬虫 |
| [nlp_extractor.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/nlp_extractor.py) | `NLPExtractor` | 关键词快速匹配 + LLM 深度提取双路径 |

#### 材料价格与追踪

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [material_price_service.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/material_price_service.py) | `MaterialPriceService` | 多源原材料价格编排服务 |
| [material_tracker.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/material_tracker.py) | `MaterialTracker` | 30/90 日基线 + 三档阈值（5%/10%/20%）预警 |

#### 自动提级与推理

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [auto_escalation_engine.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/auto_escalation_engine.py) | `AutoEscalationEngine` | R1-R7 提级规则（只升不降） |
| [llm_client.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/llm_client.py) | `LLMClient` | OpenAI 兼容 LLM 封装 |
| [chain_query_service.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/chain_query_service.py) | `ChainQueryService` | 产业链图 BFS 遍历查询 |

### 5.6 上游风险引擎（upstream）

位于 `app/services/upstream/`，是系统风险识别的核心。

#### 品类分类

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [category_classifier.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/category_classifier.py) | `classify_component_category()`、`ComponentCategoryResult` | 4 步分类：MLCC 专用 → 规则匹配 → LLM 兜底 → 未知；21 品类元数据 + 规则；LLM 缓存（500 条上限） |
| [mlcc_classifier.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/mlcc_classifier.py) | `classify_mlcc()`、`MlccClassificationResult` | 排除非 MLCC → 提取容值/介质/封装 → 高容判定（≥10μF） |

> **重要约束**：功率模块规则必须在 MOSFET 规则之前（防止 Infineon IGBT 模块误判）。

#### 风险上下文与证据链

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [risk_context_builder.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/risk_context_builder.py) | `build_v32_context()`、`set_material_tracker()` | 主流程：分类→市场事实→body 信号→材料信号→buffer→双轨引擎→证据链；风险域分 `selection` 与 `market` 两类独立标签；异步事件循环三级 fallback |
| [evidence_chain_builder.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/evidence_chain_builder.py) | `build_evidence_chain()`、`EvidenceChainResult` | 17 品类上游材料模板；证据链含 `market_event`/`dual_track`/`supply_snapshot`/`information_status` 合并节点 |

#### 双轨风险引擎（Phase 1）

文件：[dual_track_risk_engine.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/dual_track_risk_engine.py)

- **`DualTrackRiskResult`**：category / risk_level / total_score / primary_track / track_scores / reason / evidence
- **`evaluate_dual_track_risk()`** 主流程：
  1. 生命周期直接升级（EOL→red 95 / NRND→orange 80）
  2. 材料轨评分 `_material_score()`：按 `MATERIAL_SIGNAL_WEIGHTS` 累加
  3. 供需轨评分 `_demand_supply_score()`：stock_down / price_up / shortage / lead_time
  4. 缓冲因子 `_buffer_score()`：安全库存（30d/90d）+ 多源 + supplier_count
  5. 加权：`material×model.material + demand×model.demand_supply - buffer`
  6. IC 类材料传导弱约束（单一硅片涨价 ≤34 分）
  7. 等级映射：≥80 red / ≥60 orange / ≥35 yellow / >0 green / 0 gray

#### 多因子风险引擎（Phase 2，T2-001）

文件：[multi_factor_risk_engine.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/multi_factor_risk_engine.py)

七因子加权评分：

| 因子 | 函数 | 评分要点 |
|------|------|---------|
| 市场趋势 | `calculate_market_trend_score()` | 材料信号加权 + 7d/30d/90d 价格变化率 |
| 供应紧张 | `calculate_supply_tension_score()` | 库存/交期/缺货/涨价 + 库存天数 + 交期变化率 |
| 政策合规 | `calculate_policy_compliance_score()` | 8 种政策信号（实体清单=100/BIS=90/USTR=90/出口管制=80…） |
| 灾害区域 | `calculate_disaster_zone_score()` | 10 种灾害信号，供应商受灾 ×1.2 |
| BOM 暴露度 | `calculate_bom_exposure_score()` | 用量 0-60 + 项目数 0-30 + 关键物料 10 |
| 替代难度 | `calculate_substitution_difficulty_score()` | 无替代=100/单替代+30 + 认证周期 + Pin 兼容度 |
| 置信度 | `calculate_confidence_score()` | S/A/B/C 级基础分 + 交叉验证加成 → 调整系数 0.8-1.2 |

`evaluate_multi_factor_risk()` 主流程：生命周期升级 → 七因子计算 → 加权求和 → 置信度调整 → 关键因子地板机制 → 数据充分性 → 等级映射 → Phase1 兼容双轨分数。

#### 情报评分与事件处理

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| [intelligence_scoring.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/intelligence_scoring.py) | `score_intelligence_event()` | 置信度 = 来源 35% + 字段完整度 35% + 交叉验证 20% + 事实加成；"单一公众号谣言"检测（强制 observe） |
| [manual_event_service.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/manual_event_service.py) | `build_market_event_from_manual_payload()`、`extract_market_facts_from_events()` | 人工事件构造 + 市场事实提取 |
| [market_inbox_service.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/market_inbox_service.py) | `MarketInboxService` | 通知入库→解析→信号保存→提级判断→事件创建→历史 BOM 扫描 |
| [market_notice_parser.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/market_notice_parser.py) | `parse_market_notice()`、`ParsedMarketSignal` | 80+ 品牌关键词 + 品类 + MPN 正则 + 涨价 + 交期 + 缺货 + 置信度评分 |

#### 规则配置中心

文件：[propagation_rules.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/upstream/propagation_rules.py)

| 配置项 | 说明 |
|--------|------|
| `CATEGORY_MODEL_WEIGHTS` | 22 品类材料/供需权重（PCB=0.75/0.25 材料驱动，MCU=0.15/0.85 供需驱动） |
| `MATERIAL_SIGNAL_WEIGHTS` | 24 种材料信号权重 |
| `DEMAND_SUPPLY_SIGNAL_WEIGHTS` | 5 种供需信号权重 |
| `MULTI_FACTOR_WEIGHTS` | 七因子全局权重（总和=1.0） |
| `CONFIDENCE_COEFFICIENTS` | S=1.2 / A=1.1 / B=1.0 / C=0.8 |
| `PRICE_SURGE_THRESHOLDS` | 12 种关键材料 7 日涨幅阈值 |
| `ESCALATION_RULES_CONFIG` | R1-R7 提级规则（S 级政策→red / PCN·EOL→orange / 价格暴涨提级 / GDACS Red 提级 / 库存危机 / 单一来源 / 数据缺失） |

### 5.7 LLM 服务

位于 `app/services/llm/`，基于 DeepSeek（OpenAI 兼容）。

| 文件 | 类 | 职责 |
|------|-----|------|
| [base.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/llm/base.py) | `LLMServiceBase`、`LLMCallResult` | 统一入口 `run(context)`：检查可用性→构造 prompt→调用 LLM→JSON 解析（4 级容错）→验证→返回；默认 temp=0.3 / max_tokens=2000 / timeout=30s |
| [chain_reasoning.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/llm/chain_reasoning.py) | `ChainReasoningContext` | 事件链路推理（8 种事件类型时间窗口）；降级为规则推理 |
| [document_parser.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/llm/document_parser.py) | — | 文档解析（7 个涨价正则 + 4 类日期 + 30+ 物料/厂商关键词）；降级为正则提取（置信度 0.3） |
| [recommendation_generator.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/llm/recommendation_generator.py) | — | 处置建议生成（8 组国产替代映射：STM32→GD32 等）；降级为模板生成（按红/橙/黄/绿映射参数） |

### 5.8 供应数据源（sources）

位于 `app/services/sources/`，统一输出 `SourceResult` 格式（hit/not_found/error 三态）。

#### 基础接口

文件：[base.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/base.py)

- **`SourceResult`** 数据类（20+ 字段）：source / mpn_queried / mpn_matched / manufacturer / total_stock / supplier_count / lead_time_days / unit_price / price_breaks / moq / currency / lifecycle_status / category / product_url / datasheet_url / match_status / error_reason / raw_summary 等
- **`BaseSource`** ABC：`source_name` 属性 + `query_by_mpn(mpn)` + `health_check()` + `clean_mpn(mpn)`（去除 `-TR`/`-CT`/`-REEL`/`-TUBE` 等包装后缀）

#### 分销商数据源

| 文件 | 类 | 认证 | 提供数据 |
|------|-----|------|---------|
| [mouser.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/mouser.py) | `MouserSource` | API Key | 库存 + 工厂交期(天) + 阶梯价 + 生命周期（30 次/分钟限流） |
| [lcsc.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/lcsc.py) | `LCSCSource` | 免费无认证 | 库存 + 价格（0.55s 限流，无交期/生命周期） |
| [digikey.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/digikey.py) | `DigiKeySource` | OAuth2 | 库存 + 价格 + 工厂交期(周→天) + 生命周期 |
| [guanxintai.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/guanxintai.py) | `GuanxintaiSource` | 免登录 | HTML 解析聚合多渠道价格库存（3s 限流） |
| [octopart_source.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/octopart_source.py) | `OctopartSource` | Nexar GraphQL OAuth2 | 库存 + 价格 + 生命周期（100 次/月配额，24h TTL 缓存，<20% 时降级） |

#### 灾害数据源

| 文件 | 类 | 说明 |
|------|-----|------|
| [gdacs_source.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/gdacs_source.py) | `GdacsSource` | GDACS API，4h 采集，Orange/Red 级别，5 种事件类型，转 `MarketEvent` 格式 |
| [usgs_earthquake_source.py](file:///d:/1项目清单/交期风险排查/交期风险排查V4/backend/app/services/sources/usgs_earthquake_source.py) | `UsgsEarthquakeSource` | USGS API，2h 采集，M≥5.0；内置 24 个全球半导体工厂坐标 + 6 个优先区域；Haversine 距离判定直击/间接影响 |

### 5.9 原材料价格源（sources/materials）

位于 `app/services/sources/materials/`，统一抽象 `MaterialPriceSourceBase`。

| 文件 | 提供材料 |
|------|---------|
| `metals_api_source.py` | 基础有色金属（铜/铝/锌/铅/锡/镍） |
| `smm_source.py` | SMM 上海有色网（付费 API） |
| `mysteel_source.py` | Mysteel 我的钢铁网（付费 API） |
| `lme_source.py` | LME 伦敦金属交易所（网页解析） |
| `rare_earth_source.py` | 稀土元素 |
| `small_metal_source.py` | 小金属 |
| `chemical_source.py` | 化工非金属 |

### 5.10 优选库服务

位于 `app/services/preferred_library/`。

| 文件 | 职责 |
|------|------|
| `excel_importer.py` | 优选库 Excel 导入（解析多 Sheet、字段映射） |
| `normalizer.py` | 品牌/型号归一化 |
| `review_service.py` | BOM 与优选库差异对比评审 |
| `history_indexer.py` | 优选库历史索引 |

### 5.11 飞书机器人

位于 `app/services/feishu_bot/`。

| 文件 | 职责 |
|------|------|
| `bot.py` | 飞书机器人主入口 |
| `feishu_client.py` | 飞书 OpenAPI 客户端封装 |
| `message_handler.py` | 消息处理（事件推送/指令交互） |

### 5.12 知识库（knowledge）

位于 `app/knowledge/`，提供静态参考数据：

| 文件 | 内容 |
|------|------|
| `brand_category_map.py` | 品牌→品类映射 |
| `category_tree.py` | 品类树结构 |
| `category_material_mapping.py` | 品类→上游材料映射 |
| `material_mapping.py` | 材料代码与域映射（`get_material_keys_for_domain()`） |
| `part_number_prefix.py` | 型号前缀识别规则 |
| `industry_chain.py` | 产业链结构定义 |
| `risk_chain_library.py` | 风险链路模板库 |
| `event_templates.py` | 事件模板 |
| `market_intel.py` | 市场情报种子数据 |
| `media_sources.py` | 媒体数据源配置 |

---

## 六、前端架构（交期风险排查V4）

技术栈：Vue 3 + Element Plus + vue-router 4（hash 模式）+ Vite 6 + axios。

### 6.1 路由

文件：[frontend/src/router/index.js](file:///d:/1项目清单/交期风险排查/交期风险排查V4/frontend/src/router/index.js)

共 11 条路由，全部懒加载：

| 路径 | 视图 | 页面用途 |
|------|------|---------|
| `/` | `RiskChainDashboard.vue` | **首页**：风险链路驾驶舱（三栏：信号流 / 产业链图谱 / BOM 影响） |
| `/analyze` | `BomAnalyze.vue` | BOM 风险分析（上传→匹配→分析→完成） |
| `/dashboard` | `RiskDashboard.vue` | 风险仪表盘 + 通知管理 |
| `/projects` | `BomProjects.vue` | BOM 项目列表 |
| `/projects/:id` | `BomProjectDetail.vue` | 项目详情 + 报告导出 |
| `/events` | `MarketEvents.vue` | 市场事件（筛选/采集/追踪） |
| `/market-trends` | `MarketTrends.vue` | 趋势预警 + 预测验证 |
| `/market-inbox` | `MarketInbox.vue` | 行情情报收件箱（粘贴原文→自动识别） |
| `/preferred-library` | `PreferredLibrary.vue` | 优选库差异对比 |
| `/watch` | `IntelWatch.vue` | 情报监控（自然语言关注指令） |
| `/materials` | `MaterialWatch.vue` | 原材料价格追踪 |

> 注：`DeliveryRisk.vue` 与 `ProjectReview.vue` 存在但未接入路由。

### 6.2 API 客户端

基础客户端 [client.js](file:///d:/1项目清单/交期风险排查/交期风险排查V4/frontend/src/api/client.js)：axios，`baseURL: '/api'`，`timeout: 30000`。

| 模块 | 调用端点 |
|------|---------|
| `bom.js` | BOM 上传/分析/项目/报告导出 |
| `dashboard.js` | 仪表盘汇总/通知预览/发送/历史/通道 |
| `events.js` | 事件列表/采集/转发/手动/状态/影响 |
| `intelWatch.js` | 关注指令创建/历史/详情 |
| `marketInbox.js` | 通知提交/审核/队列 |
| `marketTrends.js` | 趋势汇总/时间线/验证/行动 |
| `materialAlerts.js` | 材料预警/趋势/汇总/缓存 |
| `preferredLibrary.js` | 优选库导入/对比/评审 |
| `supply.js` | 供应查询/刷新/源状态 |
| `riskChain.js` + `riskChainService.js` | 风险链路（当前 Mock 数据，预留后端接口） |

### 6.3 可复用组件

| 组件 | 职责 |
|------|------|
| `BomUploader.vue` | BOM 文件上传（单/批量，拖拽，xlsx/xls/csv） |
| `BomImpactPanel.vue` | 驾驶舱右侧 BOM 影响面板（角色筛选：采购/研发/项目管理） |
| `DocumentUpload.vue` | 文档上传（txt/md/pdf，10MB） |
| `MaterialPrice.vue` | 数据源健康状态监控卡片 |
| `ProgressSteps.vue` | 四步进度条（上传→匹配→分析→完成） |
| `RiskDetailTable.vue` | 风险明细表格（等级筛选/供应刷新） |
| `RiskSignalFlow.vue` | 驾驶舱左侧风险信号流 |
| `RiskSummary.vue` | 风险汇总四格卡片 |

### 6.4 Vite 配置

- 开发端口：9000
- 代理：`/api` → `http://127.0.0.1:5001`（注：与启动脚本 8000 端口存在差异，启动脚本定位的是 `BOM-Risk-Analyzer-patch` 子项目）

---

## 七、V5 Streamlit 轻量版

路径：`V5版本/bom-risk-review/`

### 7.1 定位

独立的轻量化 MVP 重写，采用 **Streamlit + Python + SQLite** 单体架构，聚焦核心 BOM 评审闭环。明确排除 ERP 对接、审批流、实时通知、多层 BOM、AI 预测等高级功能。

### 7.2 模块职责

| 模块 | 职责 |
|------|------|
| [app.py](file:///d:/1项目清单/交期风险排查/V5版本/bom-risk-review/app.py) | Streamlit 主应用，6 页侧边栏导航（首页/BOM导入/供应数据导入/风险评分/历史记录/规则配置） |
| `src/models.py` | 6 张表 DDL + 4 条默认规则 |
| `src/database.py` | SQLite 连接 + 建表初始化（`data/app.db`） |
| `src/importers.py` | BOM/供应数据 Excel 导入（校验、去重、审计） |
| `src/risk_engine.py` | `evaluate_risks()` 核心风险引擎（停产→高、单一来源→高、交期/价格/库存阈值判定） |
| `src/scoring_service.py` | 评分服务层（加载 BOM+供应+规则→评分→保存→审计） |
| `src/dashboard_service.py` | 仪表盘/历史查询 |
| `src/rule_config.py` | 规则阈值配置 |
| `src/audit_log.py` | 操作日志写入 |
| `src/report_exporter.py` | 三 Sheet Excel 报告导出（摘要/明细/不推荐物料） |
| `src/ui_components.py` | 各页面 Streamlit 渲染 |
| `src/sample_data.py` | 样例数据生成 |

### 7.3 启动

```powershell
streamlit run app.py
```

---

## 八、启动与运行方式

### 8.1 一键启动（推荐）

双击根目录 `一键启动-BOM交期风险系统.bat`，或运行：

```powershell
powershell -ExecutionPolicy Bypass -File "d:\1项目清单\交期风险排查\start-bom-system.ps1"
```

脚本执行 8 步：环境检查（python/node/npm）→ 释放端口（8000/9000）→ 安装后端依赖 → 安装前端依赖 → 启动后端（8000）→ 启动前端（9000）→ 打开浏览器 → 完成。日志写入 `start-logs/`。

> 注意：启动脚本优先定位 `BOM-Risk-Analyzer-patch` 子项目。

### 8.2 手动启动（V4）

**后端**：
```powershell
cd 交期风险排查V4/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**前端**：
```powershell
cd 交期风险排查V4/frontend
npm install
npm run dev -- --port 9000
```

访问 `http://127.0.0.1:9000/#/`，API 文档 `http://127.0.0.1:8000/docs`。

### 8.3 生产构建

```powershell
cd 交期风险排查V4/frontend
npm run build    # 产物到 frontend/dist/
```

后端 `main.py` 会自动托管 `frontend/dist`（SPA fallback）。

### 8.4 Docker 部署

```powershell
cd 交期风险排查V4
docker build -t bom-risk-analyzer .
docker-compose up -d
```

- 容器：`bom-risk-analyzer`，端口 `8000:8000`
- 数据卷：`./backend/data:/app/backend/data`
- 健康检查：`curl -f http://localhost:8000/api/health`

### 8.5 Nginx 反向代理（可选）

- `/api/`、`/docs` → 后端 8000
- `/` → 前端 `dist/`

### 8.6 环境配置

复制 `backend/.env.example` 为 `.env`，按需填写：LLM API Key、各供应源 API Key、原材料 API Key、飞书应用凭证、邮件 SMTP 等。

---

## 九、测试体系

### 9.1 后端测试（V4）

```powershell
cd 交期风险排查V4/backend
py -3.11 -m pytest tests -q -W error
```

测试位于 `backend/tests/`，覆盖：BOM 匹配、品类分类、双轨/多因子引擎、证据链、情报评分、人工事件、市场收件箱、供应 API、优选库等。当前基线约 **460+ passed**。

### 9.2 前端测试（V4）

```powershell
cd 交期风险排查V4/frontend
npm run test          # Vitest 单元测试
npm run test:e2e      # Playwright E2E
```

### 9.3 V5 测试

```powershell
cd V5版本/bom-risk-review
py -3.11 -m pytest tests -q
```

当前 49 项测试通过。

---

## 十、工程约定与硬约束

以下为项目积累的工程约定（来源：项目记忆），开发时必须遵守：

### 硬约束

1. **后端测试**必须通过 `python -m pytest -q -W error`（0 errors, 0 warnings）
2. **前端构建**必须通过 `npm run build`（0 warnings）
3. **供应源容错**：供应源必须实现失败降级，单个源错误不得阻塞 BOM 分析
4. **健康记录写入**：`refresh_item_supply` 和 `refresh_project_supply` 端点必须写 `SourceHealthRecord`；`/query` 端点不写

### 工程约定

- 风险域在 `risk_context_builder.py` 中分为 `selection` 和 `market` 两类独立标签
- 证据链在 `evidence_chain_builder.py` 中包含 `market_event`/`dual_track`/`supply_snapshot`/`information_status` 合并节点
- 资源客户端（httpx.Client、数据源、服务）必须用 context manager 关闭
- 供应源输出统一 `SourceResult` 格式（hit/not_found/error 三态）
- `online_evidence.source_details` 必须包含每源状态、库存、价格、错误原因

### 经验教训

- `category_classifier.py` 中**功率模块规则必须在 MOSFET 规则之前**，防止 Infineon IGBT 模块误判
- 测试中并发数据库访问会导致对象删除干扰，需串行验证以保证结果可靠
- LLM 仅用于**非结构化文本解析**和**建议文案起草**，不参与核心风险评分或物料链推理
- `koa-connect` 包装器会引发 ctx 泄漏，必须用原生 Koa 重写而非包装 Express 中间件
- **SQLite ALTER TABLE 迁移**：已建表库要新增列，必须用独立 migration key（不能复用建表时的 key），否则已记录 `migration:xxx=1` 会导致列被跳过
- **SQLAlchemy `default=`** 仅在 flush 时生效，直接构造对象访问属性会得到 None；测试中需显式赋值

---

## 十一、production-v1 改造版

### 11.1 改造背景与范围

`production-v1/` 是基于 V4 后端的**生产化改造版**，按 [EXPERT-DIAGNOSIS.md](file:///d:/1项目清单/交期风险排查/EXPERT-DIAGNOSIS.md) 第八节"落地路线图"落地三个阶段：

| 阶段 | 目标 | 是否完成 | 说明 |
|---|---|---|---|
| **P0** | 把"准"做出来 | ✅ | 核心业务逻辑改造（纯 Python） |
| **P1** | 把"稳"做出来 | ✅ 部分 | 熔断器/健康监控/可观测性已完成；PostgreSQL/Redis/Celery/JWT 需外部环境，待后续 |
| **P2** | 把"闭环"做出来 | ✅ | 风险生命周期+动作+替代料+复盘（纯 Python） |

**兼容性**：与 V4 共用 SQLite 文件，通过 SQLAlchemy ALTER TABLE 增量迁移，旧库无需重建。

### 11.2 P0 核心业务逻辑改造

#### 5 级 MPN 匹配（`part_matcher.py` + `bom_matcher.py`）

| 级别 | 枚举值 | 置信度 | 触发条件 |
|---|---|---|---|
| L1 | `exact_mpn` | 0.95 | MPN 完全相等（大小写不敏感） |
| L2 | `normalized_mpn` | 0.90 | 清洗包装后缀（`-TR`/`/TUBE`/`-REEL7`）后相等 |
| L3 | `series` | 0.75 | 系列前缀匹配（显式 `series` 字段或从事件文本提取） |
| L4 | `brand_category` | 0.55 | 同品牌+同品类 |
| L5 | `category_spread` | 0.30 | 同品类扩散（最低精度） |

**规则**：`PartMatcher` 按级别顺序短路返回；`BOMMatcher._match_level_rank` 提供级别排序用于去重保留最高精度命中。

#### 事实/推断信号分流（`risk_analysis.py`）

- `FACTUAL_EVENT_TYPES`：`PRICE_INCREASE` / `EOL` / `SHORTAGE` / `LEAD_TIME` — 直接事件
- `INFERRED_EVENT_TYPES`：`MATERIAL_PRICE` / `DISASTER` / `POLICY` — 推断信号
- `SignalOrigin` 枚举：`factual` / `inferred` / `mixed`
- **推断分数封顶**：`_capped_inference_score(80) = 35`，`_capped_inference_level("red") = "yellow"` — 未被事实确认的推断信号最高只能到 YELLOW

#### 持久化表（`risk_match.py`）

- `risk_event_bom_matches`：事件→BOM 行命中映射，含 `match_level`/`confidence`/`signal_origin`/风险快照
- `risk_change_history`：风险等级变更历史，含 `escalation/degradation/resolved/manual` 类型

#### 双轨引擎废弃

`dual_track_risk_engine` 模块保留但仅打印废弃警告，**多因子引擎**（`multi_factor_risk_engine`）是唯一评分引擎。

### 11.3 P1 稳定性基础设施

#### P1-A 可观测性（已完成）

| 模块 | 文件 | 能力 |
|---|---|---|
| **熔断器** | `services/circuit_breaker.py` | CLOSED/OPEN/HALF_OPEN 三态机，`failure_threshold`/`recovery_timeout` 可配 |
| **数据源健康监控** | `services/source_health_service.py` + `models/source_health.py` | `SourceHealthRecord` 持久化每源状态；`refresh_item_supply`/`refresh_project_supply` 写入；`/query` 不写入 |
| **结构化日志** | `observability.py` | `setup_logging()` 统一 JSON 格式，注入 request_id |
| **Prometheus 指标** | `observability.py` + `api/health.py` | `/metrics` 端点暴露；失败时优雅降级（不阻塞业务） |
| **增强健康检查** | `api/health.py` | `/api/health` 返回 DB/数据源/熔断器综合状态 |
| **SourceResult 统一格式** | `services/sources/base.py` | `hit`/`not_found`/`error` 三态 + `query_with_retry` 方法 |

#### P1-B 外部服务（已完成）

外部依赖已全部就绪：

| 服务 | 安装方式 | 连接配置 |
|---|---|---|
| **PostgreSQL 16** | Windows 官方安装包 | `postgresql+psycopg2://bom_user:bom_pass_2026@localhost:5432/bom_risk` |
| **Redis（Memurai）** | Windows 原生 Redis 兼容版 | `redis://localhost:6379/0` |

#### P1-C PostgreSQL 适配（已完成）

| 文件 | 改造内容 |
|---|---|
| `app/config.py` | 新增 `database_url` 支持 PostgreSQL URL |
| `app/database.py` | 按 URL 前缀判断是否传 `check_same_thread`（SQLite 才传）；`_ensure_migration_tracking` 按方言选择 `INSERT OR REPLACE`（SQLite）或 `ON CONFLICT`（PG） |
| `.env` | `DATABASE_URL` 已切到 PostgreSQL |
| `alembic.ini` + `alembic/env.py` | Alembic 迁移框架，`target_metadata = Base.metadata`，`sqlalchemy.url` 从 settings 读取 |
| `alembic/versions/0001_baseline.py` | Baseline 迁移，不建表（现有表由 `Base.metadata.create_all()` + `_MIGRATION_KEYS` 维护） |

**兼容性**：SQLite 仍可用于测试，PostgreSQL 用于生产。

#### P1-D Redis 缓存层（已完成）

| 文件 | 能力 |
|---|---|
| `app/services/redis_cache.py` | `RedisCacheService` 单例：惰性连接、失败降级（不可用时返回 None 不阻塞业务）、JSON 序列化、TTL 支持、批量 mget/mset |
| `app/services/supply_data.py` | `query_one` 集成缓存：查询前查缓存，命中直接返回；查询后写入缓存；TTL 用 `settings.cache_ttl_seconds`（默认 86400） |
| `app/main.py` | lifespan 初始化 `get_cache_service()` + 退出 `shutdown_cache_service()` |

**缓存 Key 格式**：`supply:query:{mpn}:{brand}` 或 `supply:query:{mpn}`（无品牌时）

#### P1-E Celery 后台任务队列（已完成）

| 文件 | 能力 |
|---|---|
| `app/services/celery_app.py` | Celery 应用 + `refresh_supply_data_task` + `refresh_project_supply_task` 两个任务 |
| `app/services/scheduled_tasks.py` | Celery Beat 定时配置（每小时派发活跃项目刷新） |
| `app/api/supply.py` | `refresh_item_supply` 端点新增 `async_refresh=true` 参数，异步派发到 Celery 队列 |

**启动方式**：
```powershell
celery -A app.services.celery_app.celery_app worker --loglevel=info
celery -A app.services.celery_app.celery_app beat --loglevel=info
```

#### P1-F JWT 认证鉴权（已完成）

| 文件 | 能力 |
|---|---|
| `app/api/auth.py` | `/api/auth/login` 登录、`/api/auth/me` 用户信息、`/api/auth/verify` 令牌验证 |
| `app/api/auth.py` | `create_access_token` / `verify_token` / `get_current_user` 依赖项 |

**默认账户**（本地用户表，后续可扩展为数据库用户）：
- 管理员：`admin` / `bom_admin_2026`
- 分析师：`analyst` / `bom_analyst_2026`

### 11.4 P2 风险闭环

#### 风险生命周期状态机（7 态）

`ReviewStatus` 枚举扩展为 7 态：

```
pending(新发现) → under_review(审核中) → confirmed(已确认) → action_taken(已行动) → monitoring(监控中) → resolved(已解除)
                                                    ↓
                                              ignored(忽略)
```

- `VALID_TRANSITIONS` 字典约束合法流转（`risk_lifecycle_service.py`）
- 非法流转被 `transition_status` 拒绝
- `resolved` 状态可通过 `pending`/`under_review` 重新打开（事件复发）

#### 来源可信度分级（`SourceConfidence`）

6 级分级 + 评分字典 `SOURCE_CONFIDENCE_SCORE`：

| 枚举值 | 评分 | 典型来源 |
|---|---|---|
| `official_notice` | 1.00 | 原厂涨价函/EOL 公告 |
| `authorized_distributor` | 0.85 | 授权代理通知 |
| `distributor` | 0.70 | LCSC/Mouser/DigiKey |
| `media` | 0.45 | 行业媒体 |
| `social_media` | 0.30 | 公众号/社交 |
| `manual_unconfirmed` | 0.20 | 人工录入未确认 |

#### 数据新鲜度机制

`DATA_FRESHNESS_HOURS` 三级阈值：

| 状态 | 阈值 | 含义 |
|---|---|---|
| `fresh` | 24h | 新鲜 |
| `stale` | 72h | 可用但陈旧，自动标记 `is_stale=True` |
| `expired` | 168h | 过期，需重新采集 |

#### 风险解除（5 种 `ResolutionReason`）

- `stock_recovered` — 库存恢复（自动）
- `event_expired` — 事件过期（自动）
- `alternative_imported` — 替代料导入
- `manual` — 人工解除
- `auto_downgrade` — 自动降级

#### 处理动作追踪（`RiskAction`）

| 字段 | 用途 |
|---|---|
| `action_type` | `stock_up`/`alternative`/`price_accept`/`delay`/`split_order`/`redesign`/`custom` |
| `result` | `pending`/`effective`/`ineffective`/`partial` |
| `action_detail` | JSON 详情（备货数量、替代料 MPN 等） |

#### 替代料验证（`AlternativePart`）

双维度验证 + 综合状态：

| 维度 | 字段 | 状态枚举 |
|---|---|---|
| 参数兼容性 | `compatibility_status` | `unverified`/`compatible`/`incompatible` |
| 供应可用性 | `supply_status` | `unverified`/`available`/`unavailable` |
| 综合 | `overall_status` | `unverified`/`verified`/`rejected` |

`AlternativePartService.verify_supply()` 异步调用 `SupplyDataService` 校验库存与交期。

#### 复盘统计（`get_review_statistics`）

- **命中率** = `confirmed / (confirmed + ignored)`
- **行动有效率** = `effective / total_with_result`

### 11.5 P2 API 路由清单

`/api/risk-lifecycle` 前缀下 19 条路由，分 7 组：

| 组 | 方法 | 路径 | 用途 |
|---|---|---|---|
| 生命周期 | POST | `/matches/{id}/transition` | 状态流转 |
| 生命周期 | GET | `/matches/{id}/transitions` | 查询合法后继状态 |
| 生命周期 | GET | `/lifecycle/statuses` | 列出全部状态 |
| 风险解除 | POST | `/matches/{id}/resolve` | 解除风险 |
| 风险解除 | GET | `/resolution-reasons` | 列出解除原因 |
| 处理动作 | POST | `/actions` | 记录处理动作 |
| 处理动作 | PUT | `/actions/{id}/result` | 更新动作结果 |
| 处理动作 | GET | `/actions/item/{id}` | 按物料查动作 |
| 处理动作 | GET | `/action-types` | 列出动作类型 |
| 替代料 | POST | `/alternatives` | 新增替代料 |
| 替代料 | POST | `/alternatives/{id}/verify-compatibility` | 验证参数兼容性 |
| 替代料 | POST | `/alternatives/{id}/verify-supply` | 验证供应可用性 |
| 替代料 | GET | `/alternatives/item/{id}` | 按物料查替代料 |
| 替代料 | GET | `/alternatives/statistics` | 替代料统计 |
| 数据新鲜度 | POST | `/freshness/check` | 触发新鲜度检查 |
| 数据新鲜度 | GET | `/freshness/summary` | 新鲜度汇总 |
| 来源可信度 | GET | `/source-confidence/levels` | 列出分级 |
| 来源可信度 | GET | `/source-confidence/classify` | 分类指定来源 |
| 复盘统计 | GET | `/review/statistics` | 命中率+有效率 |

### 11.6 数据库迁移注册表

`database.py` 中 `_MIGRATION_KEYS` 字典按 key 顺序幂等执行，已完成项写入 `app_config` 表：

| Key | 作用 |
|---|---|
| `risk_match_tables_v_prod_1` | 创建 `risk_event_bom_matches` + `risk_change_history` |
| `risk_match_p2_columns_v_p2` | **独立 key** — 为已建表补齐 P2 新增 7 列 |
| `risk_lifecycle_tables_v_p2` | 创建 `risk_actions` + `alternative_parts` |
| `source_health_tables_v_p1` | 创建 `source_health_records` |

> ⚠️ **教训**：P2 列迁移最初和建表共用 key，导致已建表库的 ALTER TABLE 被跳过。**已建表加列必须用独立 key**。

### 11.7 测试与验证

```powershell
cd production-v1/backend
# 全量测试（4 个测试文件）
python -m pytest tests/test_production_v1.py tests/test_redis_cache.py tests/test_celery_app.py tests/test_auth.py -q -W error
```

**当前基线**：95 项通过，0 warnings（符合 `-W error` 硬约束，PostgreSQL + Redis 全部就绪）。

测试覆盖：

#### `test_production_v1.py`（71 项）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| `TestPartMatcher` | 14 | L1-L3 匹配 + 工具函数 |
| `TestEnums` | 4 | 枚举值 + 置信度排序 |
| `TestSignalOriginClassification` | 4 | 事实/推断分流 + 封顶 |
| `TestRiskMatchModels` | 4 | 模型表名 + to_dict |
| `TestEventBomMatchService` | 2 | 服务初始化 + 空库统计 |
| `TestBOMMatcherIntegration` | 2 | PartMatcher 集成 + 级别排序 |
| `TestCircuitBreaker` | 7 | 熔断器三态机 |
| `TestSourceHealthService` | 4 | 健康记录 + 降级 |
| `TestObservability` | 3 | 日志 + 指标降级 |
| `TestSourceHealthModel` | 2 | 模型表名 + to_dict |
| `TestSourceResultFields` | 2 | 字段 + 重试方法 |
| `TestReviewStatusLifecycle` | 5 | 7 态 + 合法/非法流转 |
| `TestSourceConfidence` | 5 | 6 级分级 + 评分 + 分类器 |
| `TestDataFreshness` | 2 | 阈值 + 空库 |
| `TestRiskActionModel` | 3 | 表名 + to_dict + 枚举 |
| `TestAlternativePartModel` | 3 | 表名 + to_dict + 枚举 |
| `TestRiskLifecycleService` | 2 | 流转查询 + 空库统计 |
| `TestAlternativePartService` | 2 | 初始化 + 空库统计 |
| `TestResolutionReason` | 1 | 枚举值 |

#### `test_redis_cache.py`（8 项，P1 新增）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| - | 8 | 初始化 + set/get + delete + mget/mset + TTL + JSON + 单例 + 降级 |

#### `test_celery_app.py`（5 项，P1 新增）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| - | 5 | 配置 + 任务注册 + 名称 + 序列化器 + 超时 |

#### `test_auth.py`（11 项，P1 新增）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| - | 11 | 登录成功/失败 + token 生成/验证/过期/无效 + /me + /verify |

#### `test_user_rbac.py`（16 项，P3 新增）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| - | 16 | 密码哈希 + 权限矩阵 + User 模型 + UserService + deps 依赖项 + 登录端到端 |

#### `test_organization.py`（14 项，P3 新增）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| - | 14 | 组织模型 + CRUD + 用户/项目分配 + 数据隔离 + API |

#### `test_erp_adapter.py`（24 项，P3 新增）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| - | 24 | 数据类 + Mock 适配器 + 注册表 + JWT API + Webhook API |

#### `test_sdk.py`（8 项，P3 新增）

| 测试类 | 数量 | 覆盖点 |
|---|---|---|
| - | 8 | SDK 初始化 + 登录 + /me + 统计 + ERP + 错误处理 + 组织 + 版本 |

**端点冒烟测试**：7 个 GET 端点全部返回 200。

### 11.8 P3 产品化阶段

#### ① 用户权限与角色（RBAC）

| 文件 | 能力 |
|---|---|
| `app/models/user.py` | User 模型（username/password_hash/role/organization_id）+ Role 枚举（admin/analyst/procurement/viewer）+ ROLE_PERMISSIONS 权限矩阵 |
| `app/services/user_service.py` | UserService（认证/创建/列表/改角色/启停）+ bcrypt 密码哈希 + ensure_default_users() |
| `app/api/auth.py` | /login + /me + /register + /users + /users/{id}/role（后三个仅 admin） |
| `app/api/deps.py` | require_role(roles) / require_permission(perm) 工厂依赖项 + require_admin / require_analyst 预定义 |

#### ② 多项目/多组织隔离

| 文件 | 能力 |
|---|---|
| `app/models/organization.py` | Organization 模型（id/name/code/description） |
| `app/services/organization_service.py` | 组织 CRUD + get_visible_projects（按组织过滤）+ can_access_project |
| `app/api/organizations.py` | 5 个 admin only 端点（创建/列表/详情/分配用户/分配项目） |

#### ③ ERP/PLM 对接适配层

| 文件 | 能力 |
|---|---|
| `app/services/erp/base.py` | IErpAdapter 抽象接口 + 5 个数据类（ErpBom/ErpInventory/ErpPurchaseOrder/ErpRiskAlert） |
| `app/services/erp/mock_adapter.py` | MockErpAdapter（开发测试用） |
| `app/services/erp/registry.py` | 适配器注册表 + 单例管理（register_adapter / get_erp_adapter） |
| `app/api/erp.py` | 8 个端点（health/bom/inventory/purchase-orders/risk-alert/alternative + 2 webhook） |

**对接新 ERP**：只需实现 `IErpAdapter` 子类，调用 `register_adapter("sap_rest", SapRestAdapter)` 注册。

#### ④ API 文档与 SDK

| 文件 | 能力 |
|---|---|
| `app/models/api_schemas.py` | 统一 ErrorResponse / SuccessResponse / PaginatedResponse |
| `app/api/docs.py` | GET /api/docs/error-codes + GET /api/docs/version |
| `sdk/bom_risk_client.py` | Python SDK 客户端（7 模块：Auth/RiskLifecycle/Alternatives/Erp/Health/Organizations/Docs） |
| `sdk/README.md` | SDK 使用文档（中文） |

#### ⑤ 部署脚本与备份恢复

| 文件 | 能力 |
|---|---|
| `deploy/scripts/start-services.ps1` | 启动 PG/Redis/uvicorn/Celery |
| `deploy/scripts/stop-services.ps1` | 停止所有服务 |
| `deploy/scripts/status-services.ps1` | 彩色状态表 |
| `deploy/scripts/backup-database.ps1` | pg_dump 备份 + 30 天保留 |
| `deploy/scripts/restore-database.ps1` | 数据恢复 + 确认提示 |
| `deploy/scripts/setup-scheduled-tasks.ps1` | Windows 计划任务（每日 02:00 备份） |
| `deploy/config/prometheus.yml` | Prometheus 抓取配置 |
| `deploy/config/alert_rules.yml` | 11 条告警规则 |

---

*文档生成时间：2026-07-23 · 基于代码库当前状态（含 production-v1 P0/P1/P2/P3 全部改造完成，157 项测试通过）*
