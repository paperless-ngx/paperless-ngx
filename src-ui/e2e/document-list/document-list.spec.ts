import { expect, test } from '@playwright/test'

test('basic filtering', async ({ page }) => {
  await page.goto('/documents')
  await page.getByRole('button', { name: 'Tags' }).click()
  await page.getByRole('menuitem', { name: 'Inbox' }).click()
  await expect(page).toHaveURL(/tags__id__all=1/)
  await expect(page.locator('pngx-document-list')).toHaveText(/8 documents/)
  await page.getByRole('button', { name: 'Document type' }).click()
  await page.getByRole('menuitem', { name: /^Invoice Test/ }).click()
  await expect(page).toHaveURL(/document_type__id__in=1/)
  await expect(page.locator('pngx-document-list')).toHaveText(/3 documents/)
  await page.getByRole('button', { name: 'Reset filters' }).first().click()
  await page.getByRole('button', { name: 'Correspondent' }).click()
  await page.getByRole('menuitem', { name: 'Test Correspondent 1' }).click()
  await page.getByRole('menuitem', { name: 'Correspondent 9' }).click()
  await expect(page).toHaveURL(/correspondent__id__in=(?:1,2|2,1)/)
  await expect(page.locator('pngx-document-list')).toHaveText(/7 documents/)
  await page
    .locator('pngx-filter-editor')
    .getByTitle('Correspondent')
    .getByText('Exclude')
    .click()
  await expect(page).toHaveURL(/correspondent__id__none=(?:1,2|2,1)/)
  await expect(page.locator('pngx-document-list')).toHaveText(/54 documents/)
  // clear button
  await page.getByRole('button', { name: '2 selected', exact: true }).click()
  await expect(page.locator('pngx-document-list')).toHaveText(/61 documents/)
  await page.getByRole('button', { name: 'Storage path' }).click()
  await page.getByRole('menuitem', { name: 'Testing 12' }).click()
  await expect(page).toHaveURL(/storage_path__id__in=1/)
  await expect(page.locator('pngx-document-list')).toHaveText(/8 documents/)
  await page.getByRole('button', { name: 'Reset filters' }).first().click()
  await expect(page.locator('pngx-document-list')).toHaveText(/61 documents/)
})

test('text filtering', async ({ page }) => {
  await page.goto('/documents')
  await page.getByRole('main').getByRole('combobox').click()
  await page.getByRole('main').getByRole('combobox').fill('test')
  await expect(page.locator('pngx-document-list')).toHaveText(/32 documents/)
  await expect(page).toHaveURL(/text=test/)
  await page.getByRole('button', { name: 'Title & content' }).click()
  await page.getByRole('button', { name: 'Title', exact: true }).click()
  await expect(page.locator('pngx-document-list')).toHaveText(/9 documents/)
  await expect(page).toHaveURL(/title_search=test/)
  await page.getByRole('button', { name: 'Title', exact: true }).click()
  await page.getByRole('button', { name: 'Advanced search' }).click()
  await expect(page).toHaveURL(/query=test/)
  await expect(page.locator('pngx-document-list')).toHaveText(/32 documents/)
  await page.getByRole('button', { name: 'Advanced search' }).click()
  await page.getByRole('button', { name: 'ASN' }).click()
  await page.getByRole('main').getByRole('combobox').nth(1).fill('1123')
  await expect(page).toHaveURL(/archive_serial_number=1123/)
  await expect(page.locator('pngx-document-list')).toHaveText(/one document/i)
  await page.locator('select').selectOption('greater')
  await page.getByRole('main').getByRole('combobox').nth(1).click()
  await page.getByRole('main').getByRole('combobox').nth(1).fill('1123')
  await expect(page).toHaveURL(/archive_serial_number__gt=1123/)
  await expect(page.locator('pngx-document-list')).toHaveText(/5 documents/)
  await page.locator('select').selectOption('less')
  await expect(page).toHaveURL(/archive_serial_number__lt=1123/)
  await expect(page.locator('pngx-document-list')).toHaveText(/0 documents/)
  await page.locator('select').selectOption('is null')
  await expect(page).toHaveURL(/archive_serial_number__isnull=1/)
  await expect(page.locator('pngx-document-list')).toHaveText(/55 documents/)
  await page.locator('select').selectOption('not null')
  await expect(page).toHaveURL(/archive_serial_number__isnull=0/)
  await expect(page.locator('pngx-document-list')).toHaveText(/6 documents/)
})

