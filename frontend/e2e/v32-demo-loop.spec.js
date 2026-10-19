import { expect, test } from '@playwright/test'
import path from 'node:path'

const sampleBomPath = path.resolve('../demo/sample-bom-v32.csv')

test('v3.2 demo loop uploads BOM, adds manual event, reanalyzes and shows evidence', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'BOM 风险分析' })).toBeVisible()

  const fileInput = page.locator('[data-testid="bom-file-input"] input[type="file"]')
  await fileInput.setInputFiles(sampleBomPath)

  const projectNameInput = page
    .getByTestId('project-name-input')
    .locator('input')
    .or(page.getByPlaceholder('项目名称（选填，默认用文件名）'))
  await projectNameInput.fill('v3.2 E2E 验收样例')
  await page.getByTestId('start-analyze-button').click()

  await expect(page.getByRole('heading', { name: '分析完成' })).toBeVisible({ timeout: 45_000 })
  await expect(page.getByText('6 个物料已分析')).toBeVisible()
  await expect(page.getByTestId('risk-detail-table').or(page.getByRole('table').first())).toBeVisible()
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

  await page.getByTestId('reanalyze-current-bom').or(page.getByRole('button', { name: '重新分析当前BOM' })).click()
  await expect(page.getByRole('heading', { name: '分析完成' })).toBeVisible({ timeout: 45_000 })
  await expect(page.getByText('TDK').first()).toBeVisible()
  await expect(page.getByText('需求/供应轨').or(page.getByText('材料传导轨')).or(page.getByText('信息不足')).first()).toBeVisible()
  await expect(page.getByTestId('v32-risk-button').first()).toBeVisible()
  await expect(page.getByTestId('matched-events-button').first()).toBeVisible({ timeout: 20_000 })
})
