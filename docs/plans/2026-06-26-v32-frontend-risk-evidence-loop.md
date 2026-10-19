# v3.2 Frontend Risk Evidence Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 BOM 分析结果页形成 v3.2 最小前端闭环：展示双轨风险、依据链、处置建议，并允许采购/工程人员快速录入人工行情事件触发后续重分析。

**Architecture:** 保持现有 Vue 3 + Element Plus 页面结构不大改。新增两个聚焦组件：`V32EvidencePanel.vue` 负责行级 v3.2 风险解释；`ManualEventQuickAdd.vue` 负责人工事件录入。`RiskDetailTable.vue` 在明细表中增加 v3.2 列和依据链弹层；`BomAnalyze.vue` 在单文件分析结果区加入人工事件入口并扩展 CSV 导出字段。

**Tech Stack:** Vue 3 `<script setup>`、Element Plus、Axios API wrapper、Vitest + Vue Test Utils、Vite build。

## Global Constraints

- 不引入新的前端依赖，复用 Element Plus 与现有 Axios client。
- 不改变后端 API 路径，人工事件使用已存在的 `POST /api/events/manual`。
- v3.2 字段不存在时必须兼容旧分析结果，页面不能报错。
- 单一公众号/媒体传闻只负责录入，是否强预警由后端可信度模型决定，前端只展示后端返回的 review/confidence 结果。
- CSV 导出必须保持 UTF-8 BOM，兼容 Excel 中文打开。
- 部署脚本继续支持 `-TargetProject` 参数，避免硬编码中文路径。

---

## File Structure

- Create: `frontend/src/components/V32EvidencePanel.vue`
  - 单行 v3.2 风险解释面板，输入 BOM 行对象，展示品类、主导轨道、评分、依据摘要、行动建议、依据链节点。
- Create: `frontend/src/components/ManualEventQuickAdd.vue`
  - 人工行情事件快速录入表单，输入可选 `defaultItem`，提交后调用 `addManualEvent(payload)`，成功后向父组件 emit。
- Create: `frontend/src/components/__tests__/V32EvidencePanel.test.js`
  - 验证 v3.2 面板展示核心字段，并兼容无 v3.2 数据。
- Create: `frontend/src/components/__tests__/ManualEventQuickAdd.test.js`
  - 验证人工事件表单会发出 `submitted` 事件并展示后端置信度建议。
- Modify: `frontend/src/components/RiskDetailTable.vue`
  - 增加 v3.2 风险列、依据链按钮/弹层、orange 风险等级映射。
- Modify: `frontend/src/views/BomAnalyze.vue`
  - 增加人工事件快速录入卡片；选择高风险/关注行预填品牌品类；扩展 CSV 导出 v3.2 字段。
- Modify: `deploy-v3.2-mvp.ps1`
  - 复制前端新增/修改文件和组件测试；在目标 frontend 存在 package.json 时运行 `npm run build`。
- Modify: `README.md`, `README-V3.2-MVP.md`, `GIT-HANDOFF.md`
  - 补充前端闭环能力和验证结果。

---

### Task 1: v3.2 Evidence Panel

**Files:**
- Create: `frontend/src/components/__tests__/V32EvidencePanel.test.js`
- Create: `frontend/src/components/V32EvidencePanel.vue`

**Interfaces:**
- Consumes: BOM line item object with optional fields `v32_category_display`, `v32_primary_track`, `v32_risk_level`, `v32_risk_score`, `v32_evidence_summary`, `v32_action_suggestion`, `v32_evidence_chain`.
- Produces: A visual panel that renders all above fields and falls back to “暂无 v3.2 依据链数据”.

- [ ] **Step 1: Write the failing test**

```js
import { mount } from '@vue/test-utils'
import V32EvidencePanel from '../V32EvidencePanel.vue'

describe('V32EvidencePanel', () => {
  it('renders v3.2 risk summary, action suggestion and evidence nodes', () => {
    const wrapper = mount(V32EvidencePanel, {
      props: {
        item: {
          v32_category_display: '高容MLCC',
          v32_primary_track: 'demand_supply',
          v32_risk_level: 'orange',
          v32_risk_score: 72,
          v32_evidence_summary: '高容MLCC当前为orange风险，主导轨道为demand_supply。',
          v32_action_suggestion: '建议锁定库存并确认替代料。',
          v32_evidence_chain: [
            { type: 'category', title: '品类识别', detail: '识别为高容MLCC' },
            { type: 'market_event', title: '市场事件', detail: 'TDK缺货涨价通知' }
          ]
        }
      }
    })

    expect(wrapper.text()).toContain('高容MLCC')
    expect(wrapper.text()).toContain('需求/供应轨')
    expect(wrapper.text()).toContain('72')
    expect(wrapper.text()).toContain('建议锁定库存并确认替代料')
    expect(wrapper.text()).toContain('品类识别')
    expect(wrapper.text()).toContain('TDK缺货涨价通知')
  })

  it('renders empty-state text when no v3.2 evidence exists', () => {
    const wrapper = mount(V32EvidencePanel, { props: { item: {} } })
    expect(wrapper.text()).toContain('暂无 v3.2 依据链数据')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/components/__tests__/V32EvidencePanel.test.js`
