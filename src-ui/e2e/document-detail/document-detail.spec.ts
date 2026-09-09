import { expect, test } from '@playwright/test'

test('should activate / deactivate save button when changes are saved', async ({
  page,
}) => {
  await page.goto('/documents/1/')
  await page.waitForSelector('pngx-document-detail pngx-input-text:first-child')
  await expect(page.getByTitle('Storage path', { exact: true })).toHaveText(
    /\w+/
  )
  await expect(page.getByRole('button', { name: 'Save' }).nth(1)).toBeDisabled()
  await page.getByTitle('Storage path').getByTitle('Clear all').click()
  await expect(page.getByRole('button', { name: 'Save' }).nth(1)).toBeEnabled()
})

test('should warn on unsaved changes', async ({ page }) => {
  await page.goto('/documents/1/')
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
  await page.getByRole('button', { name: 'Close all' }).click()
  await expect(page.getByRole('dialog')).toHaveText(/unsaved changes/)
})

test('should support tab direct navigation', async ({ page }) => {
  await page.goto('/documents/1/details')
  await expect(page.getByRole('tab', { name: 'Details' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/1/content')
  await expect(page.getByRole('tab', { name: 'Content' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/1/metadata')
  await expect(page.getByRole('tab', { name: 'Metadata' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/1/notes')
  await expect(page.getByRole('tab', { name: 'Notes' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/documents/1/permissions')
  await expect(page.getByRole('tab', { name: 'Permissions' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
})

test('should show a mobile preview', async ({ page }) => {
  await page.goto('/documents/1/')
  await page.setViewportSize({ width: 400, height: 1000 })
  await expect(page.getByRole('tab', { name: 'Preview' })).toBeVisible()
  await page.getByRole('tab', { name: 'Preview' }).click()
  await page.waitForSelector('pngx-pdf-viewer')
})

test('should show a list of notes', async ({ page }) => {
  await page.goto('/documents/1/notes')
  await expect(page.locator('pngx-document-notes')).toBeVisible()
  await expect(
    await page.getByRole('button', {
      name: /delete note/i,
      includeHidden: true,
    })
  ).toHaveCount(4)
})

test('should support quick filters', async ({ page }) => {
  await page.goto('/documents/1/details')
  await page
    .getByRole('button', { name: 'Filter documents with these Tags' })
    .click()
  await expect(page).toHaveURL(
    /tags__id__all=2,1&sort=created&reverse=1&page=1/
  )
})

test('should finish reloading the preview after a remote document update', async ({
  page,
}) => {
  let previewRequestCount = 0
  page.on('request', (request) => {
    if (request.url().includes('/api/documents/1/preview/')) {
      previewRequestCount++
    }
  })
  await page.goto('/documents/1/details')

  await page.locator('pngx-document-detail').waitFor()
  await expect(page.getByTitle('Storage path', { exact: true })).toHaveText(
    /\w+/
  )
  const previewWasLoaded = await page.evaluate(() => {
    const detail = document.querySelector('pngx-document-detail')
    const component = (window as any).ng.getComponent(detail)
    component.pdfPreviewLoaded({ numPages: 1 })
    return component.previewLoaded()
  })
  expect(previewWasLoaded).toBe(true)
  const previewRequestsBeforeReload = previewRequestCount

  await expect
    .poll(() =>
      page.evaluate(() => {
        const detail = document.querySelector('pngx-document-detail')
        return (window as any).ng.getComponent(detail).networkActive()
      })
    )
    .toBe(false)
  const documentReloaded = page.waitForResponse(
    (response) =>
      response.url().includes('/api/documents/1/?full_perms=true') &&
      response.request().method() === 'GET'
  )
  await page.evaluate(() => {
    const detail = document.querySelector('pngx-document-detail')
    const component = (window as any).ng.getComponent(detail)
    component.handleIncomingDocumentUpdated({
      document_id: 1,
      modified: '2099-07-26T20:00:00Z',
    })
  })
  await documentReloaded
  await expect
    .poll(() => previewRequestCount)
    .toBeGreaterThan(previewRequestsBeforeReload)
  await expect
    .poll(() =>
      page.evaluate(() => {
        const detail = document.querySelector('pngx-document-detail')
        return (window as any).ng.getComponent(detail).previewLoaded()
      })
    )
    .toBe(true)
})
