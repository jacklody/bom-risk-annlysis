# v3.2 Playwright E2E Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 v3.2 BOM 风险演示增加完整浏览器端到端验收，自动验证上传样例 BOM、录入人工涨价缺货事件、重新分析并看到 v3.2 风险依据变化。

**Architecture:** 在现有 Vue/Vite 前端中增加 Playwright E2E 测试与稳定选择器，不改变业务 API 和页面主流程。E2E 使用真实浏览器访问 `http://127.0.0.1:9000/`，通过 Vite `/api` 代理调用后端 `http://127.0.0.1:8001`。使用独立 PowerShell 包装脚本先做 HTTP 烟测，再进入前端目录运行 Playwright。

**Tech Stack:** Vue 3、Vite、Element Plus、FastAPI、PowerShell、Playwright、Vitest、pytest。

## Global Constraints

- 不依赖公网 API，验收只使用本地后端、前端和 `demo/sample-bom-v32.csv`。
- 不改变生产 API 路径，前端仍通过 `/api` 相对路径访问后端。
- 演示后端固定为 `http://127.0.0.1:8001`。
- 演示前端固定为 `http://127.0.0.1:9000`。
- 只覆盖 v3.2 demo 主链路，不扩展为全系统 UI 自动化。
- 优先使用 `data-testid` 稳定选择器，不依赖脆弱 CSS 层级或像素校验。

---

## File Structure

- Modify: `frontend/package.json`
  - 增加 Playwright devDependency。
  - 增加 `test:e2e` 与 `test:e2e:headed` 脚本。
- Create: `frontend/playwright.config.js`
  - 配置 baseURL、浏览器、超时、trace/screenshot。
  - 不自动启动 webServer，避免重复启动用户已有演示窗口。
- Create: `frontend/e2e/v32-demo-loop.spec.js`
  - 执行完整浏览器端到端验收。
- Modify: `frontend/src/components/BomUploader.vue`
  - 为上传控件、项目名输入、开始分析按钮增加 `data-testid`。
- Modify: `frontend/src/components/ManualEventQuickAdd.vue`
  - 为品牌、品类、型号、事件类型、交期、来源、复选框增加 `data-testid`。
- Modify: `frontend/src/components/RiskDetailTable.vue`
  - 为表格、v3.2 风险按钮、关联事件按钮增加 `data-testid`。
- Modify: `frontend/src/views/BomAnalyze.vue`
  - 为分析完成区、重新分析按钮、导出按钮增加 `data-testid`。
- Create: `scripts/e2e-browser-demo.ps1`
  - 检查前后端链路后运行 `npm run test:e2e`。
- Modify: `scripts/start-demo.ps1`
  - 提示 E2E 验收命令。
- Modify: `DEMO-V3.2.md`
  - 增加完整浏览器自动验收说明。
- Modify: `deploy-v3.2-mvp.ps1`
  - 复制 Playwright 配置、E2E 测试、脚本和新增前端文件。
- Modify: `GIT-HANDOFF.md`、`README-V3.2-MVP.md`
  - 更新移交说明和验证命令。

---

## Task 1: 增加稳定 UI 选择器

**Files:**
- Modify: `frontend/src/components/BomUploader.vue`
- Modify: `frontend/src/components/ManualEventQuickAdd.vue`
- Modify: `frontend/src/components/RiskDetailTable.vue`
- Modify: `frontend/src/views/BomAnalyze.vue`

**Interfaces:**
- Consumes: 现有 Vue 组件 props、emit 和 API 调用。
- Produces: Playwright 可使用的 `data-testid`：
  - `bom-file-input`
  - `project-name-input`
  - `start-analyze-button`
  - `analysis-done-panel`
  - `manual-event-title`
  - `manual-event-brand`
  - `manual-event-category`
  - `manual-event-mpn`
  - `manual-event-type`
  - `manual-event-increase`
  - `manual-event-lead-time`
  - `manual-event-source`
  - `manual-event-shortage-confirmed`
  - `manual-event-confirmed-by-user`
  - `manual-event-submit`
  - `reanalyze-current-bom`
  - `risk-detail-table`
  - `v32-risk-button`
  - `matched-events-button`

- [ ] **Step 1: 给 BomUploader 增加选择器**

在 `frontend/src/components/BomUploader.vue` 中，将单文件 `el-upload` 改为：

```vue
<el-upload
  ref="uploadRef"
  data-testid="bom-file-input"
  drag
  :auto-upload="false"
  :on-change="handleChange"
  :limit="1"
  accept=".xlsx,.xls,.csv"
  :disabled="disabled"
>
```

将项目名称输入改为：

