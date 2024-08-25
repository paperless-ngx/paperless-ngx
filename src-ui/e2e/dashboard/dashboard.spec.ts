import { test, expect } from '@playwright/test'

const REQUESTS_HAR1 = 'e2e/dashboard/requests/api-dashboard1.har'
const REQUESTS_HAR2 = 'e2e/dashboard/requests/api-dashboard2.har'
const REQUESTS_HAR3 = 'e2e/dashboard/requests/api-dashboard3.har'
const REQUESTS_HAR4 = 'e2e/dashboard/requests/api-dashboard4.har'

test('dashboard inbox link', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR1, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await page.getByRole('link', { name: 'Documents in inbox' }).click()
  await expect(page).toHaveURL(/tags__id__in=9/)
  await expect(page.locator('pngx-document-list')).toHaveText(/8 documents/)
})

test('dashboard total documents link', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR2, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await page.getByRole('link').filter({ hasText: 'Total documents' }).click()
  await expect(page).toHaveURL(/documents/)
  await expect(page.locator('pngx-document-list')).toHaveText(/61 documents/)
  await page.getByRole('button', { name: 'Reset filters' })
})

test('dashboard saved view show all', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR3, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await page
    .locator('pngx-widget-frame')
    .filter({ hasText: 'Inbox' })
    .getByRole('link', { name: 'Show all' })
    .first()
    .click()
  await expect(page).toHaveURL(/view\/7/)
  await expect(page.locator('pngx-document-list')).toHaveText(/8 documents/)
})

test('dashboard saved view document links', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR4, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await page
    .locator('pngx-widget-frame')
    .filter({ hasText: 'Inbox' })
    .locator('table')
    .getByRole('link', { name: /test/ })
    .first()
    .click({ position: { x: 0, y: 0 } })
  await expect(page).toHaveURL(/documents\/310\/details/)
})

test('test slim sidebar', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR1, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await page.locator('#sidebarMenu').getByRole('button').click()
  await expect(
    page.getByRole('link', { name: 'Dashboard' }).getByText('Dashboard')
  ).toBeHidden()
  await page.locator('#sidebarMenu').getByRole('button').click()
  await expect(
    page.getByRole('link', { name: 'Dashboard' }).getByText('Dashboard')
  ).toBeVisible()
})
