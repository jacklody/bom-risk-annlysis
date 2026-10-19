# Git 移交说明

本目录已经整理为一个本地 Git 仓库，包含 BOM Risk Analyzer v3.2 MVP 后端补丁、前端最小闭环、完整演示闭环，以及 v3.3 行情情报收件箱 MVP。

## 仓库内容

- `backend/app/services/upstream/`：v3.2 MVP 核心算法、人工事件、依据链模块。
- `backend/app/api/`：事件 API 与 BOM 风险分析 API 接入。
- `frontend/src/components/`、`frontend/src/views/`：v3.2 风险展示、依据链弹层、人工事件快速录入。
- `tests/`：A1/A2/A3/A4/A5 与 BOM 分析集成测试。
- `frontend/src/components/__tests__/`：前端组件测试。
- `demo/sample-bom-v32.csv`：完整演示闭环样例 BOM。
- `scripts/start-demo.ps1`：一键启动后端和前端演示服务。
- `scripts/smoke-browser-demo.ps1`：浏览器演示烟测，验证后端健康检查、前端首页和 Vite `/api` 代理。
- `frontend/e2e/v32-demo-loop.spec.js`、`frontend/e2e/v33-market-inbox.spec.js`、`scripts/e2e-browser-demo.ps1`：完整浏览器端到端验收。
- `backend/app/services/upstream/market_notice_parser.py`、`market_inbox_service.py`、`backend/app/api/market_inbox.py`：v3.3 行情情报收件箱后端能力。
- `frontend/src/views/MarketInbox.vue`、`frontend/src/api/marketInbox.js`：v3.3 行情情报收件箱前端页面和 API 客户端。
- `DEMO-V3.2.md`：阶段成果演示说明。
- `deploy-v3.2-mvp.ps1`：将补丁复制到 WorkBuddy 项目并运行后端测试和前端构建的部署脚本。
- `README-V3.2-MVP.md`：补丁说明。
- `BOM风险预警系统-v3.2第一轮MVP验收记录.md`：验收记录。

## 本地验证

```powershell
py -3.11 -m pytest tests -q
```

重点验证：

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

## 部署到 WorkBuddy 项目

新版脚本不再把中文路径写死在脚本内，避免 Windows PowerShell 5 读取 UTF-8 中文路径时乱码。请通过 `-TargetProject` 传入目标项目路径：

```powershell
powershell -ExecutionPolicy Bypass -File "d:\1项目清单\交期风险排查\BOM-Risk-Analyzer-patch\deploy-v3.2-mvp.ps1" -TargetProject "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer"
```

脚本会优先使用 `py -3.11`，避免误调用未安装依赖的 Python 环境；若目标项目存在 `frontend/package.json`，还会运行前端构建。当前验证口径包括：后端 v3.2/v3.3 重点测试、项目基线测试、前端组件与页面测试、前端 build，以及浏览器端到端验收。浏览器 E2E 会覆盖样例 BOM 上传、人工行情事件录入、重分析、页面关键结果，以及 v3.3 行情收件箱的原文识别和历史 BOM 影响摘要。

## 本地 Git 仓库状态

当前目录已初始化为本地 Git 仓库，并已提交 v3.2 MVP 补丁；v3.3 提交后可在本目录运行：

```powershell
git log --oneline
```

另已生成可移交的 Git bundle 文件：

```text
BOM-Risk-Analyzer-v3.2-mvp.bundle
```

对方可以用下面命令从 bundle 克隆：

```powershell
git clone "d:\1项目清单\交期风险排查\BOM-Risk-Analyzer-v3.2-mvp.bundle" BOM-Risk-Analyzer-v3.2-mvp
```

## 推送到远程 Git 仓库

如果你已经有 GitHub/Gitee/GitLab 空仓库，把地址替换到下面命令：

```powershell
git remote add origin <你的远程仓库地址>
git branch -M main
git push -u origin main
```

如果要用 GitHub CLI 新建私有仓库：

```powershell
gh auth login
gh repo create bom-risk-analyzer-v32-mvp --private --source . --push
```
