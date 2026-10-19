# 方案 B B1-B7 阶段交付说明

## 交付范围

方案 B 已完成 B1 风险仪表盘、HTML 报告导出，B2 Excel 报告导出，B3 风险变化摘要，B4 通知预览与手动通知准备，B5 通知执行记录、历史查询和重复通知抑制，B6 通知渠道状态、安全发送适配和测试通道能力，以及 B7 SMTP 邮件通知通道接入，覆盖后端聚合接口、报告导出接口、通知准备接口、通知历史接口、通知通道状态接口、SMTP 发送适配、前端仪表盘页面、导航入口、项目详情导出入口与对应测试。

本阶段遵循既定边界：只复用现有 BOM、供应、行情事件和趋势行动数据，不改变风险评分规则，不新增外部授权数据源，不引入服务端 PDF 渲染依赖。

## 已完成能力

### 风险仪表盘

新增 `/dashboard` 前端页面，用于集中展示：

- 项目总数、高风险项目数、红色物料数、30 天活跃事件数、待处理行动数
- 项目风险分布
- 品类风险排行
- 近期活跃事件
- 趋势行动摘要
- 供应源健康状态
- 风险变化摘要和通知准备信息
- 仪表盘统计口径说明

后端新增 `/api/dashboard/summary`，聚合现有项目、物料、行情事件、趋势行动和供应源注册信息，前端可通过仪表盘直接跳转到项目详情或事件追踪页面。

### 风险变化摘要与通知准备

`/api/dashboard/summary` 已新增 `risk_changes` 输出，面向后续定时扫描与通知任务提供可消费的摘要输入，包含：

- 新增红色风险物料数、黄色风险物料数、变化项目数
- 近 7 天活跃事件数量与事件跳转上下文
- 可通知状态 `notification_ready`
- 可直接用于消息正文的 `notification_summary`
- 变化项目列表与项目详情跳转入口

前端“风险仪表盘”新增“风险变化摘要”卡片，集中展示红黄风险增量、变化项目、近 7 天事件、通知摘要，以及变化项目/新增事件的追踪入口。

B3 准备定时扫描/通知所需的数据边界和展示入口。

### 通知预览与手动通知准备

新增两个 dashboard 通知接口，复用 `risk_changes` 生成可发送内容，但不直接调用外部消息通道：

- `GET /api/dashboard/notification/preview`：返回手动通知预览，包含 `ready`、`subject`、`body`、风险变化明细和跳转动作
- `POST /api/dashboard/notification/dispatch`：生成一次手动通知准备结果，返回 `prepared`/`skipped` 状态、预览内容和人工发送提示

前端“风险变化摘要”卡片新增“通知预览”和“准备手动通知”入口。当前阶段将通知内容准备好并提示人工发送，避免在未配置正式通知渠道前误发外部消息。

### 通知执行记录、历史查询与重复抑制

新增通知执行记录模型 `dashboard_notification_records`，用于保存每次通知准备结果，包含渠道、状态、通知键、标题、正文、是否外发、消息提示和创建时间。

- `POST /api/dashboard/notification/dispatch` 支持 `idempotency_key`，当相同通知键已存在历史记录时返回 `suppressed`，避免重复准备同一批通知。
- `GET /api/dashboard/notification/history` 返回最近通知执行记录，用于审计和前端展示。
- 前端“风险变化摘要”卡片新增“通知执行历史”，展示最近通知标题、通知键、状态和是否外发。

当前 B5 仍不直接接入外部短信、邮件或飞书发送通道，只把正式通知落地所需的持久化、重复抑制和审计边界补齐。

### 通知渠道配置与安全发送适配

B6 新增通知通道状态查询和安全发送适配边界：

- `GET /api/dashboard/notification/channels` 返回人工通知、测试通道以及邮件、飞书、企业微信等真实通道占位状态。
- `POST /api/dashboard/notification/dispatch` 支持 `mock` 测试通道，可验证发送成功、执行记录落库和前端历史刷新。
- 未配置的真实通道会返回 `blocked`，不会标记为已发送，也不会触达外部系统。
- 通知执行记录新增 provider、收件人摘要、失败原因、重试次数、最近尝试时间和实际发送时间等审计字段。
- 前端“风险变化摘要”新增通知通道状态展示和“发送测试通知”入口。

B6 仍遵循安全默认策略：真实邮件、飞书、企业微信通道在未配置前只展示状态和阻断原因，不执行外发。

### SMTP 邮件通知通道

B7 将邮件作为首个真实通知通道接入：

