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
  // filter button is available before tags have loaded
  const selectedTags = page.locator('pngx-input-tags .ng-value pngx-tag')
  await expect(selectedTags).toHaveCount(2)
  await expect(
    selectedTags.getByText('Another Sample Tag', { exact: true })
  ).toBeVisible()
  await expect(selectedTags.getByText('Inbox', { exact: true })).toBeVisible()
  await page
    .getByRole('button', { name: 'Filter documents with these Tags' })
    .click()
  await expect(page).toHaveURL((url) => {
    const tags = url.searchParams.get('tags__id__all')?.split(',').sort()
    return url.pathname === '/documents' && tags?.join(',') === '1,2'
  })
  await expect(page.locator('pngx-document-list')).toHaveText(/one document/i)
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

test('should render saved notes as sanitized markdown', async ({ page }) => {
  const markdown =
    '**Bold note**\n\n- first item\n- second item\n\n[Paperless](https://example.com)\n\n<script>alert("xss")</script>'
  await page.route(
    (url) =>
      url.pathname.endsWith('/api/documents/1/') &&
      url.searchParams.get('full_perms') === 'true',
    async (route) => {
      const response = await route.fetch()
      const document = await response.json()
      await route.fulfill({
        response,
        json: {
          ...document,
          notes: [
            { id: 101, note: markdown, created: new Date().toISOString() },
          ],
        },
      })
    }
  )

  await page.goto('/documents/1/notes')

  const renderedNote = page.locator('pngx-document-notes .card-text').first()
  await expect(renderedNote.locator('strong')).toHaveText('Bold note')
  await expect(renderedNote.locator('li')).toHaveCount(2)
  await expect(
    renderedNote.getByRole('link', { name: 'Paperless' })
  ).toHaveAttribute('href', 'https://example.com')
  await expect(renderedNote.locator('script')).toHaveCount(0)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
})

test('should toggle markdown note preview and retain the draft', async ({
  page,
}) => {
  await page.route(
    (url) =>
      url.pathname.endsWith('/api/documents/1/') &&
      url.searchParams.get('full_perms') === 'true',
    async (route) => {
      const response = await route.fetch()
      const document = await response.json()
      await route.fulfill({ response, json: { ...document, notes: [] } })
    }
  )

  await page.goto('/documents/1/notes')

  const notes = page.locator('pngx-document-notes')
  const modeGroup = notes.getByRole('group', { name: 'Note input mode' })
  const editRadio = modeGroup.getByRole('radio', { name: 'Edit', exact: true })
  const previewRadio = modeGroup.getByRole('radio', {
    name: 'Preview',
    exact: true,
  })
  const editButton = modeGroup.getByText('Edit', { exact: true })
  const previewButton = modeGroup.getByText('Preview', { exact: true })
  await expect(editRadio).toBeChecked()
  await expect(previewRadio).not.toBeChecked()
  await previewButton.click()
  await expect(notes.locator('.note-preview')).toContainText(
    'Nothing to preview'
  )

  await editButton.click()
  const markdown = '**draft**\n\n- list item'
  await notes.locator('textarea').fill(markdown)
  await previewButton.click()
  const preview = notes.locator('.note-preview .markdown-preview')
  await expect(preview.locator('strong')).toHaveText('draft')
  await expect(preview.locator('li')).toHaveText('list item')
  await expect(previewRadio).toBeChecked()
  await expect(editRadio).not.toBeChecked()

  await editButton.click()
  await expect(notes.locator('textarea')).toHaveValue(markdown)
  await expect(editRadio).toBeChecked()
  await expect(previewRadio).not.toBeChecked()
  await page.unrouteAll({ behavior: 'ignoreErrors' })
})

test('should add a markdown note from preview mode', async ({ page }) => {
  const markdown = '**saved from preview**\n\n- a list item'
  let documentNotes = []
  let submittedNote: string | undefined

  await page.route(
    (url) =>
      url.pathname.endsWith('/api/documents/1/') &&
      url.searchParams.get('full_perms') === 'true',
    async (route) => {
      const response = await route.fetch()
      const document = await response.json()
      await route.fulfill({
        response,
        json: { ...document, notes: documentNotes },
      })
    }
  )
  await page.route('**/api/documents/1/notes/', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()

    submittedNote = route.request().postDataJSON().note
    documentNotes = [
      { id: 102, note: submittedNote, created: new Date().toISOString() },
    ]
    await route.fulfill({
      json: documentNotes,
    })
  })

  await page.goto('/documents/1/notes')

  const notes = page.locator('pngx-document-notes')
  const modeGroup = notes.getByRole('group', { name: 'Note input mode' })
  const editRadio = modeGroup.getByRole('radio', { name: 'Edit', exact: true })
  const previewButton = modeGroup.getByText('Preview', { exact: true })
  await notes.locator('textarea').fill(markdown)
  await previewButton.click()
  await notes.getByRole('button', { name: 'Add note', exact: true }).click()

  await expect.poll(() => submittedNote).toBe(markdown)
  const renderedNote = notes.locator('.card-text').first()
  await expect(renderedNote.locator('strong')).toHaveText('saved from preview')
  await expect(renderedNote.locator('li')).toHaveText('a list item')
  await expect(editRadio).toBeChecked()
  await expect(notes.locator('textarea')).toHaveValue('')
  await page.unrouteAll({ behavior: 'ignoreErrors' })
})
