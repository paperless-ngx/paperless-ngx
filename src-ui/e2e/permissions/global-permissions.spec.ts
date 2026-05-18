import { expect, test } from '@playwright/test'
import path from 'node:path'

const REQUESTS_HAR = path.join(__dirname, 'requests/api-global-permissions.har')

test('should not allow user to edit settings', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(page.getByRole('link', { name: 'Settings' })).not.toBeAttached()
  await page.goto('/settings')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})

test('should not allow user to view documents', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(
    page.locator('nav').getByRole('link', { name: 'Documents' })
  ).not.toBeAttached()
  await page.goto('/documents')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
  await page.goto('/documents/1')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})

test('should not allow user to view correspondents', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(
    page.getByRole('link', { name: 'Attributes' })
  ).not.toBeAttached()
  await page.goto('/attributes/correspondents')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})

test('should not allow user to view tags', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(
    page.getByRole('link', { name: 'Attributes' })
  ).not.toBeAttached()
  await page.goto('/attributes/tags')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})

test('should not allow user to view document types', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(
    page.getByRole('link', { name: 'Attributes' })
  ).not.toBeAttached()
  await page.goto('/attributes/documenttypes')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})

test('should not allow user to view storage paths', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(
    page.getByRole('link', { name: 'Attributes' })
  ).not.toBeAttached()
  await page.goto('/attributes/storagepaths')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})

test('should not allow user to view logs', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(page.getByRole('link', { name: 'Logs' })).not.toBeAttached()
  await page.goto('/logs')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})

test('should not allow user to view tasks', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/dashboard')
  await expect(page.getByRole('link', { name: 'Tasks' })).not.toBeAttached()
  await page.goto('/tasks')
  await expect(page.locator('body')).toHaveText(
    /You don't have permissions to do that/i
  )
})
