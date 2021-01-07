import { DOCUMENT } from '@angular/common';
import { Inject, Injectable, Renderer2, RendererFactory2 } from '@angular/core';

export interface PaperlessSettings {
  key: string
  type: string
  default: any
}

export const SETTINGS_KEYS = {
  BULK_EDIT_CONFIRMATION_DIALOGS: 'general-settings:bulk-edit:confirmation-dialogs',
  BULK_EDIT_APPLY_ON_CLOSE: 'general-settings:bulk-edit:apply-on-close',
  DOCUMENT_LIST_SIZE: 'general-settings:documentListSize',
  DARK_MODE_USE_SYSTEM: 'general-settings:dark-mode:use-system',
  DARK_MODE_ENABLED: 'general-settings:dark-mode:enabled'
}

const SETTINGS: PaperlessSettings[] = [
  {key: SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS, type: "boolean", default: true},
  {key: SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE, type: "boolean", default: false},
  {key: SETTINGS_KEYS.DOCUMENT_LIST_SIZE, type: "number", default: 50},
  {key: SETTINGS_KEYS.DARK_MODE_USE_SYSTEM, type: "boolean", default: true},
  {key: SETTINGS_KEYS.DARK_MODE_ENABLED, type: "boolean", default: false}
]

@Injectable({
  providedIn: 'root'
})
export class SettingsService {

  private renderer: Renderer2;

  constructor(
    private rendererFactory: RendererFactory2,
    @Inject(DOCUMENT) private document
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