```vue
<el-input
  v-model="projectName"
  data-testid="project-name-input"
  placeholder="项目名称（选填，默认用文件名）"
  style="max-width: 300px"
  size="default"
/>
```

将开始分析按钮改为：

```vue
<el-button
  data-testid="start-analyze-button"
  type="primary"
  @click="startAnalyze"
  :loading="disabled"
  size="default"
>
  <el-icon><VideoPlay /></el-icon> 开始分析
</el-button>
```

- [ ] **Step 2: 给 ManualEventQuickAdd 增加选择器**

在 `frontend/src/components/ManualEventQuickAdd.vue` 中，为输入框补齐：

```vue
<input v-model="form.brand" data-testid="manual-event-brand" class="native-input" placeholder="TDK / Murata" />
<input v-model="form.category" data-testid="manual-event-category" class="native-input" placeholder="high_cap_mlcc" />
<input v-model="form.mpn" data-testid="manual-event-mpn" class="native-input" placeholder="可选" />
<select v-model="form.event_type" data-testid="manual-event-type" class="native-input">
```

将交期输入改为：

```vue
<input
  v-model.number="form.lead_time_weeks"
  data-testid="manual-event-lead-time"
  class="native-input"
  type="number"
  min="0"
  placeholder="16"
/>
```

将来源输入改为：

```vue
<input
  v-model="form.source_url"
  data-testid="manual-event-source"
  class="native-input wide"
  placeholder="供应商通知、官网链接或文件路径"
/>
```

将两个复选框改为：

```vue
<input v-model="form.shortage_confirmed" data-testid="manual-event-shortage-confirmed" type="checkbox" />
<input v-model="form.confirmed_by_user" data-testid="manual-event-confirmed-by-user" type="checkbox" />
```

- [ ] **Step 3: 给结果区和重新分析按钮增加选择器**

在 `frontend/src/views/BomAnalyze.vue` 中，将单文件结果容器改为：

```vue
<div v-if="phase === 'done' && result && !batchMode" data-testid="analysis-done-panel">
```

将重新分析按钮改为：

```vue
<el-button
  data-testid="reanalyze-current-bom"
  size="small"
  type="warning"
  :loading="reanalyzing"
  @click="reanalyzeCurrentUpload"
>
  重新分析当前BOM
</el-button>
```

将导出按钮改为：

```vue
<el-button data-testid="export-csv-button" @click="exportTable" size="small">
  <el-icon><Download /></el-icon> 导出 CSV
</el-button>
```

- [ ] **Step 4: 给风险表格增加选择器**

在 `frontend/src/components/RiskDetailTable.vue` 中，将表格改为：

```vue
<el-table
  data-testid="risk-detail-table"
  :data="filteredItems"
  stripe
  max-height="500"
  style="margin-top: 8px"
  row-key="row_number"
>
```

将 v3.2 风险按钮改为：

```vue
<el-button size="small" link type="primary" class="v32-risk-btn" data-testid="v32-risk-button">
```

将关联事件按钮改为：

```vue
<el-button size="small" link type="primary" data-testid="matched-events-button">
  {{ row.matched_events.length }} 条
</el-button>
```

- [ ] **Step 5: 运行前端组件测试**

Run:

```powershell
cd "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer\frontend"
npm test -- --run
```

Expected:

```text
Test Files  2 passed (2)
Tests  3 passed (3)
```

- [ ] **Step 6: 提交选择器改动**

```powershell
git add frontend/src/components/BomUploader.vue frontend/src/components/ManualEventQuickAdd.vue frontend/src/components/RiskDetailTable.vue frontend/src/views/BomAnalyze.vue
git commit -m "test: add stable selectors for v3.2 browser e2e"
```

---

## Task 2: 增加 Playwright 配置和 E2E 测试

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/playwright.config.js`
- Create: `frontend/e2e/v32-demo-loop.spec.js`

**Interfaces:**
- Consumes: Task 1 中的 `data-testid`。
- Produces: `npm run test:e2e` 命令。

- [ ] **Step 1: 修改 package.json**

在 `frontend/package.json` 中增加脚本：

```json
"test:e2e": "playwright test",
"test:e2e:headed": "playwright test --headed"
```

在 `devDependencies` 中增加：

```json
"@playwright/test": "^1.45.0"
```

- [ ] **Step 2: 安装依赖**

Run:

```powershell
cd "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer\frontend"
npm install
npx playwright install chromium
```

Expected:

```text
added ... packages
```

Playwright 浏览器安装命令退出码为 0。

- [ ] **Step 3: 创建 Playwright 配置**

Create `frontend/playwright.config.js`:

```js
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: {
    timeout: 15_000
  },
  use: {
    baseURL: 'http://127.0.0.1:9000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ]
})
```

- [ ] **Step 4: 创建 E2E 测试**

Create `frontend/e2e/v32-demo-loop.spec.js`:

```js
import { expect, test } from '@playwright/test'
import path from 'node:path'

