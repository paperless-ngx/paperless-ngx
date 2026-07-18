import {
  DOCUMENT_LIST_SERVICE,
  OPEN_DOCUMENT_SERVICE,
} from '../data/storage-keys'
import * as navUtils from '../utils/navigation'
import { IdentityChangeService } from './identity-change.service'

describe('IdentityChangeService', () => {
  let service: IdentityChangeService

  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    service = new IdentityChangeService()
  })

  afterEach(() => {
    service.ngOnDestroy()
    window.history.replaceState({}, '', '/')
    jest.restoreAllMocks()
  })

  it('clears account-specific browser state before redirecting', () => {
    sessionStorage.setItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS, 'documents')
    localStorage.setItem(
      DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG,
      'view-config'
    )
    const redirectSpy = jest
      .spyOn(navUtils, 'setLocationHref')
      .mockImplementation(() => {})

    service.finish('/next-account')

    expect(sessionStorage.getItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)).toBeNull()
    expect(
      localStorage.getItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
    ).toBeNull()
    expect(redirectSpy).toHaveBeenCalledWith('/next-account')
  })

  it('removes the one-time switch marker on return', () => {
    window.history.pushState({}, '', '/?account_switched=1')
    sessionStorage.setItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS, 'documents')

    const reason = service.handleReturnFromAccountChange()

    expect(window.location.search).toBe('')
    expect(sessionStorage.getItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)).toBeNull()
    expect(reason).toBeNull()
  })

  it('returns the logout reason and removes it from the URL', () => {
    window.history.pushState(
      {},
      '',
      '/?account_switched=1&account_switch_reason=logout'
    )

    const reason = service.handleReturnFromAccountChange()

    expect(reason).toBe('logout')
    expect(window.location.search).toBe('')
  })

  it('does not announce the same change again after finishing it', () => {
    const redirectSpy = jest
      .spyOn(navUtils, 'setLocationHref')
      .mockImplementation(() => {})
    const announceSpy = jest.spyOn(service, 'announce')
    const redirectUrl = '/?account_switched=1&account_switch_reason=logout'

    service.finish(redirectUrl)
    window.history.pushState({}, '', redirectUrl)
    const reason = service.handleReturnFromAccountChange()

    expect(redirectSpy).toHaveBeenCalledWith(redirectUrl)
    expect(announceSpy).toHaveBeenCalledTimes(1)
    expect(announceSpy).toHaveBeenCalledWith('logout')
    expect(reason).toBe('logout')
  })

  it('clears tab-local state and retains the reason from another tab', () => {
    sessionStorage.setItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS, 'documents')
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})
    const payload = JSON.stringify({
      changed: 'change-id',
      reason: 'logout',
    })

    window.dispatchEvent(
      new StorageEvent('storage', {
        key: 'paperless-account-session-changed',
        newValue: payload,
      })
    )

    expect(sessionStorage.getItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)).toBeNull()
    expect(reloadSpy).toHaveBeenCalled()
    expect(service.handleReturnFromAccountChange()).toBe('logout')
  })

  it('ignores duplicate cross-tab notifications', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})
    const event = new StorageEvent('storage', {
      key: 'paperless-account-session-changed',
      newValue: JSON.stringify({ changed: 'change-id', reason: 'logout' }),
    })

    window.dispatchEvent(event)
    window.dispatchEvent(event)

    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })
})
