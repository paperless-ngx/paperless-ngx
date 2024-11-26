import { User } from './user'

export interface UiSettings {
  user: User
  settings: Object
  permissions: string[]
}

export interface UiSetting {
  key: string
  type: string
  default: any
}

export enum GlobalSearchType {
  ADVANCED = 'advanced',
  TITLE_CONTENT = 'title-content',
}

export const PAPERLESS_GREEN_HEX = '#17541f'

export const SETTINGS_KEYS = {
  LANGUAGE: 'language',
  APP_LOGO: 'app_logo',
  APP_TITLE: 'app_title',
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
  NOTES_ENABLED: 'general-settings:notes-enabled',
  AUDITLOG_ENABLED: 'general-settings:auditlog-enabled',
  SLIM_SIDEBAR: 'general-settings:slim-sidebar',
  UPDATE_CHECKING_ENABLED: 'general-settings:update-checking:enabled',
  UPDATE_CHECKING_BACKEND_SETTING:
    'general-settings:update-checking:backend-setting',
  SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE:
    'general-settings:saved-views:warn-on-unsaved-change',
  DASHBOARD_VIEWS_SORT_ORDER:
    'general-settings:saved-views:dashboard-views-sort-order',
  SIDEBAR_VIEWS_SORT_ORDER:
    'general-settings:saved-views:sidebar-views-sort-order',
  TOUR_COMPLETE: 'general-settings:tour-complete',
  DEFAULT_PERMS_OWNER: 'general-settings:permissions:default-owner',
  DEFAULT_PERMS_VIEW_USERS: 'general-settings:permissions:default-view-users',
  DEFAULT_PERMS_VIEW_GROUPS: 'general-settings:permissions:default-view-groups',
  DEFAULT_PERMS_EDIT_USERS: 'general-settings:permissions:default-edit-users',
  DEFAULT_PERMS_EDIT_GROUPS: 'general-settings:permissions:default-edit-groups',
  DOCUMENT_EDITING_REMOVE_INBOX_TAGS:
    'general-settings:document-editing:remove-inbox-tags',
  DOCUMENT_EDITING_OVERLAY_THUMBNAIL:
    'general-settings:document-editing:overlay-thumbnail',
  SEARCH_DB_ONLY: 'general-settings:search:db-only',
  SEARCH_FULL_TYPE: 'general-settings:search:more-link',
  EMPTY_TRASH_DELAY: 'trash_delay',
  GMAIL_OAUTH_URL: 'gmail_oauth_url',
  OUTLOOK_OAUTH_URL: 'outlook_oauth_url',
}

export const SETTINGS: UiSetting[] = [
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
    key: SETTINGS_KEYS.NOTES_ENABLED,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.AUDITLOG_ENABLED,
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
  {
    key: SETTINGS_KEYS.TOUR_COMPLETE,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.DEFAULT_PERMS_OWNER,
    type: 'number',
    default: undefined,
  },
  {
    key: SETTINGS_KEYS.DEFAULT_PERMS_VIEW_USERS,
    type: 'array',
    default: [],
  },
  {
    key: SETTINGS_KEYS.DEFAULT_PERMS_VIEW_GROUPS,
    type: 'array',
    default: [],
  },
  {
    key: SETTINGS_KEYS.DEFAULT_PERMS_EDIT_USERS,
    type: 'array',
    default: [],
  },
  {
    key: SETTINGS_KEYS.DEFAULT_PERMS_EDIT_GROUPS,
    type: 'array',
    default: [],
  },
  {
    key: SETTINGS_KEYS.DASHBOARD_VIEWS_SORT_ORDER,
    type: 'array',
    default: [],
  },
  {
    key: SETTINGS_KEYS.SIDEBAR_VIEWS_SORT_ORDER,
    type: 'array',
    default: [],
  },
  {
    key: SETTINGS_KEYS.APP_LOGO,
    type: 'string',
    default: '',
  },
  {
    key: SETTINGS_KEYS.APP_TITLE,
    type: 'string',
    default: '',
  },
  {
    key: SETTINGS_KEYS.DOCUMENT_EDITING_REMOVE_INBOX_TAGS,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.DOCUMENT_EDITING_OVERLAY_THUMBNAIL,
    type: 'boolean',
    default: true,
  },
  {
    key: SETTINGS_KEYS.SEARCH_DB_ONLY,
    type: 'boolean',
    default: false,
  },
  {
    key: SETTINGS_KEYS.SEARCH_FULL_TYPE,
    type: 'string',
    default: GlobalSearchType.TITLE_CONTENT,
  },
  {
    key: SETTINGS_KEYS.EMPTY_TRASH_DELAY,
    type: 'number',
    default: 30,
  },
  {
    key: SETTINGS_KEYS.GMAIL_OAUTH_URL,
    type: 'string',
    default: null,
  },
  {
    key: SETTINGS_KEYS.OUTLOOK_OAUTH_URL,
    type: 'string',
    default: null,
  },
]