const sampleBomPath = path.resolve('../demo/sample-bom-v32.csv')

test('v3.2 demo loop uploads BOM, adds manual event, reanalyzes and shows evidence', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'BOM 风险分析' })).toBeVisible()

  const fileInput = page.locator('[data-testid="bom-file-input"] input[type="file"]')
  await fileInput.setInputFiles(sampleBomPath)

  await page.getByTestId('project-name-input').locator('input').fill('v3.2 E2E 验收样例')
  await page.getByTestId('start-analyze-button').click()

  await expect(page.getByTestId('analysis-done-panel')).toBeVisible({ timeout: 45_000 })
  await expect(page.getByText('分析完成')).toBeVisible()
  await expect(page.getByTestId('risk-detail-table')).toBeVisible()
  await expect(page.getByText('v3.2风险')).toBeVisible()
  await expect(page.getByText('v3.2依据摘要')).toBeVisible()

  await page.getByTestId('manual-event-title').fill('TDK高容MLCC缺货涨价通知')
  await page.getByTestId('manual-event-brand').fill('TDK')
  await page.getByTestId('manual-event-category').fill('high_cap_mlcc')
  await page.getByTestId('manual-event-mpn').fill('C3225X5R1A226M250AC')
  await page.getByTestId('manual-event-type').selectOption('price_increase')
  await page.getByTestId('manual-event-increase').fill('20')
  await page.getByTestId('manual-event-lead-time').fill('16')
  await page.getByTestId('manual-event-source').fill('file://demo/tdk-high-cap-mlcc-notice.pdf')

  const shortage = page.getByTestId('manual-event-shortage-confirmed')
  if (!(await shortage.isChecked())) {
    await shortage.check()
  }
  const confirmed = page.getByTestId('manual-event-confirmed-by-user')
  if (!(await confirmed.isChecked())) {
    await confirmed.check()
  }

  await page.getByTestId('manual-event-submit').click()
  await expect(page.getByText('人工事件已进入行情事件库')).toBeVisible({ timeout: 20_000 })

  await page.getByTestId('reanalyze-current-bom').click()
  await expect(page.getByTestId('analysis-done-panel')).toBeVisible({ timeout: 45_000 })
  await expect(page.getByText('TDK')).toBeVisible()
  await expect(page.getByText('需求/供应轨').or(page.getByText('材料传导轨')).or(page.getByText('信息不足'))).toBeVisible()
  await expect(page.getByTestId('v32-risk-button').first()).toBeVisible()
  await expect(page.getByTestId('matched-events-button').first()).toBeVisible({ timeout: 20_000 })
})
```

- [ ] **Step 5: 运行 E2E 测试**

先确认服务已启动：

```powershell
powershell -ExecutionPolicy Bypass -File "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer\scripts\smoke-browser-demo.ps1"
```

再运行：

```powershell
cd "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer\frontend"
npm run test:e2e
```

Expected:

```text
1 passed
```

- [ ] **Step 6: 提交 E2E 测试改动**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.js frontend/e2e/v32-demo-loop.spec.js
git commit -m "test: add v3.2 browser e2e demo loop"
```

---

## Task 3: 增加 E2E 包装脚本和文档

**Files:**
- Create: `scripts/e2e-browser-demo.ps1`
- Modify: `scripts/start-demo.ps1`
- Modify: `DEMO-V3.2.md`
- Modify: `README-V3.2-MVP.md`
- Modify: `GIT-HANDOFF.md`

**Interfaces:**
- Consumes: Task 2 的 `npm run test:e2e`。
- Produces: 项目根目录一键 E2E 命令 `powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1`。

- [ ] **Step 1: 创建包装脚本**

Create `scripts/e2e-browser-demo.ps1`:

```powershell
# BOM Risk Analyzer v3.2 browser E2E demo test
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$SmokeScript = Join-Path $PSScriptRoot "smoke-browser-demo.ps1"

if (-not (Test-Path -LiteralPath $FrontendDir)) {
    throw "Frontend directory not found: $FrontendDir"
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "package.json"))) {
    throw "package.json not found in frontend directory: $FrontendDir"
}

Write-Host "Running browser smoke test before E2E..." -ForegroundColor Cyan
& powershell -ExecutionPolicy Bypass -File $SmokeScript

Push-Location $FrontendDir
try {
    Write-Host "Running Playwright v3.2 browser E2E demo loop..." -ForegroundColor Cyan
    npm run test:e2e
} finally {
    Pop-Location
}
```

- [ ] **Step 2: 更新启动脚本提示**

