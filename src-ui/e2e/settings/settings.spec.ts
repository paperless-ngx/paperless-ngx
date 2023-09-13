import { test, expect } from '@playwright/test'

const REQUESTS_HAR = 'e2e/settings/requests/api-settings.har'

test('should post settings on save', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/settings')
  await page.getByLabel('Use system setting').click()
  await page.getByRole('button', { name: 'Save' }).scrollIntoViewIfNeeded()
  const updatePromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid = data['settings'] != null
    return (
      isValid &&
      request.method() === 'POST' &&
      request.url().includes('/api/ui_settings/')
    )
  })
  await page.getByRole('button', { name: 'Save' }).click()
  await updatePromise
})

test('should activate / deactivate save button when settings change', async ({
  page,
}) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/settings')
  await expect(page.getByRole('button', { name: 'Save' })).toBeDisabled()
  await page.getByLabel('Use system setting').click()
  await page.getByRole('button', { name: 'Save' }).scrollIntoViewIfNeeded()
  await expect(page.getByRole('button', { name: 'Save' })).toBeEnabled()
})

test('should warn on unsaved changes', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/settings')
  await page.getByLabel('Use system setting').click()
  await page.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.getByRole('dialog')).toHaveText(/unsaved changes/)
  await page.getByRole('button', { name: 'Cancel' }).click()
  await page.getByLabel('Use system setting').click()
  await page.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('should apply appearance changes when set', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/settings')
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', /auto/)
  await page.getByLabel('Use system setting').click()
  await page.getByLabel('Enable dark mode').click()
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', /dark/)
})

test('should toggle saved view options when set & saved', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/settings/savedviews')
  await page.getByLabel('Show on dashboard').first().click()
  await page.getByLabel('Show in sidebar').first().click()
  const updatePromise = page.waitForRequest((request) => {
    if (!request.url().includes('8')) return true // skip other saved views
    const data = request.postDataJSON()
    const isValid =
      data['show_on_dashboard'] === true && data['show_in_sidebar'] === true
    return (
      isValid &&
      request.method() === 'PATCH' &&
      request.url().includes('/api/saved_views/')
    )
  })
  await page.getByRole('button', { name: 'Save' }).scrollIntoViewIfNeeded()
  await page.getByRole('button', { name: 'Save' }).click()
  await updatePromise
})

test('should support tab direct navigation', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR, { notFound: 'fallback' })
  await page.goto('/settings/general')
  await expect(page.getByRole('tab', { name: 'General' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/settings/notifications')
  await expect(
    page.getByRole('tab', { name: 'Notifications' })
  ).toHaveAttribute('aria-selected', 'true')
  await page.goto('/settings/savedviews')
  await expect(page.getByRole('tab', { name: 'Saved Views' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/settings/mail')
  await expect(page.getByRole('tab', { name: 'Mail' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await page.goto('/settings/usersgroups')
  await expect(
    page.getByRole('tab', { name: 'Users & Groups' })
  ).toHaveAttribute('aria-selected', 'true')
})
