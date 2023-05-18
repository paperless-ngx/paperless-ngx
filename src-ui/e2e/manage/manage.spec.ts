import { test, expect } from '@playwright/test'

const REQUESTS_HAR1 = 'e2e/manage/requests/api-manage1.har'
const REQUESTS_HAR2 = 'e2e/manage/requests/api-manage2.har'

test('should show a list of tags with bottom pagination as well', async ({
  page,
}) => {
  await page.routeFromHAR(REQUESTS_HAR1, { notFound: 'fallback' })
  await page.goto('/tags')
  await expect(page.getByRole('main')).toHaveText(/26 total tags/i)
  await expect(await page.locator('ngb-pagination')).toHaveCount(2)
})

test('should show a list of correspondents without bottom pagination', async ({
  page,
}) => {
  await page.routeFromHAR(REQUESTS_HAR2, { notFound: 'fallback' })
  await page.goto('/correspondents')
  await expect(page.getByRole('main')).toHaveText(/4 total correspondents/i)
  await expect(await page.locator('ngb-pagination')).toHaveCount(1)
})

test('should support quick filter Documents button', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR1, { notFound: 'fallback' })
  await page.goto('/tags')
  await page
    .getByRole('row', { name: 'Inbox' })
    .getByRole('button', { name: 'Documents' })
    .click()
  await expect(page).toHaveURL(/tags__id__all=9/)
})

test('should support item editing', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR1, { notFound: 'fallback' })
  await page.goto('/tags')
  await page
    .getByRole('row', { name: 'Inbox' })
    .getByRole('button', { name: 'Edit' })
    .click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByLabel('Name')).toHaveValue('Inbox')
  await page.getByTitle('Color').getByRole('button').click()
  const color = await page.getByLabel('Color').inputValue()

  const updatePromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid = data['color'] === color
    return (
      isValid &&
      request.method() === 'PUT' &&
      request.url().includes('/api/tags/9/')
    )
  })

  await page.getByRole('button', { name: 'Save' }).click()
  await updatePromise
})
