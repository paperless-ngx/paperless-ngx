import { DOCUMENT } from '@angular/common';
import { Inject, Injectable, LOCALE_ID, Renderer2, RendererFactory2 } from '@angular/core';
import { Meta } from '@angular/platform-browser';
import { CookieService } from 'ngx-cookie-service';

export interface PaperlessSettings {
  key: string
  type: string
  default: any
}

export interface LanguageOption {
  code: string
  name: string
  englishName?: string

  /**
   * A date format string for use by the date selectors. MUST contain 'yyyy', 'mm' and 'dd'.
   */
  dateInputFormat?: string
}

export const SETTINGS_KEYS = {
  BULK_EDIT_CONFIRMATION_DIALOGS: 'general-settings:bulk-edit:confirmation-dialogs',
  BULK_EDIT_APPLY_ON_CLOSE: 'general-settings:bulk-edit:apply-on-close',
  DOCUMENT_LIST_SIZE: 'general-settings:documentListSize',
  DARK_MODE_USE_SYSTEM: 'general-settings:dark-mode:use-system',
  DARK_MODE_ENABLED: 'general-settings:dark-mode:enabled',
  DARK_MODE_THUMB_INVERTED: 'general-settings:dark-mode:thumb-inverted',
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
  {key: SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED, type: "boolean", default: true},
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
    private meta: Meta,
    @Inject(LOCALE_ID) private localeId: string
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
      {code: "en-us", name: $localize`English (US)`, englishName: "English (US)", dateInputFormat: "mm/dd/yyyy"},
      {code: "en-gb", name: $localize`English (GB)`, englishName: "English (GB)", dateInputFormat: "dd/mm/yyyy"},
      {code: "de-de", name: $localize`German`, englishName: "German", dateInputFormat: "dd.mm.yyyy"},
      {code: "nl-nl", name: $localize`Dutch`, englishName: "Dutch", dateInputFormat: "dd-mm-yyyy"},
      {code: "fr-fr", name: $localize`French`, englishName: "French", dateInputFormat: "dd/mm/yyyy"},
      {code: "pt-pt", name: $localize`Portuguese`, englishName: "Portuguese", dateInputFormat: "dd/mm/yyyy"},
      {code: "pt-br", name: $localize`Portuguese (Brazil)`, englishName: "Portuguese (Brazil)", dateInputFormat: "dd/mm/yyyy"},
      {code: "it-it", name: $localize`Italian`, englishName: "Italian", dateInputFormat: "dd/mm/yyyy"},
      {code: "ro-ro", name: $localize`Romanian`, englishName: "Romanian", dateInputFormat: "dd.mm.yyyy"},
      {code: "ru-ru", name: $localize`Russian`, englishName: "Russian", dateInputFormat: "dd.mm.yyyy"},
      {code: "es-es", name: $localize`Spanish`, englishName: "Spanish", dateInputFormat: "dd/mm/yyyy"},
      {code: "pl-pl", name: $localize`Polish`, englishName: "Polish", dateInputFormat: "dd.mm.yyyy"},
      {code: "sv-se", name: $localize`Swedish`, englishName: "Swedish", dateInputFormat: "yyyy-mm-dd"},
      {code: "lb-lu", name: $localize`Luxembourgish`, englishName: "Luxembourgish", dateInputFormat: "dd.mm.yyyy"}
    ]
  }

  getDateLocaleOptions(): LanguageOption[] {
    let isoOption: LanguageOption = {code: "iso-8601", name: $localize`ISO 8601`, dateInputFormat: "yyyy-mm-dd"}
    return [isoOption].concat(this.getLanguageOptions())
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

  getLocalizedDateInputFormat(): string {
    let dateLocale = this.get(SETTINGS_KEYS.DATE_LOCALE) || this.getLanguage() || this.localeId.toLowerCase()
    return this.getDateLocaleOptions().find(o => o.code == dateLocale)?.dateInputFormat || "yyyy-mm-dd"
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
