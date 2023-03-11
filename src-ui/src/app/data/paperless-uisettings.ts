import { PaperlessUser } from './paperless-user'

export interface PaperlessUiSettings {
  user: PaperlessUser
  settings: Object
  permissions: string[]
}

export interface PaperlessUiSetting {
  key: string
  type: string
  default: any
}

export const SETTINGS_KEYS = {
  LANGUAGE: 'language',
  // maintain old general-settings: for backwards compatibility
  BULK_EDIT_CONFIRMATION_DIALOGS:
    'general-settings:bulk-edit:confirmation-dialogs',
  BULK_EDIT_APPLY_ON_CLOSE: 'general-settings:bulk-edit:apply-on-close',
  DOCUMENT_LIST_SIZE: 'general-settings:documentListSize',
  DARK_MODE_USE_SYSTEM: 'general-settings:dark-mode:use-system',
  DARK_MODE_ENABLED: 'general-settings:dark-mode:enabled',
  DARK_MODE_THUMB_INVERTED: 'general-settings:dark-mode:thumb-inverted',
  THEME_COLOR: 'general-settings:theme:color',
  USE_NATIVE_PDF_VIEWER: 'general-settings:document-details:native-pdf-viewer',
  DATE_LOCALE: 'general-settings:date-display:date-locale',
  DATE_FORMAT: 'general-settings:date-display:date-format',
  NOTIFICATIONS_CONSUMER_NEW_DOCUMENT:
    'general-settings:notifications:consumer-new-documents',
  NOTIFICATIONS_CONSUMER_SUCCESS:
    'general-settings:notifications:consumer-success',
  NOTIFICATIONS_CONSUMER_FAILED:
    'general-settings:notifications:consumer-failed',
  NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD:
    'general-settings:notifications:consumer-suppress-on-dashboard',
  COMMENTS_ENABLED: 'general-settings:comments-enabled',
  SLIM_SIDEBAR: 'general-settings:slim-sidebar',
  UPDATE_CHECKING_ENABLED: 'general-settings:update-checking:enabled',
  UPDATE_CHECKING_BACKEND_SETTING:
    'general-settings:update-checking:backend-setting',
  SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE:
    'general-settings:saved-views:warn-on-unsaved-change',
}

export const SETTINGS: PaperlessUiSetting[] = [
  {
    key: SETTINGS_KEYS.LANGUAGE,
    type: 'string',
    default: '',
  },
  {
    key: SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.SLIM_SIDEBAR,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.DOCUMENT_LIST_SIZE,
    type: 'number',
    default: 50,
  },
  {
    key: SETTINGS_KEYS.DARK_MODE_USE_SYSTEM,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.DARK_MODE_ENABLED,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.THEME_COLOR,
    type: 'string',
    default: '',
  },
  {
    key: SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.DATE_LOCALE,
    type: 'string',
    default: '',
  },
  {
    key: SETTINGS_KEYS.DATE_FORMAT,
    type: 'string',
    default: 'mediumDate',
  },
  {
    key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.COMMENTS_ENABLED,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.UPDATE_CHECKING_ENABLED,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.UPDATE_CHECKING_BACKEND_SETTING,
    type: 'string',
    default: '',
  },
  {
    key: SETTINGS_KEYS.SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE,
    type: 'boolean',
    default: true,
  },
]
