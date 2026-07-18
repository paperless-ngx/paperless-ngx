import { Injectable, OnDestroy } from '@angular/core'
import {
  DOCUMENT_LIST_SERVICE,
  OPEN_DOCUMENT_SERVICE,
} from '../data/storage-keys'
import { locationReload, setLocationHref } from '../utils/navigation'

const IDENTITY_CHANGE_STORAGE_KEY = 'paperless-account-session-changed'
const IDENTITY_CHANGE_PENDING_KEY =
  'paperless-account-session-change-notification'
const IDENTITY_CHANGE_ANNOUNCED_KEY =
  'paperless-account-session-change-announced'

export type IdentityChangeReason = 'logout'

interface IdentityChangePayload {
  changed: string
  reason?: IdentityChangeReason
}

@Injectable({
  providedIn: 'root',
})
export class IdentityChangeService implements OnDestroy {
  private channel?: BroadcastChannel
  private lastHandledChangeId?: string

  /** Handles identity-change events delivered through local storage. */
  private readonly storageListener = (event: StorageEvent) => {
    if (event.key === IDENTITY_CHANGE_STORAGE_KEY) {
      this.handleExternalIdentityChange(this.parsePayload(event.newValue))
    }
  }

  /** Subscribes to cross-tab identity-change notifications. */
  constructor() {
    try {
      if (typeof BroadcastChannel !== 'undefined') {
        this.channel = new BroadcastChannel(IDENTITY_CHANGE_STORAGE_KEY)
        this.channel.onmessage = (event) =>
          this.handleExternalIdentityChange(this.parsePayload(event.data))
      }
    } catch (error) {
      console.warn('Unable to initialize account-switch notifications', error)
    }
    window.addEventListener('storage', this.storageListener)
  }

  /** Releases the cross-tab notification listeners. */
  ngOnDestroy(): void {
    window.removeEventListener('storage', this.storageListener)
    this.channel?.close()
  }

  /** Broadcasts an identity change and returns its unique event ID. */
  announce(reason?: IdentityChangeReason): string {
    const payload: IdentityChangePayload = {
      changed: `${Date.now()}-${Math.random()}`,
      ...(reason ? { reason } : {}),
    }
    try {
      this.channel?.postMessage(payload)
    } catch (error) {
      console.warn('Unable to broadcast an account switch', error)
    }
    try {
      localStorage.setItem(IDENTITY_CHANGE_STORAGE_KEY, JSON.stringify(payload))
    } catch (error) {
      console.warn('Unable to persist an account-switch notification', error)
    }
    return payload.changed
  }

  /** Removes browser state that must not leak between accounts. */
  clearUserState(): void {
    try {
      sessionStorage.removeItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)
      localStorage.removeItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
    } catch (error) {
      console.warn('Unable to clear account-specific browser state', error)
    }
  }

  /** Broadcasts an identity change and navigates to its server response. */
  finish(redirectUrl: string): void {
    this.clearUserState()
    const reason = this.reasonFromUrl(
      new URL(redirectUrl, window.location.origin)
    )
    const changeId = this.announce(reason)
    try {
      sessionStorage.setItem(IDENTITY_CHANGE_ANNOUNCED_KEY, changeId)
    } catch (error) {
      console.warn('Unable to track an account-switch notification', error)
    }
    setLocationHref(redirectUrl)
  }

  /** Consumes a completed identity change and returns its notification reason. */
  handleReturnFromAccountChange(): IdentityChangeReason | null {
    const url = new URL(window.location.href)
    const returnedFromChange = url.searchParams.get('account_switched') === '1'
    const pendingChange = this.getPendingChange()
    if (!returnedFromChange && pendingChange === null) return null

    const reason = returnedFromChange
      ? this.reasonFromUrl(url)
      : pendingChange?.reason
    if (returnedFromChange) {
      url.searchParams.delete('account_switched')
      url.searchParams.delete('account_switch_reason')
      window.history.replaceState({}, '', url.toString())
    }
    this.clearUserState()
    this.clearPendingChange()

    let alreadyAnnounced = false
    try {
      alreadyAnnounced = Boolean(
        sessionStorage.getItem(IDENTITY_CHANGE_ANNOUNCED_KEY)
      )
      sessionStorage.removeItem(IDENTITY_CHANGE_ANNOUNCED_KEY)
    } catch (error) {
      console.warn('Unable to consume an account-switch notification', error)
    }
    if (returnedFromChange && !alreadyAnnounced) {
      this.announce(reason)
    }
    return reason ?? null
  }

  /** Reads a supported identity-change reason from a redirect URL. */
  private reasonFromUrl(url: URL): IdentityChangeReason | undefined {
    return url.searchParams.get('account_switch_reason') === 'logout'
      ? 'logout'
      : undefined
  }

  /** Parses and validates a cross-tab identity-change payload. */
  private parsePayload(value: unknown): IdentityChangePayload | null {
    if (typeof value === 'string') {
      try {
        return this.parsePayload(JSON.parse(value))
      } catch {
        return value ? { changed: value } : null
      }
    }
    if (
      typeof value !== 'object' ||
      value === null ||
      typeof (value as IdentityChangePayload).changed !== 'string'
    ) {
      return null
    }
    const payload = value as IdentityChangePayload
    return {
      changed: payload.changed,
      ...(payload.reason === 'logout' ? { reason: payload.reason } : {}),
    }
  }

  /** Returns an identity change waiting to be shown after a reload. */
  private getPendingChange(): IdentityChangePayload | null {
    try {
      return this.parsePayload(
        sessionStorage.getItem(IDENTITY_CHANGE_PENDING_KEY)
      )
    } catch (error) {
      console.warn('Unable to read an account-switch notification', error)
      return null
    }
  }

  /** Removes a consumed cross-tab identity-change notification. */
  private clearPendingChange(): void {
    try {
      sessionStorage.removeItem(IDENTITY_CHANGE_PENDING_KEY)
    } catch (error) {
      console.warn('Unable to clear an account-switch notification', error)
    }
  }

  /** Stores an external identity change and reloads the stale tab. */
  private handleExternalIdentityChange(
    payload: IdentityChangePayload | null
  ): void {
    if (payload === null || payload.changed === this.lastHandledChangeId) return
    this.lastHandledChangeId = payload.changed
    try {
      sessionStorage.setItem(
        IDENTITY_CHANGE_PENDING_KEY,
        JSON.stringify(payload)
      )
    } catch (error) {
      console.warn('Unable to store an account-switch notification', error)
    }
    this.clearUserState()
    locationReload()
  }
}
