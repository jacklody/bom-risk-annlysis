# BOM 交期风险预警系统 — 执行过程复盘

> 本文件记录项目从启动到当前的完整执行过程，包括所有版本的需求迭代和执行动作结果。

---

## 目录

- [一、项目背景与目标](#一项目背景与目标)
- [二、版本迭代历程](#二版本迭代历程)
- [三、关键执行动作记录](#三关键执行动作记录)
- [四、技术架构演进](#四技术架构演进)
- [五、问题与修复记录](#五问题与修复记录)
- [六、验收与合规审查](#六验收与合规审查)

---

## 一、项目背景与目标

### 1.1 项目定位
BOM 交期风险预警系统是一个电子元器件供应链风险预警平台，旨在帮助企业识别和管理电子元器件采购中的交期风险。

### 1.2 核心目标
1. 从多数据源拉通风险信息（分销商 API、生命周期数据、人工事件、涨价函、原材料价格、灾害、政策）
2. 将风险源映射到具体 BOM 型号
3. 实现事实/推断双通道风险评估
4. 提供可追溯、可确认、可复盘的风险管理能力

---

## 二、版本迭代历程

### 2.1 V4 版本（初始版本）
- 基础风险分析功能
- 双轨风险引擎（dual_track_risk_engine.py）
- 三套前端并存（V4 + V5 + frontend-v2）
- SQLite 数据库
- 无缓存机制
- 无认证鉴权

### 2.2 V5 版本（演进版本）
- 多因子风险引擎（multi_factor_risk_engine.py）
- 部分前端整合
- 初步的数据源拉通

### 2.3 production-v1 版本（生产版本）
- PostgreSQL 18 + Alembic 迁移
- Redis 缓存（Memurai）
- Celery 异步任务队列
- 五级 MPN 匹配（L1-L5）
- 事实/推断双通道分流
- JWT 认证鉴权
- RBAC 四角色权限
- 风险生命周期管理
- 多组织隔离
- ERP/PLM 对接适配器

---

## 三、关键执行动作记录

### 3.1 环境配置阶段

#### 3.1.1 PostgreSQL 安装配置
- **动作**：安装 PostgreSQL 18，创建 `bom_user` 用户和 `bom_risk` 数据库
- **问题**：服务名称不匹配（脚本用 `PostgreSQL-16`，实际为 `postgresql-x64-18`）
- **修复**：全局替换 PowerShell 脚本中的服务名称

#### 3.1.2 Redis（Memurai）安装配置
- **动作**：安装 Memurai（Windows 版 Redis），配置密码
- **结果**：缓存服务正常运行

#### 3.1.3 PowerShell 脚本修复
- **问题**：执行策略限制（`Set-ExecutionPolicy RemoteSigned`）
- **问题**：`$Host` 变量冲突（改为 `$DbHost`）
- **修复**：在 `start-services.ps1`, `status-services.ps1`, `backup-database.ps1`, `restore-database.ps1` 中修复

### 3.2 后端核心开发

#### 3.2.1 五级 MPN 匹配实现
- **文件**：`part_matcher.py`
- **功能**：实现 L1-L5 匹配层次
  - L1: 精确 MPN 匹配（置信度 0.95）
  - L2: 规格化 MPN 匹配（置信度 0.90）
  - L3: 系列/前缀匹配（置信度 0.75）
  - L4: 品牌+品类匹配（置信度 0.55）
  - L5: 品类波及（置信度 0.30）

#### 3.2.2 事实/推断双通道实现
- **文件**：`multi_factor_risk_engine.py`
- **功能**：
  - 新增 `signal_origin` 字段（factual/inferred/mixed）
  - 评分拆分（fact_score/supply_score/inference_score）
  - 推断风险封顶黄色（35分）
  - IC 类材料传导弱约束

#### 3.2.3 命中持久化表
- **文件**：`risk_match.py`, `event_bom_match_service.py`
- **功能**：`risk_event_bom_matches` 表，记录事件与 BOM 的命中关系

#### 3.2.4 熔断机制
- **文件**：`circuit_breaker.py`
- **功能**：数据源熔断、重试、降级（CLOSED→OPEN→HALF_OPEN）

#### 3.2.5 认证鉴权
- **文件**：`api/auth.py`
- **功能**：JWT 认证 + RBAC 四角色（admin/analyst/procurement/viewer）

#### 3.2.6 风险生命周期
- **文件**：`risk_lifecycle_service.py`
- **功能**：7 态状态机（pending→under_review→confirmed→action_taken→monitoring→resolved/ignored）

### 3.3 前端开发

#### 3.3.1 前端整合
- 删除嵌套目录 `frontend/src/frontend/`
- 清理 V4/V5/frontend-v2 三套前端冗余

#### 3.3.2 Mock 数据替换
- **文件**：`riskChainService.js`
- **动作**：将 Mock 数据生成器替换为真实后端 API 调用
- **API**：`/risk-chain/dashboard`, `/risk-chain/material-chain` 等

### 3.4 部署与运维

#### 3.4.1 部署脚本
- 7 个 PowerShell 脚本：启动/停止服务、数据库备份/恢复、状态检查等

#### 3.4.2 监控告警
- Prometheus 配置 + 11 条告警规则
- 结构化日志（JSON 格式）

---

## 四、技术架构演进

### 4.1 数据层演进
```
V4: SQLite (单进程, 无迁移)
V5: SQLite (单进程, 手写迁移)
production-v1: PostgreSQL 18 + Alembic (多进程, 正规迁移)
```

### 4.2 缓存层演进
```
V4: 内存 dict (进程重启丢失)
V5: 内存 dict (进程重启丢失)
production-v1: Redis (Memurai) + 降级机制
```

### 4.3 任务队列演进
```
V4: 同步阻塞
V5: 同步阻塞
production-v1: Celery + Redis (异步任务)
```

### 4.4 风险引擎演进
```
V4: 双轨引擎 (dual_track_risk_engine.py)
V5: 双轨 + 多因子引擎并存
production-v1: 多因子引擎唯一, 双轨废弃
```

### 4.5 匹配引擎演进
```
V4: 品牌+品类匹配 (L4/L5)
V5: 初步系列匹配
production-v1: L1-L5 五级匹配完整实现
```

---

## 五、问题与修复记录

### 5.1 P0 阻断上线缺陷

#### P0-01: 多因子引擎白写
- **问题**：代码写好了但从未被调用，主流程还在用已废弃的双轨引擎
- **修复**：修改 `risk_context_builder.py`，将 `evaluate_dual_track_risk` 替换为 `evaluate_multi_factor_risk`

#### P0-02: 推断封顶漏风
- **问题**：API 层做了等级封顶但 `score` 没封顶，造成数据不一致
- **修复**：在 `_apply_signal_split` 中，当 `signal_origin == INFERRED` 时，`final_score` 也通过 `_capped_inference_score()` 封顶

#### P0-03: 命中表空转
- **问题**：持久化服务完整实现但从未写入数据
- **修复**：在 `analyze_bom` 和 `analyze_all_projects` 中调用 `EventBomMatchService.persist_matches()`

#### P0-04: 批量接口崩溃
- **问题**：`analyze_all_projects` 有未定义变量 `intel_engine` 引用
- **修复**：在函数开头添加 `intel_engine = MarketIntelEngine()`

#### P0-05: L4 误报
- **问题**：低置信度匹配（L4，置信度 0.55）仍触发 RED 告警
- **修复**：将 L4 命中的风险等级从 `RiskLevel.RED` 改为 `RiskLevel.ORANGE`

### 5.2 其他问题

#### 依赖版本冲突
- **问题**：Starlette/httpx 版本不兼容（`ModuleNotFoundError: No module named 'httpx2'`）
- **修复**：降级 Starlette 到 `>=0.37.0,<1.0.0`

#### bcrypt 版本冲突
- **问题**：`ValueError: password cannot be longer than 72 bytes`
- **修复**：降级 bcrypt 到 `>=3.2.0,<4.0.0`

#### Vite 代理端口配置
- **问题**：前端配置端口与 Vite 配置冲突
- **修复**：更新 `vite.config.js`，设置端口 3000，代理目标 `http://127.0.0.1:8000`

---

## 六、验收与合规审查

### 6.1 专家诊断报告（EXPERT-DIAGNOSIS.md）
- **发布时间**：2026-07-22
- **内容**：8 大章节，涵盖数据源拉通、风险映射链路、LLM 评估、生产差距清单、设计冗余、核心架构等

### 6.2 合规审查结果

#### P0 强制项（5/5 ✅）
1. ✅ PostgreSQL 迁移完成
2. ✅ 五级 MPN 匹配实现
3. ✅ 数据源熔断+重试+降级
4. ✅ Redis 缓存层
5. ✅ 事件→BOM 命中持久化表

#### P1 稳定项（7/7 ✅）
1. ✅ Celery 任务队列
2. ✅ 结构化日志 + Prometheus 指标
3. ✅ Alembic 数据库迁移
4. ✅ 健康检查增强
5. ✅ JWT 认证鉴权
6. ✅ 风险生命周期管理
7. ✅ 数据新鲜度机制

#### 设计改造项（5/5 ✅）
1. ✅ L1-L5 五级匹配
2. ✅ signal_origin 字段 + 评分隔离
3. ✅ 材料链路推断风险约束（最高黄色）
4. ✅ risk_event_bom_matches 表完整字段
5. ✅ fact_score/supply_score/inference_score 评分拆分

#### 冗余砍除项（4/4 ✅）
1. ✅ 双轨引擎废弃
2. ✅ 三套前端清理
3. ✅ chain_reasoning 降为辅助解释
4. ✅ Mock 风险链路驾驶舱删除

### 6.3 测试验证结果
- **测试数量**：101 passed, 7 skipped
- **测试覆盖**：五级匹配、信号来源分类、推断评分封顶、熔断机制、风险链 API 等

---

## 七、总结

### 7.1 项目成果
- 完成了从 V4 到 production-v1 的完整架构演进
- 实现了专家诊断报告中要求的所有 P0/P1 项
- 建立了完整的风险评估体系（事实/推断双通道）
- 具备生产级部署能力（PostgreSQL、Redis、Celery、监控告警）

### 7.2 核心设计原则
```
数据源可信度 × 型号匹配可信度 × 事实/推断分流 × 可追溯证据链 × 人工确认闭环
```

### 7.3 关键经验
1. **接口先行**：先定义数据结构和接口，再实现具体逻辑
2. **规则主导**：核心风险判断必须基于确定性规则，LLM 仅做辅助
3. **可追溯性**：每个风险决策必须有完整的证据链和持久化记录
4. **容错降级**：任何外部依赖必须有熔断、重试、降级机制

---

*文档生成时间：2026-07-24 · 基于完整对话历史整理*