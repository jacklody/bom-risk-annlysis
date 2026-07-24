---
title: "production-v1 版本"
confidence: 0.95
last_ingested: 2026-07-24
sources:
  - raw/articles/EXPERT-DIAGNOSIS.md
  - raw/notes/EXECUTION-HISTORY.md
stale: false
---

## 定义

production-v1 是 BOM 交期风险预警系统的生产版本，包含专家诊断报告要求的所有 P0/P1 项，具备生产级部署能力。

## 核心特性

### 数据层
- PostgreSQL 18 + Alembic 迁移
- Redis 缓存（Memurai）

### 任务队列
- Celery + Redis 异步任务

### 风险引擎
- 多因子风险引擎（七因子加权评分）
- 五级 MPN 匹配（L1-L5）
- 事实/推断双通道分流

### 安全认证
- JWT 认证
- RBAC 四角色权限（admin/analyst/procurement/viewer）

### 业务功能
- 风险生命周期管理（7态状态机）
- 多组织隔离
- ERP/PLM 对接适配器

### 运维监控
- 结构化日志（JSON）
- Prometheus 指标 + 11 条告警规则
- 7 个 PowerShell 部署脚本

## 项目结构

```
production-v1/
├── backend/
│   ├── app/
│   │   ├── api/          # REST API 端点
│   │   ├── services/     # 业务逻辑层
│   │   ├── models/       # 数据库模型
│   │   ├── config/       # 配置管理
│   │   └── utils/        # 工具函数
│   ├── alembic/          # 数据库迁移
│   └── tests/            # 测试用例
├── frontend/             # 前端代码
├── deploy/               # 部署脚本
└── docs/                 # 文档
```

## 部署要求

- PostgreSQL 18（服务名：postgresql-x64-18）
- Redis（Memurai）
- Python 3.11+
- Node.js 18+

## 启动方式

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\scripts\start-services.ps1
```

## 关联概念

- [[five-level-mpn-matching]]：五级 MPN 匹配
- [[multi-factor-risk-engine]]：多因子风险引擎
- [[signal-origin]]：信号来源分类