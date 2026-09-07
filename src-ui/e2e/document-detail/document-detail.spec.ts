import { expect, test } from '@playwright/test'

for (const width of [1440, 390]) {
  test(`should save a selected title suggestion explicitly at ${width}px`, async ({
    page,
  }) => {
    const documentId = width === 1440 ? 60 : 61
    const apiUrl = `http://localhost:8001/api/documents/${documentId}/`
    const currentTitle = `document ${documentId}`
    const suggestedTitle = `Suggested title ${documentId}`

    // Keep AI responses deterministic while using the real editor and save API.
    await page.route('**/api/ui_settings/', async (route) => {
      const response = await route.fetch()
      const settings = await response.json()
      settings.settings.ai_enabled = true
      await route.fulfill({ response, json: settings })
    })
    await page.route(
      `**/api/documents/${documentId}/ai_suggestions/`,
      (route) =>
        route.fulfill({
          json: {
            title: suggestedTitle,
            tags: [],
            suggested_tags: [],
            correspondents: [],
            suggested_correspondents: [],
            document_types: [],
            suggested_document_types: [],
            storage_paths: [],
            suggested_storage_paths: [],
            dates: [],
          },
        })
    )

    await page.setViewportSize({ width, height: 1000 })
    await page.goto(`/documents/${documentId}/details`)
    const title = page.locator('pngx-input-text[formcontrolname="title"]')
    await expect(title.locator('input')).toHaveValue(currentTitle)
    await page.getByRole('button', { name: 'Suggest', exact: true }).click()
    await title.getByText(suggestedTitle, { exact: true }).click()
    await expect(title.locator('input')).toHaveValue(suggestedTitle)

    const headers = { Referer: page.url() }
    const beforeSave = await page.request.get(apiUrl, { headers })
    expect((await beforeSave.json()).title).toBe(currentTitle)
    try {
      const saved = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === new URL(apiUrl).pathname &&
          response.request().method() === 'PATCH'
      )
      await page
        .getByRole('button', { name: 'Save', exact: true })
        .first()
        .click()
      expect((await saved).ok()).toBe(true)
      await page.reload()
      await expect(title.locator('input')).toHaveValue(suggestedTitle)
    } finally {
      const restored = await page.request.patch(apiUrl, {
        headers,
        data: { title: currentTitle },
      })
      expect(restored.ok()).toBe(true)
    }
  })
}

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
