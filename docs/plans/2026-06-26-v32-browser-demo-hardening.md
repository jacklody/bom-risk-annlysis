# v3.2 浏览器级演示验收与体验加固计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 API 级演示闭环之外，补齐浏览器演示稳定性，让用户打开前端后能稳定连通后端并看到 BOM 分析入口。

**Architecture:** 保持现有 Vite/Vue 架构，统一前后端演示地址为 `127.0.0.1`，新增一个 PowerShell 浏览器演示烟测脚本，验证后端健康检查、前端首页、Vite `/api` 代理三条链路。再使用浏览器工具打开页面，检查关键 UI 文案、控制台错误和网络错误。

**Tech Stack:** Vue 3、Vite dev server、FastAPI、PowerShell、integrated browser MCP。

## Global Constraints

- 不引入 Playwright/Cypress 等新依赖。
- 不改变生产 API 路径，仍使用 `/api` 相对路径。
- 演示后端固定为 `http://127.0.0.1:8001`。
- 演示前端固定为 `http://127.0.0.1:9000`。
- 烟测脚本只验证浏览器演示链路可达，不替代后端完整业务测试。

---

## 文件结构

- Modify: `frontend/vite.config.js`
  - 将 dev proxy 从 `http://localhost:8001` 改为 `http://127.0.0.1:8001`。
- Create: `scripts/smoke-browser-demo.ps1`
  - 验证后端健康检查、前端首页、前端代理 `/api/health`。
- Modify: `scripts/start-demo.ps1`
  - 启动后提示运行烟测脚本。
- Modify: `DEMO-V3.2.md`
  - 增加浏览器验收步骤和代理排查说明。
- Modify: `deploy-v3.2-mvp.ps1`
  - 同步 `frontend/vite.config.js` 和 scripts。

---

## Task 1: 代理一致性

**Files:**
- Modify: `frontend/vite.config.js`

**Steps:**
- [ ] 将 `/api` proxy target 改为 `http://127.0.0.1:8001`。
- [ ] 运行 `npm run build` 确认配置不破坏构建。

---

## Task 2: 浏览器演示烟测脚本

**Files:**
- Create: `scripts/smoke-browser-demo.ps1`

**Steps:**
- [ ] 用 `Invoke-WebRequest` 检查 `http://127.0.0.1:8001/api/health` 返回 200。
- [ ] 检查 `http://127.0.0.1:9000/` 返回 200 且包含 `id="app"`。
- [ ] 检查 `http://127.0.0.1:9000/api/health` 返回 200，证明 Vite 代理通。
- [ ] 输出下一步人工演示路径：上传 `demo\sample-bom-v32.csv`。

---

## Task 3: 文档与部署

**Files:**
- Modify: `scripts/start-demo.ps1`
- Modify: `DEMO-V3.2.md`
- Modify: `deploy-v3.2-mvp.ps1`

**Steps:**
- [ ] 启动脚本提示烟测命令。
- [ ] 演示文档增加烟测命令和常见代理错误。
- [ ] 部署脚本复制 `frontend/vite.config.js`。

---

## Task 4: 验证和移交

**Commands:**
- `powershell -ExecutionPolicy Bypass -File .\scripts\smoke-browser-demo.ps1`
- `py -3.11 -m pytest tests\test_v32_demo_loop.py -q`
- `py -3.11 -m pytest tests -q`
- `npm test -- --run`
- `npm run build`
- 浏览器工具打开 `http://127.0.0.1:9000/`，检查页面关键文案、控制台和网络请求。