在 `scripts/start-demo.ps1` 的提示区增加：

```powershell
Write-Host "For full browser E2E acceptance, run: powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1" -ForegroundColor Green
```

- [ ] **Step 3: 更新 DEMO 文档**

在 `DEMO-V3.2.md` 的自动验证命令章节增加：

```markdown
完整浏览器端到端验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1
```

该脚本会先运行浏览器烟测，再用 Playwright 自动上传 `demo\sample-bom-v32.csv`，录入 TDK 高容 MLCC 缺货涨价事件，重新分析当前 BOM，并检查 v3.2 风险依据和关联事件是否出现在页面上。
```

- [ ] **Step 4: 更新 README 和移交说明**

在 `README-V3.2-MVP.md` 的已验证行为中增加：

```markdown
- 浏览器端到端验收可自动完成样例 BOM 上传、人工行情事件录入、重新分析和页面关键结果校验。
```

在 `GIT-HANDOFF.md` 的仓库内容中增加：

```markdown
- `frontend/e2e/v32-demo-loop.spec.js`、`scripts/e2e-browser-demo.ps1`：完整浏览器端到端验收。
```

- [ ] **Step 5: 提交文档和脚本**

```powershell
git add scripts/e2e-browser-demo.ps1 scripts/start-demo.ps1 DEMO-V3.2.md README-V3.2-MVP.md GIT-HANDOFF.md
git commit -m "docs: document v3.2 browser e2e acceptance"
```

---

## Task 4: 更新部署脚本、完整验证和移交包

**Files:**
- Modify: `deploy-v3.2-mvp.ps1`
- Modify: `docs/plans/2026-06-27-v32-playwright-e2e-demo.md`

**Interfaces:**
- Consumes: 前面所有新增文件。
- Produces: 更新后的 WorkBuddy 目标项目和 Git bundle。

- [ ] **Step 1: 更新部署脚本复制文件清单**

在 `deploy-v3.2-mvp.ps1` 中确保复制：

```powershell
$frontendFiles = @(
    "src\components\V32EvidencePanel.vue",
    "src\components\ManualEventQuickAdd.vue",
    "src\components\RiskDetailTable.vue",
    "src\components\BomUploader.vue",
    "src\views\BomAnalyze.vue",
    "playwright.config.js",
    "e2e\v32-demo-loop.spec.js"
)

$scriptFiles = @(
    "start-demo.ps1",
    "smoke-browser-demo.ps1",
    "e2e-browser-demo.ps1"
)
```

同时复制 `frontend/package.json` 和 `frontend/package-lock.json`，如果存在：

```powershell
foreach ($frontendRootFile in @("package.json", "package-lock.json")) {
    $srcFile = Join-Path $SRC "frontend\$frontendRootFile"
    if (Test-Path -LiteralPath $srcFile) {
        Copy-Item $srcFile (Join-Path $DST "frontend\$frontendRootFile") -Force
    }
}
```

- [ ] **Step 2: 运行部署脚本**

```powershell
powershell -ExecutionPolicy Bypass -File "d:\1项目清单\交期风险排查\BOM-Risk-Analyzer-patch\deploy-v3.2-mvp.ps1" -TargetProject "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer"
```

Expected:

```text
26 passed
79 passed
Frontend build passed
```

- [ ] **Step 3: 运行前端组件测试和 E2E**

```powershell
cd "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer\frontend"
npm test -- --run
```

Expected:

```text
Test Files  2 passed (2)
Tests  3 passed (3)
```

```powershell
cd "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer"
powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1
```

Expected:

```text
1 passed
```

- [ ] **Step 4: 提交部署脚本和计划**

```powershell
git add deploy-v3.2-mvp.ps1 docs/plans/2026-06-27-v32-playwright-e2e-demo.md
git commit -m "chore: deploy v3.2 browser e2e acceptance"
```

- [ ] **Step 5: 重新生成 Git bundle**

```powershell
git bundle create "..\BOM-Risk-Analyzer-v3.2-mvp.bundle" --all
git bundle verify "..\BOM-Risk-Analyzer-v3.2-mvp.bundle"
```

Expected:

```text
BOM-Risk-Analyzer-v3.2-mvp.bundle is okay
```

---

## Self-Review

- Spec coverage: 计划覆盖 Playwright 依赖、配置、E2E 主链路、稳定选择器、包装脚本、文档、部署脚本、验证和移交包。
- Placeholder scan: 无 TBD/TODO/稍后实现等占位项。
- Type consistency: 所有 `data-testid` 名称在 Task 1 定义，并在 Task 2 E2E 中一致使用。
- Scope check: 只覆盖 v3.2 demo 主链路，没有扩展为全系统 UI 自动化。
