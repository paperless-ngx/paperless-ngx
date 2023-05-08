import { test, expect } from '@playwright/test'

const REQUESTS_HAR = 'e2e/tasks/requests/api-tasks.har'

test('should show a list of dismissable tasks in tabs', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/tasks')
  await expect(page.getByRole('tab', { name: /Failed/ })).toHaveText(/1/)
  await expect(
    page.getByRole('cell').filter({ hasText: 'Dismiss' })
  ).toHaveCount(1)
  await expect(page.getByRole('tab', { name: /Complete/ })).toHaveText(/8/)
  await page.getByRole('tab', { name: /Complete/ }).click()
  await expect(
    page.getByRole('cell').filter({ hasText: 'Dismiss' })
  ).toHaveCount(8)
  await page.getByRole('tab', { name: /Started/ }).click()
  await expect(
    page.getByRole('cell').filter({ hasText: 'Dismiss' })
  ).toHaveCount(0)
  await page.getByRole('tab', { name: /Queued/ }).click()
  await expect(
    page.getByRole('cell').filter({ hasText: 'Dismiss' })
  ).toHaveCount(0)
})

test('should support dismissing tasks', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/tasks')
  await page.getByRole('tab', { name: /Failed/ }).click()
  const dismissPromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid = Array.isArray(data['tasks']) && data['tasks'].includes(255)
    return (
      isValid &&
      request.method() === 'POST' &&
      request.url().includes('/api/acknowledge_tasks/')
    )
  })
  await page
    .getByRole('button', { name: 'Dismiss', exact: true })
    .first()
    .click()
  await dismissPromise
})

test('should support dismiss all tasks', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/tasks')
  await expect(page.getByRole('button', { name: 'Dismiss all' })).toBeEnabled()
  await page.getByRole('button', { name: 'Dismiss all' }).click()
  const dismissPromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid = Array.isArray(data['tasks'])
    return (
      isValid &&
      request.method() === 'POST' &&
      request.url().includes('/api/acknowledge_tasks/')
    )
  })
  await page.getByRole('button', { name: /Dismiss/ }).click()
  await dismissPromise
})

test('should warn on dismiss all tasks', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/tasks')
  await expect(page.getByRole('button', { name: 'Dismiss all' })).toBeEnabled()
  await page.getByRole('button', { name: 'Dismiss all' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(1)
})
