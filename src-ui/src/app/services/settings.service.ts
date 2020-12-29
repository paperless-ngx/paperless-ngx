import { Injectable } from '@angular/core';

export interface PaperlessSettings {
  key: string
  type: string
  default: any
}

export const SETTINGS_KEYS = {
  BULK_EDIT_CONFIRMATION_DIALOGS: 'general-settings:bulk-edit:confirmation-dialogs',
  BULK_EDIT_APPLY_ON_CLOSE: 'general-settings:bulk-edit:apply-on-close',
  DOCUMENT_LIST_SIZE: 'general-settings:documentListSize',
}

const SETTINGS: PaperlessSettings[] = [
  {key: SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS, type: "boolean", default: true},
  {key: SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE, type: "boolean", default: false},
  {key: SETTINGS_KEYS.DOCUMENT_LIST_SIZE, type: "number", default: 50}
]

@Injectable({
  providedIn: 'root'
})
export class SettingsService {

  constructor() { }

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
