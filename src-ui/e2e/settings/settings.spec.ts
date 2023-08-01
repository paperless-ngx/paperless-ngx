import { test, expect } from '@playwright/test'

const REQUESTS_HAR = 'e2e/settings/requests/api-settings.har'
const REQUESTS_HAR2 = 'e2e/settings/requests/api-settings2.har'
const REQUESTS_HAR3 = 'e2e/settings/requests/api-settings3.har'
const REQUESTS_HAR_SSO_NOTHING =
  'e2e/settings/requests/api-settings-ssogroup-nothing.har'
const REQUESTS_HAR_SSO_VIEW =
  'e2e/settings/requests/api-settings-ssogroup-view.har'
const REQUESTS_HAR_SSO_CHANGE =
  'e2e/settings/requests/api-settings-ssogroup-change.har'
const REQUESTS_HAR_SSO_CREATE =
  'e2e/settings/requests/api-settings-ssogroup-create.har'
const REQUESTS_HAR_SSO_DELETE =
  'e2e/settings/requests/api-settings-ssogroup-delete.har'

test('should not be able to do anything', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR_SSO_NOTHING, { notFound: 'fallback' })
  await page.goto('/settings/usersgroups')
  await expect(page.getByTestId('list-ssogroups')).toHaveCount(0)
})

test('should list three sso groups and no buttons', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR_SSO_VIEW, { notFound: 'fallback' })
  await page.goto('/settings/usersgroups')
  const sso_table = page.getByTestId('list-ssogroups')
  await expect(sso_table.getByRole('listitem')).toHaveCount(4) // 3 + header
  await expect(sso_table.getByRole('button', { name: 'edit' })).toHaveCount(0) // No edit
  await expect(sso_table.getByRole('button', { name: 'delete' })).toHaveCount(0) // No delete
  await expect(page.getByRole('button', { name: 'Add SSO Group' })).toHaveCount(
    0
  ) // No add
})

test('should be able to edit sso_group', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR_SSO_CHANGE, { notFound: 'fallback' })
  await page.goto('/settings/usersgroups')
  const sso_table = page.getByTestId('list-ssogroups')
  await expect(sso_table.getByRole('listitem')).toHaveCount(4) // 3 + header
  await expect(sso_table.getByRole('button', { name: 'edit' })).toHaveCount(3) // Only edit
  await expect(sso_table.getByRole('button', { name: 'delete' })).toHaveCount(0) // No delete
  await expect(page.getByRole('button', { name: 'Add SSO Group' })).toHaveCount(
    0
  ) // No add
  await sso_table.getByRole('button', { name: 'edit' }).first().click() // Delete a group
  await expect(page.getByRole('dialog')).toHaveCount(1) // Expect dialog
  await page.getByRole('combobox').click()
  await page.getByRole('option', { name: 'guest' }).click()
  await page.getByLabel('Name', { exact: true }).fill('new_guest')
  const updatePromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid =
      data['name'] == 'new_guest' && data['group'] == 2 && data['id'] == 2
    return (
      request.method() === 'PUT' && request.url().includes('/api/sso_groups/1')
    )
  })
  await page.getByRole('button', { name: 'save' }).click()
  await updatePromise
})

test('should be able to delete sso_group', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR_SSO_DELETE, { notFound: 'fallback' })
  await page.goto('/settings/usersgroups')
  const sso_table = page.getByTestId('list-ssogroups')
  await expect(sso_table.getByRole('listitem')).toHaveCount(4) // 3 + header
  await expect(sso_table.getByRole('button', { name: 'edit' })).toHaveCount(0) // No edit
  await expect(sso_table.getByRole('button', { name: 'delete' })).toHaveCount(3) // Only delete
  await expect(page.getByRole('button', { name: 'Add SSO Group' })).toHaveCount(
    0
  ) // No add
  await sso_table.getByRole('button', { name: 'delete' }).first().click() // Delete a group
  await expect(page.getByRole('dialog')).toHaveCount(1) // Expect dialog
  const updatePromise = page.waitForRequest((request) => {
    return (
      request.method() === 'DELETE' &&
      request.url().includes('/api/sso_groups/1')
    )
  })
  await page.getByRole('button', { name: 'proceed' }).click()
  await updatePromise // Should receive delete request
})

