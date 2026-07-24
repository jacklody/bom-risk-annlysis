# BOM物料风险预警系统 — 产品需求文档 (PRD)

> 版本：v1.0  
> 编制日期：2026-06-23  
> 作者：产品团队  
> 基础来源：基于workbuddy已调研内容（BOM物料标准化审查与交期风险评估-调研报告 2026-06-12）修订

---

## 目录

1. [产品概述](#一产品概述)
2. [市场背景与用户分析](#二市场背景与用户分析)
3. [竞品分析](#三竞品分析)
4. [功能需求](#四功能需求)
5. [非功能需求](#五非功能需求)
6. [系统架构](#六系统架构)
7. [数据模型](#七数据模型)
8. [风险评分算法](#八风险评分算法)
9. [用户界面设计要点](#九用户界面设计要点)
10. [实施计划与里程碑](#十实施计划与里程碑)
11. [成功指标](#十一成功指标)

---

## 一、产品概述

### 1.1 产品定位

**BOM物料风险预警系统** 是一款面向电子行业硬件研发团队的供应链风险管理和物料决策辅助工具。通过在BOM（物料清单）级别进行颗粒度精确到每颗物料的交期风险评估、通用性检查、EOL监控和替代推荐，协助研发团队在设计阶段即识别并规避供应链风险。

### 1.2 核心价值主张

| 价值点 | 描述 |
|--------|------|
| **Shift-Left风险管控** | 将供应链风险检查从采购阶段前移到设计阶段，避免"设计定型后发现关键物料停产"的困局 |
| **历史项目持续守护** | 已交付项目的BOM不是"一交了之"，系统持续监控物料生命周期变化，主动告警 |
| **新项目快速评审** | 新BOM上传后分钟级完成全量物料风险扫描，加速NPI（新产品导入）决策 |
| **数据沉淀即护城河** | 每次BOM审查结果积累为内部物料优选库(AVL)，越用越准，长期降低供应链风险 |

### 1.3 目标用户

| 用户角色 | 核心场景 | 痛点 |
|---------|---------|------|
| **硬件工程师** | 设计阶段BOM评审、物料选型 | 不确定选用的物料是否好买/会不会停产 |
| **项目经理** | 新项目风险评估、历史项目监控 | 项目交付后发现物料停产，售后维修无料可用 |
| **采购工程师** | 物料交期确认、替代寻源 | 不知道研发选什么料，等BOM到手上已经快来不及了 |
| **供应链/质量负责人** | 供应链风险全局视图、合规管控 | 缺乏系统化的风险预警，每次都是"事后救火" |

### 1.4 产品边界

**做**：
- BOM级物料交期/库存/生命周期/替代风险检测与预警
- 历史BOM的持续风险监控与告警
- 新BOM的快速风险评审
- 物料通用性（标准化程度）评估
- 物料价格趋势与上游涨价监控
- 物料出货量变化预警

**不做**（但预留接口）：
- ERP/PLM系统的完整替代
- 供应商关系管理(SRM)
- 产品生命周期管理(PLM)
- PCB设计工具的EDA功能
- 制造执行系统(MES)

---

## 二、市场背景与用户分析

### 2.1 行业痛点量化

> 以下数据来自调研报告及行业公开信息：

| 指标 | 数据 | 来源 |
|------|------|------|
| 2025年全球元器件停产数量 | 621,909颗 | Z2Data 2026年3月分析 |
| 其中"静默停产"（无PCN通知） | 52%（323,286颗） | Z2Data |
| 符合JEDEC标准的PCN比例 | 仅约25% | Z2Data |
| 国内贸易商仍用Excel处理BOM的比例 | 78% | 2025年行业报告 |
| EOL+交期>12周覆盖供应链中断比例 | 80%+ | 行业经验 |

### 2.2 用户场景详解

#### 场景A：新项目BOM风险评审

```
张三（硬件工程师）完成了一个新产品的原理图设计，导出了BOM Excel。
他需要确认：
1. BOM中哪些物料交期超过12周？（影响项目排期）
2. 有没有物料已经EOL或NRND？（不能用于新设计）
3. 哪些物料只有单一货源？（供应中断风险高）
4. 哪些物料有国产替代？（供应链安全/降本）

当前做法：手动在立创、Mouser、DigiKey逐个搜索，每人半天~1天
期望：上传BOM → 5分钟内输出逐行风险标记 + 替代建议
```

#### 场景B：历史项目风险巡检

```
李四（项目经理）负责的3个老产品已交付2年。
最近听说某款MCU全球缺货，他不确定自己的产品是否用了这款料。
同时团队需要知道：老产品的BOM中有没有已经开始EOL的物料？

当前做法：不定期、无系统化的抽查（或者根本不查）
期望：每周系统自动扫描所有历史BOM → 发现风险自动告警
```

#### 场景C：物料通用性评估

```
王五（供应链负责人）发现团队不同项目中使用了功能相近但型号不同的MOS管。
他希望系统能识别这种情况，推荐标准化物料，减少物料种类、提升单一物料采购量。

期望：系统能标记"非标准物料" → 推荐标准替代 → 统计物料复用率
```

---

## 三、竞品分析

### 3.1 竞品定位图

```
                    高价格
                      │
       SiliconExpert ●│
       Z2Data        ●│
                      │   ● 云汉芯城
                      │   ● 华秋电子
  ──────────────────┼──────────────────
                      │
               自建AVL ●
                      │   ● Octopart (免费)
                      │   ● KiCost (开源)
                      │
                    低价格
  功能深度 ←────────────────→ 易用性
```

### 3.2 竞品详细对比

| 维度 | SiliconExpert | Z2Data | Octopart | 云汉芯城 | KiCost(开源) | **本系统(目标)** |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 生命周期预测 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ❌ | ❌ | ⭐⭐ |
| EOL/PCN监控 | ⭐⭐⭐ | ⭐⭐⭐ | ❌ | ❌ | ❌ | ⭐⭐ |
| 交期/库存查询 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 价格聚合 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| 替代推荐 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ❌ | ⭐⭐⭐ |
| 合规检查 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ❌ | ⭐ | ⭐ |
| 多层级供应链 | ❌ | ⭐⭐⭐ | ❌ | ❌ | ❌ | ❌ (P2) |
| 国产替代 | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ❌ | ⭐⭐ |
| API集成 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| 历史BOM管理 | ⭐⭐ | ⭐⭐ | ❌ | ❌ | ❌ | ⭐⭐⭐ |
| 定时巡检告警 | ⭐⭐ | ⭐⭐⭐ | ❌ | ❌ | ❌ | ⭐⭐⭐ |
| 年成本 | ¥20-100万+ | ¥20-100万+ | 免费 | ¥0-5万 | 免费 | ¥0-2万(自建) |
| 上手难度 | 高 | 高 | 低 | 中 | 中 | 低 |

### 3.3 本产品差异化优势

| 差异点 | 竞品不足 | 本产品策略 |
|--------|---------|-----------|
| **历史BOM持续守护** | 商业平台只做单次查询，不管"老项目" | 所有历史BOM纳入巡检范围，持续监控 |
| **物料通用性评估** | 平台只管"能不能买到"，不管"该不该用" | 结合标准封装/多货源/主流品牌三要素评分 |
| **价格/出货量趋势** | 多数平台只给实时价格 | 积累历史快照，分析趋势变化 |
| **低成本启动** | 商业平台动辄数十万 | 免费API+开源组件，MVP阶段零成本 |
| **数据自主可控** | SaaS平台数据在外 | 所有BOM和AVL数据本地部署 |

---

## 四、功能需求

### 4.1 功能模块总览

```
BOM物料风险预警系统
├── M1: BOM管理
│   ├── F1.1 BOM上传与解析
│   ├── F1.2 型号标准化
│   ├── F1.3 历史BOM归档
│   └── F1.4 BOM版本对比
├── M2: 风险分析引擎
│   ├── F2.1 交期风险评估
│   ├── F2.2 库存风险评估
│   ├── F2.3 生命周期检测
│   ├── F2.4 供应商集中度评估
│   ├── F2.5 价格趋势分析
│   ├── F2.6 通用性评分
│   └── F2.7 出货量风险
├── M3: 监控与告警
│   ├── F3.1 定时巡检
│   ├── F3.2 变化检测
│   ├── F3.3 分级告警
│   └── F3.4 告警通知
├── M4: 替代推荐
│   ├── F4.1 同规格替代匹配
│   ├── F4.2 国产替代推荐
│   └── F4.3 替代方案对比
├── M5: 报告与导出
│   ├── F5.1 风险仪表盘
│   ├── F5.2 Excel报告导出
│   └── F5.3 定期报告
└── M6: 物料优选库(AVL)
    ├── F6.1 AVL物料录入
    ├── F6.2 AVL物料评分
    └── F6.3 物料复用率统计
```

### 4.2 M1: BOM管理

#### F1.1 BOM上传与解析

| 属性 | 描述 |
|------|------|
| **用户故事** | 作为硬件工程师，我希望直接上传BOM Excel文件，系统自动识别各列内容，无需手动映射 |
| **输入** | .xlsx / .xls / .csv 格式的BOM文件 |
| **智能列映射** | 自动识别：位号(Reference/Designator)、型号(MPN/Part Number)、规格(Specification/Value)、封装(Package/Footprint)、用量(Quantity/Qty)、描述(Description) |
| **容错** | 列名变体兼容（如 "Mfr Part #" / "MPN" / "型号" / "物料编码" 均识别为型号列） |
| **验收标准** | 90%以上常见BOM格式无需手动调整列映射 |
| **优先级** | P0 |

#### F1.2 型号标准化

| 属性 | 描述 |
|------|------|
| **用户故事** | 作为工程师，我经常拿到不同格式的型号（有的带包装后缀，有的是简写），希望系统自动标准化 |
| **处理步骤** | ① 去除常见包装后缀（TR, T&R, T/R, CT, DKR, REEL, TAPE） ② 去除温度范围后缀（视器件类型） ③ 提取核心MPN ④ rapidfuzz模糊匹配纠错 |
| **精度目标** | 标准化准确率 ≥ 85%（对照人工校验） |
| **优先级** | P0 |

#### F1.3 历史BOM归档

| 属性 | 描述 |
|------|------|
| **用户故事** | 作为项目经理，我希望所有历史项目的BOM都能在系统中保存和管理 |
| **功能** | 按项目、版本存储BOM；支持搜索、筛选、导出；查看每个项目的最新风险状态 |
| **优先级** | P0 |

#### F1.4 BOM版本对比

| 属性 | 描述 |
|------|------|
| **用户故事** | 作为硬件工程师，当BOM发生变更时，我想看到新旧BOM的差异（哪些物料新增/删除/变更） |
| **功能** | 两个BOM版本逐行对比，高亮差异行 |
| **优先级** | P2 |

### 4.3 M2: 风险分析引擎

#### 风险维度汇总

| 编号 | 风险维度 | 数据来源 | 触发条件 | 等级 | 优先级 |
|:---:|---------|---------|---------|:---:|:---:|
| F2.1 | **交期风险** | Mouser/DigiKey API (Lead Time字段) | >12周→🔴 / 4-12周→🟡 / <4周→🟢 | 🔴🟡🟢 | P0 |
| F2.2 | **库存风险** | LCSC/Mouser/DigiKey (Stock字段) | 总库存=0→🔴 / 仅1渠道有货→🟡 / ≥2渠道→🟢 | 🔴🟡🟢 | P0 |
| F2.3 | **生命周期风险** | 分销商API + 制造商状态标记 | EOL/Obsolete→🔴 / NRND→🔴 / Active→🟢 | 🔴🟢 | P0 |
| F2.4 | **供应商集中度** | 统计有现货的独立供应商数量 | 仅1家→🔴 / 2-3家→🟡 / ≥4家→🟢 | 🔴🟡🟢 | P0 |
| F2.5 | **价格趋势** | 对比历史快照与当前价格 | 涨幅>30%→🔴 / 10-30%→🟡 | 🔴🟡🟢 | P1 |
| F2.6 | **通用性评分** | MPN标准化 + AVL匹配 + 封装标准化判断 | 非标封装+单一货源→🔴 / 非标但多渠道→🟡 | 🔴🟡🟢 | P1 |
| F2.7 | **出货量风险** | 分销商库存变化趋势 | 30天内库存下降>50%→🔴 | 🔴🟡🟢 | P2 |

#### 综合风险评级规则

```
单物料综合风险 = MAX(各维度风险等级)

特殊规则：
- 生命周期=EOL → 直接🔴，无视其他维度
- 生命周期=NRND → 直接🔴（对研发BOM）
- 交期>12周 + 库存=0 → 🔴
- 仅1家供应商 + 交期>4周 → 至少🟡
```

### 4.4 M3: 监控与告警

#### F3.1 定时巡检

| 属性 | 描述 |
|------|------|
| **用户故事** | 作为项目经理，我希望能自动定期检查所有历史项目BOM的物料状态，不需要手动触发 |
| **巡检频率** | 关键物料（高风险/单货源）：每周；普通物料：每月 |
| **实现方式** | Celery定时任务 + Redis Beat Scheduler |
| **优先级** | P0 |

#### F3.2 变化检测

| 变化类型 | 检测逻辑 | 严重程度 |
|---------|---------|:---:|
| 生命周期降级 | Active→NRND 或 NRND→EOL | 🔴 紧急 |
| 交期翻倍 | 连续两次查询交期增加≥100% | 🔴 紧急 |
| 库存骤降 | 与上次快照比库存降≥50% | 🟡 警告 |
| 价格跳涨 | 单价上涨≥30% | 🟡 警告 |
| 供应商减少 | 有货供应商数减少 | 🟡 警告 |

#### F3.3 告警通知

| 渠道 | 适用场景 | 优先级 |
|------|---------|:---:|
| **邮件通知** | 所有告警 | P1 |
| **企业微信/钉钉** | 紧急告警即时推送 | P2 |
| **系统内消息中心** | 所有告警汇总查看 | P1 |

### 4.5 M4: 替代推荐

#### F4.1 同规格替代匹配

| 属性 | 描述 |
|------|------|
| **触发条件** | 物料风险等级为🔴或🟡 |
| **匹配逻辑** | ① 相同封装 + 相同/更优关键参数（电压/电流/精度/温度范围等） ② 制造商状态=Active ③ 多地有现货 |
| **数据来源** | LCSC参数搜索 + Octopart聚合 + 云汉芯城API |

#### F4.2 国产替代推荐

| 属性 | 描述 |
|------|------|
| **触发条件** | 物料为进口品牌且存在风险 |
| **匹配逻辑** | 查找同参数的国产型号，优先有现货 + 有成功替代案例 |
| **数据来源** | 云汉芯城78万国产替代关系库 + 自建AVL映射表 |

### 4.6 M5: 报告与导出

#### F5.1 风险仪表盘

- 全局风险统计：各风险等级物料数量和占比
- 项目风险排行：按风险物料占比排序
- 风险趋势图：近N期巡检的风险变化趋势
- 物料分类风险分布：按物料类别（MCU/电源/被动/连接器等）展示风险分布

#### F5.2 Excel报告导出

- 原BOM + 新增列：风险等级、交期、库存、供应商数量、替代建议
- 高风险行红色底色，中风险行黄色底色
- 支持批量生成和下载

### 4.7 M6: 物料优选库(AVL)

#### F6.1 AVL管理

- 支持手动添加/批量导入优选物料
- 自动关联物料的历史使用记录、价格区间、认证供应商
- 标记"优选"(Preferred) / "可用"(Approved) / "限制使用"(Restricted) / "禁用"(Banned)

#### F6.2 AVL物料评分模型

```
AVL Score = 0.3 × 质量分 + 0.2 × 供应稳定分 + 0.2 × 价格竞争力分 + 0.15 × 技术支持分 + 0.15 × 国产替代可行性分

质量分：来自品质部门评估/来料检验数据
供应稳定分：≥2家供应商 + 近6个月库存稳定 + 交期<8周
价格竞争力分：与同类物料中位价比
技术支持分：是否有FAE支持 / 文档完善度
国产替代可行性分：是否有已验证的国产替代型号
```

---

## 五、非功能需求

### 5.1 性能要求

| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| BOM解析响应时间 | <5秒（100行BOM） | 上传完成到页面展示 |
| 单物料查询超时 | <5秒/源 | API调用超时设置 |
| 批量查询（100行BOM） | <3分钟 | 全部物料查询+评分完成 |
| Web页面首屏加载 | <3秒 | Lighthouse Performance |
| API查询并发数 | ≥20 | 并发压力测试 |
| 数据库查询延迟 | <500ms（单表万级） | EXPLAIN ANALYZE |

### 5.2 可用性要求

| 指标 | 目标值 |
|------|--------|
| BOM解析自动列识别成功率 | ≥90% |
| 型号标准化准确率 | ≥85% |
| 风险评分误报率 | <15%（人工校验修正前） |
| 系统可用性 | ≥99%（工作时间） |

### 5.3 安全性要求

| 要求 | 说明 |
|------|------|
| BOM数据加密存储 | 数据库层面加密 |
| API Key安全存储 | 环境变量或Secret Manager |
| 访问控制 | 基于角色的访问控制(RBAC) |
| 操作审计 | 关键操作日志记录 |

### 5.4 可扩展性要求

- API数据源可插拔（新增分销商API无需改动核心逻辑）
- 风险评分规则可配置（权重和阈值通过配置文件调整）
- BOM列映射可扩展（支持自定义列名模板）

---

## 六、系统架构

### 6.1 总体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                          前端层 (React)                            │
│  BOM上传页面 │ 风险仪表盘 │ 物料详情 │ 报告中心 │ 系统配置         │
└──────────────────────────────┬───────────────────────────────────┘
                               │ REST API (JSON)
┌──────────────────────────────┴───────────────────────────────────┐
│                      后端服务层 (FastAPI)                          │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ BOM Service  │  │ Risk Engine  │  │ Alert Service │            │
│  │ - 解析       │  │ - 交期       │  │ - 定时巡检    │            │
│  │ - 标准化     │  │ - 库存       │  │ - 变化检测    │            │
│  │ - 存储       │  │ - 生命周期    │  │ - 通知推送    │            │
│  │ - 对比       │  │ - 供应商     │  │ - 告警管理    │            │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘            │
│         │                │                  │                     │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌──────┴───────┐            │
│  │ AVL Service │  │ Alternative  │  │ Report       │            │
│  │ - 优选库    │  │ Recommender  │  │ Generator    │            │
│  │ - 评分      │  │ - 同规格     │  │ - Excel      │            │
│  │ - 复用率    │  │ - 国产替代   │  │ - Dashboard  │            │
│  └─────────────┘  └──────────────┘  └──────────────┘            │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────┴───────────────────────────────────┐
│                       数据聚合层 (API Gateway)                     │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ LCSC API │  │Mouser API│  │DigiKey   │  │云汉芯城 API   │    │
│  │(免费匿名)│  │(免费注册) │  │API(OAuth)│  │(商务对接)     │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
│                    ▲                                              │
│                    │ 缓存层 (Redis)                               │
│                    │ TTL: 24h (库存) / 7天 (datasheet)           │
└──────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┴───────────────────────────────────┐
│                        数据存储层                                   │
│  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ PostgreSQL │  │  Redis   │  │  MinIO   │  │  Celery      │  │
│  │- BOM数据   │  │- 查询缓存│  │- 报告文件│  │- 定时任务    │  │
│  │- AVL库     │  │- 任务队列│  │- 上传附件│  │- 异步分析    │  │
│  │- 风险快照  │  │- Session │  │          │  │              │  │
│  └────────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 技术选型明细

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|---------|
| 后端框架 | FastAPI | ≥0.110 | 原生async、自动OpenAPI文档、类型安全 |
| ORM | SQLAlchemy 2.0+ | async模式 | 成熟、性能好、文档丰富 |
| BOM解析 | pandas + openpyxl | stable | Excel处理事实标准 |
| 型号标准化 | rapidfuzz | ≥3.0 | 比fuzzywuzzy快10倍+ |
| HTTP客户端 | httpx (AsyncClient) | ≥0.27 | asyncio原生、HTTP/2支持 |
| 数据库 | PostgreSQL | ≥16 | JSONB支持、全文搜索、窗口函数 |
| 缓存/队列 | Redis | ≥7 | 查询缓存+任务队列 |
| 任务调度 | Celery | ≥5.3 | 稳定的Python任务队列 |
| 前端框架 | React | ≥18 | 生态最丰富 |
| UI组件库 | Ant Design 5 | — | Table组件适合BOM展示 |
| 图表 | ECharts / Recharts | — | 风险仪表盘可视化 |
| 容器化 | Docker + Compose | — | 一键部署 |

---

## 七、数据模型

### 7.1 核心实体关系图

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  projects    │ 1───N │  bom_items   │ N───1 │ material_    │
│              │       │              │       │ master (AVL) │
│ id           │       │ id           │       │              │
│ name         │       │ project_id   │       │ id           │
│ version      │       │ reference_id │       │ mpn_clean    │
│ product_name │       │ mpn_raw      │       │ manufacturer │
│ status       │       │ mpn_clean    │       │ package_type │
│ created_at   │       │ manufacturer │       │ category     │
│ updated_at   │       │ description  │       │ lifecycle    │
└──────────────┘       │ package_type │       │ is_standard  │
                       │ quantity     │       │ preferred    │
                       │ category     │       │ created_at   │
                       └──────┬───────┘       └──────────────┘
                              │
                              │ 1───N
                              │
                       ┌──────┴───────┐
                       │ risk_        │
                       │ snapshots    │
                       │              │
                       │ id           │
                       │ bom_item_id  │
                       │ check_date   │
                       │ lead_time_d  │
                       │ total_stock  │
                       │ supplier_cnt │
                       │ unit_price   │
                       │ lifecycle    │
                       │ risk_level   │
                       │ risk_reasons │
                       └──────┬───────┘
                              │
                              │ 1───N
                              │
                       ┌──────┴───────┐
                       │ alerts       │
                       │              │
                       │ id           │
                       │ bom_item_id  │
                       │ alert_type   │
                       │ severity     │
                       │ message      │
                       │ is_resolved  │
                       │ resolved_at  │
                       └──────────────┘
```

### 7.2 详细表结构

```sql
-- 项目表
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    version         VARCHAR(50),
    product_name    VARCHAR(255),
    status          VARCHAR(20) DEFAULT 'active',  -- active, archived, deprecated
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- BOM物料表
CREATE TABLE bom_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    reference_id    VARCHAR(100),     -- 位号，如 R1,R2,R3
    mpn_raw         VARCHAR(255) NOT NULL,  -- 原始型号
    mpn_clean       VARCHAR(255),     -- 标准化后型号
    manufacturer    VARCHAR(100),
    description     TEXT,
    package_type    VARCHAR(50),
    quantity        INTEGER DEFAULT 1,
    category        VARCHAR(50),      -- 物料大类：MCU/电源IC/被动/连接器/...
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 物料主数据表(AVL)
CREATE TABLE material_master (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mpn_clean           VARCHAR(255) NOT NULL,
    manufacturer        VARCHAR(100),
    package_type        VARCHAR(50),
    category            VARCHAR(50),
    lifecycle_status    VARCHAR(20),  -- Active, NRND, EOL, Obsolete
    is_standard         BOOLEAN DEFAULT TRUE,
    avl_status          VARCHAR(20) DEFAULT 'approved',  -- preferred/approved/restricted/banned
    avl_score           NUMERIC(3,1),
    preferred_suppliers TEXT[],       -- 优选供应商列表
    domestic_alternatives TEXT[],     -- 国产替代型号列表
    param_json          JSONB,        -- 关键参数
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(mpn_clean, manufacturer)
);

-- 风险快照表
CREATE TABLE risk_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bom_item_id     UUID REFERENCES bom_items(id) ON DELETE CASCADE,
    check_date      TIMESTAMPTZ DEFAULT NOW(),
    lead_time_days  INTEGER,
    total_stock     INTEGER,
    supplier_count  INTEGER,
    supplier_detail JSONB,       -- [{name, stock, price, lead_time}, ...]
    unit_price      NUMERIC(10,4),
    price_trend_pct NUMERIC(5,2),
    lifecycle_status VARCHAR(20),
    risk_level      VARCHAR(10), -- critical, high, medium, low
    risk_reasons    TEXT[],      -- 风险原因列表
    overall_score   NUMERIC(3,1)
);

-- 告警表
CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bom_item_id     UUID REFERENCES bom_items(id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    alert_type      VARCHAR(50) NOT NULL,  -- eol, lead_time, stock, price, supplier
    severity        VARCHAR(10) NOT NULL,  -- critical, warning, info
    message         TEXT NOT NULL,
    is_resolved     BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_bom_items_project ON bom_items(project_id);
CREATE INDEX idx_bom_items_mpn_clean ON bom_items(mpn_clean);
CREATE INDEX idx_risk_snapshots_item ON risk_snapshots(bom_item_id);
CREATE INDEX idx_risk_snapshots_date ON risk_snapshots(check_date);
CREATE INDEX idx_alerts_project ON alerts(project_id);
CREATE INDEX idx_alerts_unresolved ON alerts(is_resolved) WHERE is_resolved = FALSE;
```

---

## 八、风险评分算法

### 8.1 算法概述

本系统采用 **加权评分 + 规则覆盖** 的混合模型，确保评分结果既有量化依据，又符合实际业务经验。

### 8.2 各维度评分细则

#### 交期风险评分

```python
def score_lead_time(lead_time_days: int) -> tuple[str, float]:
    """
    返回: (风险等级, 归一化风险分值 0-1)
    """
    if lead_time_days > 84:       # >12周
        return ('critical', 1.0)
    elif lead_time_days > 56:     # 8-12周
        return ('high', 0.8)
    elif lead_time_days > 28:     # 4-8周
        return ('medium', 0.5)
    elif lead_time_days > 0:
        return ('low', 0.2)
    else:
        return ('unknown', 0.5)  # 无法获取交期，默认中等
```

#### 库存风险评分

```python
def score_stock(total_stock: int, supplier_count: int, quantity_needed: int) -> tuple[str, float]:
    if total_stock == 0:
        return ('critical', 1.0)
    elif total_stock < quantity_needed:
        return ('high', 0.8)
    elif supplier_count == 1:
        return ('medium', 0.5)
    elif supplier_count <= 3:
        return ('low', 0.3)
    else:
        return ('low', 0.1)
```

#### 生命周期评分

```python
LIFECYCLE_SCORES = {
    'Obsolete':     ('critical', 1.0),
    'EOL':          ('critical', 1.0),
    'NRND':         ('critical', 1.0),   # 对研发BOM = 🔴
    'Last Time Buy':('critical', 0.9),
    'Not Recommended':('high', 0.7),
    'Active':       ('low', 0.1),
    'Preliminary':  ('medium', 0.4),
    'Unknown':      ('medium', 0.5),
}
```

#### 供应商集中度评分

```python
def score_supplier_concentration(count: int) -> tuple[str, float]:
    if count == 0:      return ('critical', 1.0)
    elif count == 1:    return ('high', 0.8)
    elif count <= 3:    return ('medium', 0.5)
    else:               return ('low', 0.2)
```

#### 综合评分

```python
WEIGHTS = {
    'lead_time':        0.30,
    'stock':            0.25,
    'lifecycle':        0.25,
    'supplier_count':   0.15,
    'price_trend':      0.05,
}

def calculate_overall_risk(scores: dict) -> tuple[str, float, list[str]]:
    """
    返回: (综合风险等级, 综合分值, 风险原因列表)
    """
    # 硬规则：生命周期异常直接最高风险
    if scores.get('lifecycle', {}).get('level') == 'critical':
        return ('critical', 1.0, ['物料生命周期异常: ' + scores['lifecycle']['status']])

    # 加权计算
    overall = sum(
        scores[dim]['score'] * WEIGHTS.get(dim, 0)
        for dim in scores
    )

    # 判定等级
    if overall >= 0.7:   level = 'critical'
    elif overall >= 0.4: level = 'medium'
    else:                level = 'low'

    # 汇总风险原因
    reasons = [
        scores[dim]['reason']
        for dim in scores
        if scores[dim].get('reason')
    ]

    return (level, overall, reasons)
```

---

## 九、用户界面设计要点

### 9.1 页面清单

| 页面 | 路由 | 核心组件 | 优先级 |
|------|------|---------|:---:|
| BOM上传页 | `/upload` | 拖拽上传区、列映射预览、解析结果预览 | P0 |
| 风险分析结果页 | `/analysis/:id` | 风险汇总卡片、物料明细表（可排序/筛选）、替代建议抽屉 | P0 |
| 项目列表页 | `/projects` | 项目卡片/表格、搜索、风险状态图标 | P0 |
| 项目详情页 | `/projects/:id` | BOM明细表、风险趋势图、告警历史、版本对比入口 | P1 |
| 风险仪表盘 | `/dashboard` | 统计卡片、饼图、项目风险排行、趋势折线图 | P1 |
| 物料库(AVL) | `/avl` | 物料搜索、筛选、评分编辑、替代映射 | P2 |
| 告警中心 | `/alerts` | 告警列表、处理状态、一键标记已读 | P1 |
| 报告中心 | `/reports` | 报告列表、下载、定时发送配置 | P2 |
| 系统配置 | `/settings` | API Key管理、风险阈值配置、通知设置 | P2 |

### 9.2 关键交互规范

- BOM物料表格：固定表头、水平滚动、支持按风险等级筛选、按列排序
- 风险等级颜色：🔴 `#F56C6C` / 🟡 `#E6A23C` / 🟢 `#67C23A`
- 风险原因展示：表格行hover显示Tooltip，点击展开详情抽屉
- 替代推荐：高风险物料行右侧显示"替代方案"按钮，点击弹出列表

---

## 十、实施计划与里程碑

### 10.1 整体时间线

```
Week 1-2  │ MVP: CLI工具 + LCSC API + Excel报告
Week 3-4  │ MVP完善: Mouser API接入 + 型号标准化引擎
          │ ──────────【里程碑1: MVP可用】──────────
Week 5-8  │ Web系统搭建: FastAPI后端 + PostgreSQL + 基础Web界面
Week 9-12 │ 核心功能: 历史BOM管理 + 风险仪表盘 + 定时巡检
          │ ──────────【里程碑2: 核心系统上线】──────────
Month 4-6 │ 智能功能: 替代推荐 + AVL积累 + 告警通知
          │ ──────────【里程碑3: 智能版上线】──────────
Month 7+  │ 扩展与集成: EDA/ERP插件 + 多团队协同
          │ ──────────【里程碑4: 深度集成】──────────
```

### 10.2 MVP交付物清单

| 编号 | 交付物 | 验收标准 | 状态 |
|:---:|--------|---------|:---:|
| MVP-1 | Python CLI工具 | `python bom_checker.py --input BOM.xlsx --output 报告.xlsx` 可成功执行 | ⬜ |
| MVP-2 | LCSC jlcsearch API接入 | 可查询到物料库存、价格、仓库分布 | ⬜ |
| MVP-3 | Excel报告输出 | 输出Excel含物料逐行风险等级（颜色标记）和风险原因 | ⬜ |
| MVP-4 | 型号标准化 | 至少处理TR/T&R/T/R等5种以上包装后缀 | ⬜ |
| MVP-5 | 基础风险评分 | 至少覆盖交期、库存、供应商数量3个维度 | ⬜ |

### 10.3 核心系统(阶段二)交付物

| 编号 | 交付物 | 验收标准 |
|:---:|--------|---------|
| S2-1 | Web界面 | 支持BOM上传、项目列表、风险分析结果查看 |
| S2-2 | PostgreSQL数据存储 | 历史BOM和风险快照可持久化存储和查询 |
| S2-3 | Mouser + DigiKey API | 可获取交期、生命周期状态 |
| S2-4 | 完整风险评分 | 覆盖交期/库存/生命周期/供应商/价格5个维度 |
| S2-5 | 定时巡检 | 支持配置巡检频率，自动执行并记录结果 |
| S2-6 | 风险仪表盘 | 展示全局风险统计和趋势 |

---

## 十一、成功指标

### 11.1 产品指标

| 指标 | 目标值 | 测量周期 |
|------|--------|---------|
| 活跃项目数 | ≥20个历史项目纳入管理 | 月 |
| BOM上传到报告输出时间 | ≤3分钟（100行BOM） | 每次 |
| 风险告警响应率 | ≥80%告警被标记为"已处理" | 月 |
| 物料复用率提升 | AVL物料使用率≥60% | 季度 |
| 设计变更率下降 | 因物料风险导致的设计变更减少30% | 季度 |

### 11.2 技术指标

| 指标 | 目标值 | 
|------|--------|
| 系统可用性 | ≥99%（工作时间） | 
| API查询成功率 | ≥95% | 
| 型号标准化准确率 | ≥85% | 
| 风险评分误报率 | ≤15% | 

---

## 附录A: 参考文档

| 文档 | 路径 |
|------|------|
| 行业调研报告 | [BOM物料标准化审查与交期风险评估-调研报告.md](./BOM物料标准化审查与交期风险评估-调研报告.md) |
| 实施方案 | [BOM物料风险预警系统-实施方案.md](./BOM物料风险预警系统-实施方案.md) |

## 附录B: 术语表

| 术语 | 全称 | 说明 |
|------|------|------|
| BOM | Bill of Materials | 物料清单 |
| AVL | Approved Vendor List | 合格供应商/物料优选库 |
| MPN | Manufacturer Part Number | 制造商物料编号 |
| EOL | End of Life | 生命周期终止 |
| NRND | Not Recommended for New Design | 不推荐用于新设计 |
| LTB | Last Time Buy | 最后采购窗口 |
| PCN | Product Change Notice | 产品变更通知 |
| PDN | Product Discontinuance Notice | 产品停产通知 |
| SPU | Standard Product Unit | 标准产品单元（云汉芯城术语） |
| NPI | New Product Introduction | 新产品导入 |
| YTEOL | Years to End of Life | 剩余寿命年限预测 |

---

> **文档版本**: v1.0  
> **编制日期**: 2026-06-23  
> **下次评审**: 2026-07-23
