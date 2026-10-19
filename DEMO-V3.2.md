# BOM Risk Analyzer v3.2 阶段演示说明

本说明用于演示当前 v3.2/v3.3 MVP 的完整闭环：

> 上传样例 BOM → 执行风险分析 → 查看 v3.2 风险轨道和依据链 → 录入人工涨价/缺货事件 → 重新分析 → 查看风险依据变化。
>
> 粘贴邮件、微信、公众号或官网通知原文 → 系统保存原文 → 自动抽取行情信号 → 高置信度信号生成 MarketEvent → 扫描历史 BOM → 输出受影响项目和物料。

## 1. 当前阶段成果

已完成能力：

- 高容 MLCC 与关键物料品类识别。
- 人工涨价/缺货/交期拉长事件录入。
- 情报可信度评分：单一传闻不会直接强预警，人工确认和多源事实会提高置信度。
- 双轨风险引擎：材料传导轨、需求/供应轨、信息不足状态、缓冲因素。
- BOM 行级 v3.2 字段：
  - `v32_category`
  - `v32_primary_track`
  - `v32_risk_level`
  - `v32_risk_score`
  - `v32_evidence_chain`
  - `v32_evidence_summary`
  - `v32_action_suggestion`
- BOM 分析页前端展示 v3.2 风险列、依据链弹层、人工事件快速录入入口。
- CSV 导出包含 v3.2 字段。
- v3.3 行情情报收件箱：支持粘贴未结构化通知原文，保存原始内容和来源信息，自动抽取品牌、品类、型号、涨幅、交期、缺货信号。
- v3.3 置信度分流：高置信度供应商/邮件/官网通知可自动生成 MarketEvent；微信群或公众号传闻会降权，保留为观察或待复核信号。
- v3.3 历史 BOM 扫描：可信行情事件生成后会扫描历史项目，输出受影响项目数和重点受影响物料，为后续行情历史趋势和预测留下数据结构。

## 2. 一键启动演示服务

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-demo.ps1
```

脚本会打开两个 PowerShell 窗口：

- 后端：`http://127.0.0.1:8001/api/health`
- 前端：`http://127.0.0.1:9000/`

两个服务启动后，先运行浏览器演示烟测：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-browser-demo.ps1
```

该脚本会验证三件事：

- 后端健康检查可达。
- 前端首页可达。
- 前端 `/api` 代理能转发到后端。

如果前端依赖不存在，请先进入 `frontend` 目录执行：

```powershell
npm install
```

## 3. 手动演示步骤

1. 打开前端：

   ```text
   http://127.0.0.1:9000/
   ```

2. 进入 BOM 风险分析页面。

3. 上传样例文件：

   ```text
   demo\sample-bom-v32.csv
   ```

4. 点击分析后，查看表格中的：

   - v3.2 风险等级
   - v3.2 主导轨道
   - v3.2 依据摘要
   - v3.2 处置建议
   - 依据链弹层

5. 在“人工行情事件快速录入”中提交类似事件：

   - 标题：`TDK高容MLCC缺货涨价通知`
   - 品牌：`TDK`
   - 品类：`high_cap_mlcc`
   - 型号：`C3225X5R1A226M250AC`
   - 事件类型：涨价
   - 涨幅：`20`
   - 交期周数：`16`
   - 勾选：已确认缺货、人工确认可信

6. 提交后点击“重新分析当前BOM”。

7. 查看高容 MLCC 行的 v3.2 依据链，确认出现市场事件依据节点和处置建议。

## 4. v3.3 行情情报收件箱演示

1. 先按第 3 节上传 `demo\\sample-bom-v32.csv` 并完成一次 BOM 分析，让系统存在历史项目。

2. 打开左侧菜单“行情收件箱”，或访问：

   ```text
   http://127.0.0.1:9000/#/market-inbox
   ```

3. 粘贴一段未结构化行情通知，例如：

   ```text
   TDK 高容MLCC C3225X5R1A226M250AC 缺货，预计涨价 10%-20%，交期延长至 16 周，即日起执行。
   ```

4. 点击“一键识别并扫描历史 BOM”。系统会展示：

   - 抽取到的品牌、品类、型号、涨幅、交期和置信度。
   - 本次自动生成的 MarketEvent 数量。
   - 已扫描历史项目数、受影响项目数和重点受影响物料。

5. 如果输入类似“群里说 MLCC 可能要涨价，暂时没看到原厂通知”，系统会保存原文和信号，但不会直接生成高置信度 MarketEvent。

## 5. 自动验证命令

在项目根目录执行：

```powershell
py -3.11 -m pytest tests\test_v32_demo_loop.py tests\test_market_notice_parser.py tests\test_market_inbox_api.py -q
```

完整验证：

```powershell
py -3.11 -m pytest tests -q
cd frontend
npm test -- --run
npm run build
```

完整浏览器端到端验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1
```

该脚本会先运行浏览器烟测，再用 Playwright 自动上传 `demo\\sample-bom-v32.csv`，录入 TDK 高容 MLCC 缺货涨价事件，重新分析当前 BOM，并检查 v3.2 风险依据和关联事件是否出现在页面上。v3.3 E2E 会进一步打开“行情收件箱”，粘贴原始通知文本，验证自动抽取、自动确认和历史 BOM 影响摘要。

## 6. 常见问题

### 5.1 localhost 打不开

请优先使用：

```text
http://127.0.0.1:9000/
```

不要拼成 `locallhost`。

### 5.2 前端能打开但上传失败

通常是后端没有启动，或前端代理没有连上后端。检查：

```text
http://127.0.0.1:8001/api/health
http://127.0.0.1:9000/api/health
```

也可以直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-browser-demo.ps1
```

### 5.3 端口被占用

如果 9000 或 8001 被占用，请关闭旧的 PowerShell 演示窗口后重新运行启动脚本。

### 5.4 实时数据源报外网错误

当前演示闭环不依赖公网 API。外网实时数据源失败时，系统仍会基于 BOM、人工事件和 v3.2 规则引擎输出演示结果。
