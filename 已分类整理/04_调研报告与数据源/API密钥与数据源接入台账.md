# API 密钥与数据源接入台账

> 维护规则：每新增、恢复、替换一个外部数据源，都必须同步更新本文档和 `BOM-Risk-Analyzer-patch/backend/.env`。本文档保存在本地项目文件夹，包含敏感信息，不要外发、不要提交到公开仓库。

## 当前凭证文件

- 后端运行凭证文件：`BOM-Risk-Analyzer-patch/backend/.env`
- 示例配置文件：`BOM-Risk-Analyzer-patch/backend/.env.example`
- 代码会从后端目录下的 `.env` 读取环境变量。

## 已接入/已验证平台

| 平台 | 用途 | 认证方式 | 账号/入口 | API Key / Client 信息 | 当前状态 | 代码状态 | 备注 |
|---|---|---|---|---|---|---|---|
| DigiKey | 元器件库存、价格、交期、生命周期 | OAuth2 Client/Secret | DigiKey Developer Portal | `DIGIKEY_CLIENT_ID` 与 `DIGIKEY_CLIENT_SECRET` 已写入 `.env` | 已恢复凭证 | 已实现连接器：`backend/app/services/sources/digikey.py` | 实测曾返回库存 4034、价格 ¥54.66、生命周期在售 |
| Mouser | 元器件库存、价格、交期、生命周期 | API Key | Mouser API Hub | `MOUSER_API_KEY` 已写入 `.env` | 已恢复凭证 | 已实现连接器：`backend/app/services/sources/mouser.py` | 已修复 API Key 需放在 query string 的调用方式；当前接口实测已命中 |
| LCSC / JLCSearch | 立创库存和价格，行情热词补充 | 免认证 | JLCSearch API | 不需要 Key | 已启用 | 已实现连接器：`backend/app/services/sources/lcsc.py`；媒体源：`lcsc_jlcsearch` | 不支持真实交期和生命周期 |
| 观芯台 | 国内聚合库存、价格、交期展示 | 免登录网页抓取 | guanxintai.com | 不需要 Key | 已启用 | 已实现连接器：`backend/app/services/sources/guanxintai.py`；媒体源：`guanxintai_search` | 实测曾返回库存 93479、价格 ¥6.98；受网页结构变化影响 |
| Nexar / Octopart | 多分销商库存、价格、leadDays、生命周期扩展 | JWT，需刷新 | Nexar Portal | `.env` 已预留 `NEXAR_CLIENT_ID`、`NEXAR_CLIENT_SECRET`、`NEXAR_ACCESS_TOKEN`，当前为空 | Schema 已验证，生产连接器待接入 | 当前主代码未发现生产连接器 | 已验证字段：`totalAvail`、`medianPrice1000`、`leadDays` |
| 芯查查 | 国内元器件数据扩展 | appId/appSecret | 芯查查开放平台 | `.env` 已预留 `XINCHACHA_APP_ID`、`XINCHACHA_APP_SECRET`，当前为空 | 待 API 开通 | 未实现 | 拿到 appId 后再接入 |

## `.env` 当前变量清单

```env
DATABASE_URL=sqlite:///data/market_risk.db
DATA_DIR=data
MIN_CONFIDENCE_THRESHOLD=0.6
CROSS_VALIDATION_SOURCES=2

MOUSER_ENABLED=true
MOUSER_API_KEY=<已写入 backend/.env>

DIGIKEY_ENABLED=true
DIGIKEY_CLIENT_ID=<已写入 backend/.env>
DIGIKEY_CLIENT_SECRET=<已写入 backend/.env>

LCSC_ENABLED=true
LCSC_REQUEST_DELAY=0.55

GUANXINTAI_ENABLED=true

NEXAR_ENABLED=false
NEXAR_CLIENT_ID=
NEXAR_CLIENT_SECRET=
NEXAR_ACCESS_TOKEN=

XINCHACHA_ENABLED=false
XINCHACHA_APP_ID=
XINCHACHA_APP_SECRET=

API_QUERY_TIMEOUT=10.0
API_BATCH_CONCURRENCY=5
CACHE_TTL_SECONDS=86400
```

## 已发现的新旧文档差异

| 文件 | 问题 | 处理建议 |
|---|---|---|
| `README-PATCH.md` | 旧说明仍写 DigiKey 暂未实现 | 后续应更新为“DigiKey 已实现，需配置凭证” |
| `docs/superpowers/plans/2026-06-28-v310-multi-source-supply-data.md` | 旧实施计划曾记录真实凭证 | 后续建议改成引用本文档和 `.env`，不要在计划文档中重复明文 |
| `新增数据源API调研与接入建议.html` | 已修正为“DigiKey/Mouser/观芯台/LCSC 已实现或已验证” | 后续新增 Nexar/芯查查时继续更新 |

## 后续新增平台更新模板

新增数据源时，复制以下模板追加：

```markdown
### 平台名称

- 平台：
- 用途：
- 官网/控制台：
- 认证方式：
- 账号：
- 密钥变量名：
- 密钥是否已写入 `.env`：是/否
- 连接器文件：
- 测试文件：
- 当前状态：待申请 / 已申请 / 已实现 / 已验证 / 暂停
- 备注：
```

## 最近更新

- 2026-06-29：恢复 DigiKey、Mouser、LCSC、观芯台、Nexar、芯查查相关环境变量位；DigiKey/Mouser 真实凭证已写入 `.env`；Nexar/芯查查保留空位等待补充。
- 2026-06-29：修复供应数据 API 初始化断点，`/api/supply/query` 已恢复多源并行调起；修复 Mouser 调用方式，API Key 改为 query string 传参。
