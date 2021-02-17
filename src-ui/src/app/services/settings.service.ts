import { DOCUMENT } from '@angular/common';
import { Inject, Injectable, Renderer2, RendererFactory2 } from '@angular/core';
import { Meta } from '@angular/platform-browser';
import { CookieService } from 'ngx-cookie-service';

export interface PaperlessSettings {
  key: string
  type: string
  default: any
}

export interface LanguageOption {
  code: string,
  name: string,
  englishName?: string
}

export const SETTINGS_KEYS = {
  BULK_EDIT_CONFIRMATION_DIALOGS: 'general-settings:bulk-edit:confirmation-dialogs',
  BULK_EDIT_APPLY_ON_CLOSE: 'general-settings:bulk-edit:apply-on-close',
  DOCUMENT_LIST_SIZE: 'general-settings:documentListSize',
  DARK_MODE_USE_SYSTEM: 'general-settings:dark-mode:use-system',
  DARK_MODE_ENABLED: 'general-settings:dark-mode:enabled',
  USE_NATIVE_PDF_VIEWER: 'general-settings:document-details:native-pdf-viewer',
  DATE_LOCALE: 'general-settings:date-display:date-locale',
  DATE_FORMAT: 'general-settings:date-display:date-format',
  NOTIFICATIONS_CONSUMER_NEW_DOCUMENT: 'general-settings:notifications:consumer-new-documents',
  NOTIFICATIONS_CONSUMER_SUCCESS: 'general-settings:notifications:consumer-success',
  NOTIFICATIONS_CONSUMER_FAILED: 'general-settings:notifications:consumer-failed',
  NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD: 'general-settings:notifications:consumer-suppress-on-dashboard',
}

const SETTINGS: PaperlessSettings[] = [
  {key: SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS, type: "boolean", default: true},
  {key: SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE, type: "boolean", default: false},
  {key: SETTINGS_KEYS.DOCUMENT_LIST_SIZE, type: "number", default: 50},
  {key: SETTINGS_KEYS.DARK_MODE_USE_SYSTEM, type: "boolean", default: true},
  {key: SETTINGS_KEYS.DARK_MODE_ENABLED, type: "boolean", default: false},
  {key: SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, type: "boolean", default: false},
  {key: SETTINGS_KEYS.DATE_LOCALE, type: "string", default: ""},
  {key: SETTINGS_KEYS.DATE_FORMAT, type: "string", default: "mediumDate"},
  {key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT, type: "boolean", default: true},
  {key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS, type: "boolean", default: true},
  {key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED, type: "boolean", default: true},
  {key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD, type: "boolean", default: true},
]

@Injectable({
  providedIn: 'root'
})
export class SettingsService {

  private renderer: Renderer2;

  constructor(
    private rendererFactory: RendererFactory2,
    @Inject(DOCUMENT) private document,
    private cookieService: CookieService,
    private meta: Meta
  ) {
    this.renderer = rendererFactory.createRenderer(null, null);

    this.updateDarkModeSettings()
  }

  updateDarkModeSettings(): void {
    let darkModeUseSystem = this.get(SETTINGS_KEYS.DARK_MODE_USE_SYSTEM)
    let darkModeEnabled = this.get(SETTINGS_KEYS.DARK_MODE_ENABLED)

    if (darkModeUseSystem) {
      this.renderer.addClass(this.document.body, 'color-scheme-system')
      this.renderer.removeClass(this.document.body, 'color-scheme-dark')
    } else {
      this.renderer.removeClass(this.document.body, 'color-scheme-system')
      darkModeEnabled ? this.renderer.addClass(this.document.body, 'color-scheme-dark') : this.renderer.removeClass(this.document.body, 'color-scheme-dark')
    }

  }

  getLanguageOptions(): LanguageOption[] {
    return [
      {code: "en-us", name: $localize`English (US)`, englishName: "English (US)"},
      {code: "en-gb", name: $localize`English (GB)`, englishName: "English (GB)"},
      {code: "de", name: $localize`German`, englishName: "German"},
      {code: "nl", name: $localize`Dutch`, englishName: "Dutch"},
      {code: "fr", name: $localize`French`, englishName: "French"}
    ]
  }

  private getLanguageCookieName() {
    let prefix = ""
    if (this.meta.getTag('name=cookie_prefix')) {
      prefix = this.meta.getTag('name=cookie_prefix').content
    }
    return `${prefix || ''}django_language`
  }

  getLanguage(): string {
    return this.cookieService.get(this.getLanguageCookieName())
  }

  setLanguage(language: string) {
    if (language) {
      this.cookieService.set(this.getLanguageCookieName(), language)
    } else {
      this.cookieService.delete(this.getLanguageCookieName())
    }
  }

  get(key: string): any {
    let setting = SETTINGS.find(s => s.key == key)

    if (!setting) {
      return null
    }

    let value = localStorage.getItem(key)

    if (value != null) {
      switch (setting.type) {
        case "boolean":
          return JSON.parse(value)
        case "number":
          return +value
        case "string":
          return value
        default:
          return value
      }
    } else {
      return setting.default
    }
  }

  set(key: string, value: any) {
    localStorage.setItem(key, value.toString())
  }

  unset(key: string) {
    localStorage.removeItem(key)
  }
}