test('should be able to create sso_group', async ({ page }) => {
  await page.routeFromHAR(REQUESTS_HAR_SSO_CREATE, { notFound: 'fallback' })
  await page.goto('/settings/usersgroups')
  const sso_table = page.getByTestId('list-ssogroups')
  await expect(sso_table.getByRole('listitem')).toHaveCount(4) // 3 + header
  await expect(sso_table.getByRole('button', { name: 'edit' })).toHaveCount(0) // No edit
  await expect(sso_table.getByRole('button', { name: 'delete' })).toHaveCount(0) // No delete
  await expect(page.getByRole('button', { name: 'Add SSO Group' })).toHaveCount(
    1
  ) // Only add
  await page.getByRole('button', { name: 'Add SSO Group' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(1)
  await page.getByRole('combobox').click()
  await page.getByRole('option', { name: 'admin' }).click()
  await page.getByLabel('Name', { exact: true }).fill('admin_v2')
  const updatePromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid = data['name'] == 'admin_v2' && data['group'] == 1
    return (
      isValid &&
      request.method() === 'POST' &&
      request.url().includes('/api/sso_groups/')
    )
  })
  await page.getByRole('button', { name: 'save' }).click()
  await updatePromise
})

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
  await expect(page.locator('body')).toHaveClass(/color-scheme-system/)
  await page.getByLabel('Use system setting').click()
  await page.getByLabel('Enable dark mode').click()
  await expect(page.locator('body')).toHaveClass(/color-scheme-dark/)
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

test('should show a list of mail accounts & support creation', async ({
  page,
}) => {
  await page.routeFromHAR(REQUESTS_HAR2, { notFound: 'fallback' })
  await page.goto('/settings/mail')
  await expect(
    page.getByRole('listitem').filter({ hasText: 'imap.gmail.com' })
  ).toHaveCount(1)
  await expect(
    page.getByRole('listitem').filter({ hasText: 'imap.domain.com' })
  ).toHaveCount(1)
  await page.getByRole('button', { name: /Add Account/ }).click()
  await expect(page.getByRole('dialog')).toHaveCount(1)
  await page.getByLabel('Name', { exact: true }).fill('Test Account')
  await page.getByLabel('IMAP Server', { exact: true }).fill('imap.server.com')
  await page.getByLabel('IMAP Port', { exact: true }).fill('993')
  await page.getByLabel('Username', { exact: true }).fill('username')
  await page.getByLabel('Password', { exact: true }).fill('password')
  const createPromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid = data['imap_server'] === 'imap.server.com'
    return (
      isValid &&
      request.method() === 'POST' &&
      request.url().includes('/api/mail_accounts/')
    )
  })
  await page.getByRole('button', { name: 'Save' }).click()
  await createPromise
})

test('should show a list of mail rules & support creation', async ({
  page,
}) => {
  await page.routeFromHAR(REQUESTS_HAR3, { notFound: 'fallback' })
  await page.goto('/settings/mail')
  await expect(
    page.getByRole('listitem').filter({ hasText: 'domain' })
  ).toHaveCount(2)
  await expect(
    page.getByRole('listitem').filter({ hasText: 'gmail' })
  ).toHaveCount(2)
  await page.getByRole('button', { name: /Add Rule/ }).click()
  await expect(page.getByRole('dialog')).toHaveCount(1)
  await page.getByLabel('Name', { exact: true }).fill('Test Rule')
  await page.getByTitle('Account').locator('span').first().click()
  await page.getByRole('option', { name: 'gmail' }).click()
  await page.getByLabel('Maximum age (days)').fill('0')
  const createPromise = page.waitForRequest((request) => {
    const data = request.postDataJSON()
    const isValid = data['name'] === 'Test Rule'
    return (
      isValid &&
      request.method() === 'POST' &&
      request.url().includes('/api/mail_rules/')
    )
  })
  await page.getByRole('button', { name: 'Save' }).scrollIntoViewIfNeeded()
  await page.getByRole('button', { name: 'Save' }).click()
  await createPromise
})