- 后端新增 SMTP 邮件通知配置项，支持通过 `.env` 或环境变量启用。
- `GET /api/dashboard/notification/channels` 可根据 SMTP 配置返回邮件通道是否可用。
- `POST /api/dashboard/notification/dispatch` 支持 `channel=email`，配置完整且存在可通知风险变化时发送真实邮件。
- SMTP 发送成功记录为 `sent`，失败记录为 `failed` 并保存失败原因。
- SMTP 未配置或未启用时继续返回 `blocked`，不会外发。
- 前端在邮件通道可用时展示“发送邮件通知”入口。
- SMTP 密码不会进入 API 响应、通知历史或前端页面。

### HTML 风险报告导出

新增 `/api/risk/report/{project_id}/export.html`，基于现有项目风险报告数据生成静态 HTML 报告，包含：

- 项目基本信息
- 风险摘要
- 高风险物料
- 供应证据
- 行情证据
- 采购建议
- 浏览器打印另存为 PDF 的提示

HTML 输出会转义动态文本，不包含密钥、环境变量或内部调试信息。

### Excel 风险报告导出

新增 `/api/risk/report/{project_id}/export.xlsx`，基于现有项目风险报告数据生成 Excel 工作簿，包含：

- `项目摘要`：项目基本信息、物料总数、红黄绿灰风险统计、风险率和生成时间
- `高风险物料`：物料型号、品牌、品类、风险等级、风险分数、库存、供应商数、交期、单价、供应摘要和采购建议
- `行情证据`：物料型号、事件标题、来源、事件类型、严重度、置信度、价格影响和交期影响

Excel 导出使用正式的 `.xlsx` MIME 类型和 UTF-8 文件名响应头，便于浏览器直接下载。

### 项目详情导出入口

在项目详情页新增两个报告入口：

- “打开HTML报告”：打开对应项目的 HTML 风险报告
- “导出Excel报告”：下载对应项目的 Excel 风险报告

## 主要变更文件

后端：

- `backend/app/api/dashboard.py`
- `backend/app/models/dashboard_notification.py`
- `backend/app/services/dashboard_summary.py`
- `backend/app/services/dashboard_notification.py`
- `backend/app/config.py`
- `backend/app/services/risk_report_export.py`
- `backend/app/api/risk_analysis.py`
- `backend/app/main.py`
- `tests/test_dashboard_api.py`
- `tests/test_risk_report_export.py`

前端：

- `frontend/src/api/dashboard.js`
- `frontend/src/api/bom.js`
- `frontend/src/views/RiskDashboard.vue`
- `frontend/src/router/index.js`
- `frontend/src/App.vue`
- `frontend/src/views/BomProjectDetail.vue`
- `frontend/src/views/__tests__/RiskDashboard.test.js`
- `frontend/src/views/__tests__/BomProjectDetail.test.js`

## 验证结果

已完成以下验证：

```powershell
$env:PYTHONPATH='backend'; py -3.11 -m pytest tests/test_risk_report_export.py tests/test_dashboard_api.py -q
```

结果：`15 passed in 18.86s`

```powershell
npm run test -- --run src/views/__tests__/BomProjectDetail.test.js src/views/__tests__/RiskDashboard.test.js
```

结果：`2 passed files / 13 passed tests`

```powershell
npm run build
```

结果：构建成功。Vite 输出了现有大 chunk 提醒和第三方库 PURE 注释提醒，不影响构建完成。

此前 B1 阶段也完成过前端全量 Vitest 验证：`12 passed files / 45 passed tests`。

## 使用方式

- 打开前端后进入“风险仪表盘”导航项，查看方案 B 聚合视图。
- 在项目详情页点击“打开HTML报告”，打开该项目的风险报告。
- 在项目详情页点击“导出Excel报告”，下载该项目的 Excel 风险报告。
- HTML 报告可通过浏览器打印功能另存为 PDF。
- 在“风险变化摘要”中查看通知预览，点击“准备手动通知”生成待人工发送的通知内容。
- 在“通知通道”中查看人工、测试、邮件、飞书、企业微信等通道状态。
- 点击“发送测试通知”验证通知发送流程，该测试通道不会触达外部系统。
- 配置并启用 SMTP 后，点击“发送邮件通知”向配置的收件人发送真实邮件通知。
- 在“通知执行历史”中查看最近通知准备记录、通知键、状态、是否外发和失败原因。

## SMTP 配置示例

```env
notification_email_enabled=true
notification_email_smtp_host=smtp.example.com
notification_email_smtp_port=587
notification_email_username=notice@example.com
notification_email_password=app-password
notification_email_sender=notice@example.com
notification_email_recipients=buyer@example.com,pm@example.com
notification_email_use_tls=true
notification_email_timeout=10
```

## 下一步建议

B1-B7 完成后，可继续进入 B8：围绕真实通知通道补充发送重试、失败告警、权限控制和更细粒度的通知策略。