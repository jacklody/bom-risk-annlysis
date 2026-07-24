# 数据源诊断报告 & 整改方案

> 检查日期：2026-07-06
> 检查范围：后端所有数据源实现、API 配置、数据库状态

---

## 一、现有数据（可直接使用）

| 数据表 | 数量 | 说明 |
|--------|------|------|
| bom_projects | 29个 | BOM项目，含文件名、状态、创建时间 |
| bom_items | 2632条 | 物料明细，含v32_risk_level/v32_primary_track/v32_risk_score |
| market_events | 80条 | 市场行情事件，含品牌/品类/类型/严重度/涨价/交期 |
| preferred_parts | 486条 | 优选库物料 |
| raw_market_notices | 4条 | 原始行情通知 |
| extracted_market_signals | 4条 | 抽取的行情信号 |
| media_source_runs | 66条 | 采集运行记录 |
| prediction_validation_records | 14条 | 预测验证记录 |
| bom_selection_reviews | 325条 | BOM选型评审记录 |

**结论**：数据库里有真实的历史数据，新前端已经通过 `/api` 代理连接到同一后端，数据可以直接用。

---

## 二、分销商 API 数据源（逐一核查）

| 数据源 | 状态 | 实现方式 | API凭证 | 能否拉数据 |
|--------|------|---------|---------|------------|
| **LCSC 立创** | ✅ 可用 | jlcsearch API（免费，无需认证） | 无需 | ✅ 能 |
| **Mouser 贸泽** | ✅ 可用 | Mouser API v1 Search | `f588fe6e-...` 已配置 | ✅ 能 |
| **DigiKey 得捷** | ✅ 可用 | OAuth2 Client Credentials | `my3L8lfG...` 已配置 | ✅ 能 |
| **观芯台** | ⚠️ 部分 | 网页关键词搜索（爬虫） | 无需 | ⚠️ 受限于HTML解析 |
| **Nexar/Octopart** | ❌ 未配置 | GraphQL API | `nexar_enabled=false` | ❌ 不能 |
| **芯查查** | ❌ 未配置 | appId/appSecret | `xinchacha_enabled=false` | ❌ 不能 |
| **云汉芯城** | ❌ 未实现 | 代码中无此源 | — | ❌ 不能 |
| **华秋电子** | ❌ 未实现 | 代码中无此源 | — | ❌ 不能 |

### 可立即启用的操作

1. **Nexar/Octopart**：去 https://octopart.com/api/register 注册免费账号，填 `NEXAR_CLIENT_ID` 和 `NEXAR_CLIENT_SECRET` 到 `.env`，改为 `NEXAR_ENABLED=true`
2. **芯查查**：去 https://www.xinchacha.com/ 申请 appId/appSecret
3. **云汉芯城**：需要对接商务，获取API权限后新增 `yunhan_source.py`
4. **华秋电子**：需要商务对接

---

## 三、公众号/媒体采集（逐一核查）

| 媒体源 | 策略 | 状态 | 能否主动拉取 |
|--------|------|------|-------------|
| **芯师爷** | manual_forward | enabled | ❌ 不能主动拉取 |
| **半导体行业观察** | manual_forward | enabled | ❌ 不能主动拉取 |
| **满天芯** | manual_forward | enabled | ❌ 不能主动拉取 |
| **芯智讯** | manual_forward | enabled | ❌ 不能主动拉取 |
| **国际电子商情** | http_html | disabled | ❌ HTML渲染问题 |
| **电子工程世界** | http_html | disabled | ❌ HTML渲染问题 |
| **立创/JLCSearch** | api_json | enabled | ✅ 能（关键词搜索API） |
| **观芯台** | keyword_search | enabled | ⚠️ 部分可用 |

### 核心问题

**微信公众号没有公开 API**。代码里已经诚实标注了：
```python
# 微信公众号类来源没有公开 API，不在这里伪造成直接抓取；
# 后续通过 Feed、手动转发、浏览器登录态或企业入口接入。
```

所有公众号源都标记为 `manual_forward`，意味着：
- 不会自动抓取
- 用户需要手动复制粘贴公众号文章到"行情情报中心 → 情报录入 → 手动转发"

### 可行方案

| 方案 | 实施难度 | 效果 |
|------|---------|------|
| **方案A：RSS/Feed 桥接** | 中 | 用 RSSHub 等工具把公众号转为 RSS Feed，后端订阅 |
| **方案B：企业微信应用** | 高 | 通过企业微信官方API获取已关注公众号推文 |
| **方案C：手动转发增强** | 低 | 当前已实现，前端优化粘贴体验 |
| **方案D：飞书机器人** | 中 | 用飞书机器人订阅公众号消息推送到群，再通过飞书API读取 |

**建议**：先用方案C（当前已实现）+ 方案D（飞书集成）。你的系统已经集成了飞书SDK，可以通过飞书群消息转发来实现公众号内容的自动流入。

---

## 四、上游材料行情数据源

| 数据源 | 状态 | 说明 |
|--------|------|------|
| **Metals API** | ❌ 未配置 | `METALS_API_KEY=` 为空，需去 https://metals-api.com/ 注册免费key |
| **稀土** | ❌ 未配置 | `RARE_EARTH_AMPLIFIER=1.6` 因子已设，但无数据源 |
| **化工品** | ❌ 未实现 | 环氧树脂、双酚A等无数据源 |
| **硅片/晶圆** | ❌ 未实现 | 无稳定公开价格数据源 |

### 可立即启用的操作

1. **Metals API**（铜/银/铝/锡/镍/金/钯）：去 https://metals-api.com/ 注册，免费套餐每月 500 次请求。填入 `METALS_API_KEY`
2. 化工品和硅片行情暂无免费API，可在前端"上游材料链路"页手动录入行业报告数据

---

## 五、整改优先级

### 🔴 立即执行（不依赖外部配置）

1. ✅ **新前端已连接后端** — `/api` 代理到 8001 端口，数据已通
2. 前端仪表盘使用 `/api/dashboard/summary` 读取真实数据
3. 前端情报中心使用 `/api/events` 读取80条真实事件
4. 上游材料链路页使用品类知识库模板 + 后端统计数据

### 🟡 本周完成（需简单注册）

1. 注册 Metals API → 填入 `.env` → 铜/银/铝价格实时展示
2. 注册 Nexar/Octopart → 增加一个聚合查询源
3. 已有LCSC/Mouser/DigiKey 三个源并行查询，查询覆盖率已较高

### 🟢 两周内完成（需要开发）

1. 飞书群消息 → 公众号文章自动流入
2. 云汉芯城 API 对接（需商务）
3. 原材料追踪页对接 Metals API

---

## 六、关键结论

1. **BOM数据不是模拟的**：29个真实项目、2632条物料、80条行情事件都在数据库里
2. **三个主力API（LCSC/Mouser/DigiKey）已真实在拉数据**：API key都配好了
3. **公众号不能自动拉取**：微信没有公开API，代码已诚实标注。推荐用飞书桥接
4. **上游材料行情（铜/银/铝）**：Metals API 只需注册即可接入
5. **新前端直接可用**：数据通过 `/api` 代理，开箱即用
