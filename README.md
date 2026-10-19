# BOM 交期风险智能排查系统

公开发布版，包含后端 API、前端界面、演示入口、文档和离线汇报产物。

## 快速启动

### 后端
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端
```powershell
cd frontend
npm install
npm run dev
```

默认前端入口：`http://localhost:5173/`，后端接口：`http://localhost:8000/`。

## 主要产物

- `backend/`：FastAPI 后端服务
- `frontend/`：Vue + Vite 前端系统
- `docs/`：当前系统界面、交付说明等
- `system-demo-launcher.html`：领导汇报演示入口
- `bom-risk-review/`：静态评审报告页面
- `文档/`：调研、执行计划、数据源与测试报告

## 说明

本仓库不包含本地环境变量、缓存、日志、数据库文件和 node_modules。
