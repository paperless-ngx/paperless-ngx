import { expect, test } from '@playwright/test'
import path from 'node:path'

const REQUESTS_HAR = path.join(__dirname, 'requests/api-document-detail.har')
const REQUESTS_HAR2 = path.join(__dirname, 'requests/api-document-detail2.har')

test('should activate / deactivate save button when changes are saved', async ({
  page,
}) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/documents/175/')
  await page.waitForSelector('pngx-document-detail pngx-input-text:first-child')
  await expect(page.getByTitle('Storage path', { exact: true })).toHaveText(
    /\w+/
  )
  await expect(page.getByRole('button', { name: 'Save' }).nth(1)).toBeDisabled()
  await page.getByTitle('Storage path').getByTitle('Clear all').click()
  await expect(page.getByRole('button', { name: 'Save' }).nth(1)).toBeEnabled()
})

test('should warn on unsaved changes', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/documents/175/')
  await expect(page.getByTitle('Correspondent', { exact: true })).toHaveText(
    /\w+/
  )
  await expect(page.getByRole('button', { name: 'Save' }).nth(1)).toBeDisabled()
  await page
    .getByTitle('Storage path', { exact: true })
    .getByTitle('Clear all')
    .click()
  await expect(page.getByRole('button', { name: 'Save' }).nth(1)).toBeEnabled()
  await page.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveText(/unsaved changes/)
  await page.getByRole('button', { name: 'Cancel' }).click()
  await page.getByRole('link', { name: 'Close all' }).click()
  await expect(page.getByRole('dialog')).toHaveText(/unsaved changes/)
})

test('should support tab direct navigation', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/documents/175/details')
  await expect(page.getByRole('tab', { name: 'Details' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/175/content')
  await expect(page.getByRole('tab', { name: 'Content' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/175/metadata')
  await expect(page.getByRole('tab', { name: 'Metadata' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/175/notes')
  await expect(page.getByRole('tab', { name: 'Notes' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/175/permissions')
  await expect(page.getByRole('tab', { name: 'Permissions' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
})

test('should show a mobile preview', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/documents/175/')
  await page.setViewportSize({ width: 400, height: 1000 })
  await expect(page.getByRole('tab', { name: 'Preview' })).toBeVisible()
  await page.getByRole('tab', { name: 'Preview' }).click()
  await page.waitForSelector('pdf-viewer')
})

test('should show a list of notes', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/documents/175/notes')
  await expect(page.locator('pngx-document-notes')).toBeVisible()
  await expect(
    await page.getByRole('button', {
      name: /delete note/i,
      includeHidden: true,
    })
  ).toHaveCount(4)
})

test('should support quick filters', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR2, { notFound: 'fallback' })
  await page.goto('/documents/175/details')
  await page
    .getByRole('button', { name: 'Filter documents with these Tags' })
    .click()
  await expect(page).toHaveURL(/tags__id__all=4&sort=created&reverse=1&page=1/)
})