Expected: FAIL because `V32EvidencePanel.vue` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement a focused panel using computed display helpers for track/risk labels and evidence list rendering.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/components/__tests__/V32EvidencePanel.test.js`
Expected: PASS.

---

### Task 2: Manual Event Quick Add

**Files:**
- Create: `frontend/src/components/__tests__/ManualEventQuickAdd.test.js`
- Create: `frontend/src/components/ManualEventQuickAdd.vue`

**Interfaces:**
- Consumes: optional `defaultItem` with `raw_brand`, `normalized_category`, `v32_category`, `raw_part_number`.
- Uses: `addManualEvent(payload)` from `../api/events`.
- Emits: `submitted` with response data after successful POST.

- [ ] **Step 1: Write the failing test**

```js
import { mount, flushPromises } from '@vue/test-utils'
import ManualEventQuickAdd from '../ManualEventQuickAdd.vue'
import { addManualEvent } from '../../api/events'

vi.mock('../../api/events', () => ({
  addManualEvent: vi.fn()
}))

describe('ManualEventQuickAdd', () => {
  it('submits a manual price increase and emits backend review result', async () => {
    addManualEvent.mockResolvedValueOnce({
      data: {
        status: 'ok',
        review_recommendation: 'auto_confirm',
        confidence_reason: '人工确认且含涨价缺货事实'
      }
    })

    const wrapper = mount(ManualEventQuickAdd, {
      props: {
        defaultItem: {
          raw_brand: 'TDK',
          v32_category: 'high_cap_mlcc',
          raw_part_number: 'C3216X5R1A226M'
        }
      }
    })

    await wrapper.find('[data-test="manual-event-title"]').setValue('TDK高容MLCC缺货涨价通知')
    await wrapper.find('[data-test="manual-event-increase"]').setValue('20')
    await wrapper.find('[data-test="manual-event-submit"]').trigger('click')
    await flushPromises()

    expect(addManualEvent).toHaveBeenCalledWith(expect.objectContaining({
      title: 'TDK高容MLCC缺货涨价通知',
      brand: 'TDK',
      category: 'high_cap_mlcc',
      event_type: 'price_increase',
      increase_max_pct: 20,
      confirmed_by_user: true
    }))
    expect(wrapper.emitted('submitted')).toHaveLength(1)
    expect(wrapper.text()).toContain('auto_confirm')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/components/__tests__/ManualEventQuickAdd.test.js`
Expected: FAIL because component does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement title, brand, category, event_type, increase_max_pct, lead_time_weeks, shortage_confirmed, confirmed_by_user inputs and submit state.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/components/__tests__/ManualEventQuickAdd.test.js`
Expected: PASS.

---

### Task 3: Integrate v3.2 Fields into BOM Result UI

**Files:**
- Modify: `frontend/src/components/RiskDetailTable.vue`
- Modify: `frontend/src/views/BomAnalyze.vue`

**Interfaces:**
- `RiskDetailTable.vue` imports `V32EvidencePanel.vue`.
- `BomAnalyze.vue` imports `ManualEventQuickAdd.vue` and listens for `submitted`.

- [ ] **Step 1: Add v3.2 table column**

In `RiskDetailTable.vue`, add a column labelled `v3.2风险` that displays `v32_risk_level`, `v32_risk_score`, `v32_primary_track`, and a popover containing `V32EvidencePanel`.

- [ ] **Step 2: Add orange mappings**

Update tag helpers to map `orange` to Element Plus `warning` and display `🟠 较高`.

- [ ] **Step 3: Add manual event card to single-file result**

In `BomAnalyze.vue`, render `ManualEventQuickAdd` after `RiskSummary` for single-file results. Preselect the first red/orange/yellow item where available.

- [ ] **Step 4: Extend CSV export**

Add CSV columns `v3.2品类,v3.2主导轨道,v3.2风险等级,v3.2评分,v3.2依据摘要,v3.2处置建议`.

- [ ] **Step 5: Verify build**

Run: `npm run build`
Expected: Vite build succeeds.

---

### Task 4: Deploy Script and Handoff

**Files:**
- Modify: `deploy-v3.2-mvp.ps1`
- Modify: `README.md`
- Modify: `README-V3.2-MVP.md`
- Modify: `GIT-HANDOFF.md`

**Interfaces:**
- Deploy script copies frontend components, views, tests from patch repo to target WorkBuddy project.
- Deploy script runs backend syntax/tests and frontend build.

- [ ] **Step 1: Copy frontend files in deploy script**

Add copy commands for:
- `frontend/src/components/V32EvidencePanel.vue`
- `frontend/src/components/ManualEventQuickAdd.vue`
- `frontend/src/components/RiskDetailTable.vue`
- `frontend/src/views/BomAnalyze.vue`
- `frontend/src/components/__tests__/*.test.js`

- [ ] **Step 2: Run frontend build during deploy**

If `frontend/package.json` exists, run `npm run build` from target frontend folder.

- [ ] **Step 3: Run full verification**

Run:
- `py -3.11 -m pytest tests -q`
- `npm test -- --run`
- `npm run build`

- [ ] **Step 4: Commit and regenerate bundle**

Run:
```powershell
git add .
git commit -m "feat: add v3.2 frontend risk evidence loop"
git bundle create "..\BOM-Risk-Analyzer-v3.2-mvp.bundle" --all
git bundle verify "..\BOM-Risk-Analyzer-v3.2-mvp.bundle"
```