test('date filtering', async ({ page }) => {
  await page.goto('/documents')
  await page.getByRole('button', { name: 'Dates' }).click()
  await page.locator('.ng-arrow-wrapper').first().click()
  await page.getByRole('option', { name: 'Within 3 months' }).click()
  await expect(page.locator('pngx-document-list')).toHaveText(/one document/i)
  await page
    .getByRole('menuitem', { name: 'Relative dates' })
    .locator('span')
    .first()
    .click()
  await page.getByRole('option', { name: 'Within 3 months' }).click()
  await page.getByLabel('Dates selected').locator('button').first().click()
  await page.getByLabel('Dates selected').locator('button').first().click()
  const createdFrom = page.getByRole('textbox', { name: 'mm/dd/yyyy' }).first()
  await createdFrom.fill('12/11/2022')
  await createdFrom.press('Enter')
  await page.getByRole('button', { name: 'Title & content' }).click()
  await expect(page.locator('pngx-document-list')).toHaveText(/3 documents/)
})

test('sorting', async ({ page }) => {
  await page.goto('/documents')
  await page.getByRole('button', { name: 'Sort' }).click()
  await page.getByRole('button', { name: 'ASN' }).click()
  await expect(page).toHaveURL(/sort=archive_serial_number/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page
    .locator('pngx-page-header')
    .getByRole('button', { name: 'Correspondent' })
    .click()
  await expect(page).toHaveURL(/sort=correspondent__name/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page.getByRole('button', { name: 'Title', exact: true }).click()
  await expect(page).toHaveURL(/sort=title/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page
    .locator('pngx-page-header')
    .getByRole('button', { name: 'Document type' })
    .click()
  await expect(page).toHaveURL(/sort=document_type__name/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page.getByRole('button', { name: 'Created', exact: true }).click()
  await expect(page).toHaveURL(/sort=created/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page.getByRole('button', { name: 'Added', exact: true }).click()
  await expect(page).toHaveURL(/sort=added/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page.getByRole('button', { name: 'Modified' }).click()
  await expect(page).toHaveURL(/sort=modified/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page.getByRole('button', { name: 'Notes' }).click()
  await expect(page).toHaveURL(/sort=num_notes/)
  await page.getByRole('button', { name: 'Sort' }).click()
  await page.locator('.w-100 > label > i-bs').first().click()
  await expect(page).not.toHaveURL(/reverse=1/)
})

test('change views', async ({ page }) => {
  await page.goto('/documents')
  await page.locator('.btn-group > label').first().click()
  await expect(page.locator('pngx-document-list table')).toBeVisible()
  await page.locator('label:nth-child(4)').first().click()
  await expect(page.locator('pngx-document-card-small').first()).toBeAttached()
  await page.locator('label:nth-child(6)').click()
  await expect(page.locator('pngx-document-card-large').first()).toBeAttached()
})

test('bulk edit', async ({ page }) => {
  await page.goto('/documents')

  await page
    .locator('pngx-document-card-small .doc-img-container')
    .nth(0)
    .click()
  await page
    .locator('pngx-document-card-small .doc-img-container')
    .nth(3)
    .click({
      modifiers: ['Shift'],
    })

  await expect(page.locator('pngx-document-list')).toHaveText(
    /Selected 4 of 61 documents/i
  )

  await page.getByRole('button', { name: 'Page' }).click()
  await expect(page.locator('pngx-document-list')).toHaveText(
    /Selected 50 of 61 documents/i
  )
  await page.getByRole('button', { name: 'All' }).click()
  await expect(page.locator('pngx-document-list')).toHaveText(
    /Selected 61 of 61 documents/i
  )
  await page.getByRole('button', { name: 'None' }).click()

  await page
    .locator('pngx-document-card-small .doc-img-container')
    .nth(1)
    .click()
  await page
    .locator('pngx-document-card-small .doc-img-container')
    .nth(2)
    .click()

  await page.getByRole('button', { name: 'Tags' }).click()
  await page
    .getByRole('textbox', { name: 'Filter tags' })
    .fill('TagWithPartial')
  await page.getByRole('menuitem', { name: 'TagWithPartial' }).click()

  await page.getByRole('button', { name: 'Apply' }).click()

  const bulkEditPromise = page.waitForRequest((request) => {
    const postData = request.postDataJSON()
    let isValid = postData['method'] == 'modify_tags'
    isValid = isValid && postData['parameters']['add_tags'].includes(3)
    return request.url().toString().includes('bulk_edit') && isValid
  })

  await page.getByRole('button', { name: 'Confirm' }).click()
  await bulkEditPromise
})
