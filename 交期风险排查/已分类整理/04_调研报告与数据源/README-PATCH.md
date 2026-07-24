# BOM物料风险预警系统 v0.3 — 补丁部署说明

从 v0.2（纯行情事件匹配）升级到 v0.3（集成实时数据源）。

---

## 改动文件清单

### 新增文件（直接复制到对应目录）

| 源文件 | 目标位置 |
|--------|---------|
| `backend/app/services/sources/__init__.py` | `backend/app/services/sources/__init__.py` |
| `backend/app/services/sources/base.py` | `backend/app/services/sources/base.py` |
| `backend/app/services/sources/lcsc.py` | `backend/app/services/sources/lcsc.py` |
| `backend/app/services/sources/mouser.py` | `backend/app/services/sources/mouser.py` |
| `backend/app/services/supply_data.py` | `backend/app/services/supply_data.py` |
| `backend/.env.example` | `backend/.env` (复制后修改) |

### 覆盖更新（替换原有文件）

| 文件 | 改动说明 |
|------|---------|
| `backend/app/config.py` | 新增 mouser_api_key、lcsc_enabled 等配置项 |
| `backend/app/services/supply_risk.py` | 新增 realtime_data/通用性评分参数，评分逻辑增强 |
| `backend/app/api/risk_analysis.py` | 集成 SupplyDataService 批量 API 查询 |
| `backend/app/models/bom.py` | BomItem 新增 total_stock/supplier_count/lead_time_days/unit_price/lifecycle_status/commonality_score |
| `backend/app/database.py` | 新增 auto-migration 补全 v3 字段 |

---

## 部署步骤

### 1. 复制文件

```powershell
# 将 patch 目录下的新文件复制到 BOM-Risk-Analyzer 项目中
$SRC = "d:\1项目清单\交期风险排查\BOM-Risk-Analyzer-patch"
$DST = "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer"

# 新文件
Copy-Item "$SRC\backend\app\services\sources\*" "$DST\backend\app\services\sources\" -Force
Copy-Item "$SRC\backend\app\services\supply_data.py" "$DST\backend\app\services\"
Copy-Item "$SRC\backend\.env.example" "$DST\backend\.env"

# 覆盖文件（谨慎！建议先备份原文件）
Copy-Item "$SRC\backend\app\config.py" "$DST\backend\app\" -Force
Copy-Item "$SRC\backend\app\services\supply_risk.py" "$DST\backend\app\services\" -Force
Copy-Item "$SRC\backend\app\api\risk_analysis.py" "$DST\backend\app\api\" -Force
Copy-Item "$SRC\backend\app\models\bom.py" "$DST\backend\app\models\" -Force
Copy-Item "$SRC\backend\app\database.py" "$DST\backend\app\" -Force
```

### 2. 配置 API Key

编辑 `backend/.env`:

```env
# Mouser API Key（免费注册：https://www.mouser.com/api-search/）
MOUSER_API_KEY=your-key-here

# LCSC 免费免认证，无需配置
LCSC_ENABLED=true

# 可选：DigiKey API
# DIGIKEY_CLIENT_ID=
# DIGIKEY_CLIENT_SECRET=
# DIGIKEY_ENABLED=false
```

**如果没有 Mouser API Key**：系统仍可运行，仅 LCSC 数据源生效（库存+价格）。

### 3. 启动验证

```powershell
cd D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

健康检查：`http://127.0.0.1:8001/api/health`

上传 BOM 后调用 `POST /api/risk/analyze/{id}` 即可看到：
- 每行物料增加 **实时库存、供应商数、交期天数、单价、生命周期、通用性评分** 字段
- 风险原因会包含 API 查询结果（如"交期84天(>12周)"、"所有渠道均无现货库存"）

### 4. 退回 v0.2

如果新版有问题，只需要将数据库 `backend\data\market_risk.db` 中的 bom_items 表新增的 v3 字段删除即可（或直接用旧版代码+旧数据库启动）。

---

## 架构变化

```
v0.2 流程:
  BOM上传 → 市场事件匹配 → 品类启发式规则 → 风险评分

v0.3 流程:
  BOM上传 → 市场事件匹配 ──────────────────┐
           → LCSC API 查询 ─┐               ├→ 综合风险评分
           → Mouser API 查询 ┤→ SupplyDataService ←─ 通用性评分
                             └→ 实时交期/库存/生命周期
```

---

## 已知限制

1. LCSC jlcsearch API 不返回交期和生命周期，这两个维度依赖 Mouser API
2. Mouser API 需要免费注册获取 Key（如果不配则只用 LCSC）
3. 当前无缓存层，每次分析都会重新查询 API（100行BOM约需 55秒 LCSC + 并行 Mouser）
4. DigiKey API 暂未实现

---

## 支持的 API 数据维度

| 维度 | LCSC | Mouser | 说明 |
|------|:---:|:---:|------|
| 实时库存 | ✅ | ✅ | 汇总三仓(LCSC) / 全球仓(Mouser) |
| 工厂交期(天) | ❌ | ✅ | Mouser Availability 文本解析 |
| 阶梯价格 | ✅ | ✅ | 统一为 {qty, price, currency} |
| 生命周期 | ❌ | ✅ | Active/NRND/EOL/Obsolete |
| 数据手册 | ✅ | ✅ | PDF 直链 |
| 基础物料标记 | ✅ | ❌ | JLCPCB 基础库标记 |