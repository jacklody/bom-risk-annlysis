import { expect, test } from '@playwright/test'

test('v3.4 preferred library page is independent and shows governance result', async ({ page }) => {
  await page.goto('/#/preferred-library')
  await expect(page.getByRole('heading', { name: '优选库治理' })).toBeVisible()
  await expect(page.getByText('不与 BOM 风险页混合展示')).toBeVisible()
  await page.getByTestId('bom-project-id').fill('1')
  await expect(page.getByTestId('run-selection-review')).toBeVisible()
})
