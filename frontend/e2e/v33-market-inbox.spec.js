import { expect, test } from '@playwright/test'

test('v3.3 market inbox identifies raw notice and shows affected BOM summary', async ({ page }) => {
  await page.goto('/#/market-inbox')

  await expect(page.getByRole('heading', { name: '行情情报收件箱' })).toBeVisible()
  await page.getByTestId('market-notice-title').fill('TDK高容MLCC缺货涨价通知')
  await page.getByTestId('market-notice-source-name').fill('TDK代理商邮件')
  await page.getByTestId('market-notice-raw-text').fill('TDK 高容MLCC C3225X5R1A226M250AC 缺货，预计涨价 10%-20%，交期延长至 16 周，即日起执行。')
  await page.getByTestId('market-notice-submit').click()

  await expect(page.getByTestId('market-inbox-result')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('TDK').first()).toBeVisible()
  await expect(page.getByText('high_cap_mlcc').first()).toBeVisible()
  await expect(page.getByText('auto_confirmed').first()).toBeVisible()
  await expect(page.getByText(/受影响项目/).first()).toBeVisible()
})
