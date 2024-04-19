import { FilterRule } from './filter-rule'
import { ObjectWithPermissions } from './object-with-permissions'

export enum DisplayMode {
  TABLE = 'table',
  SMALL_CARDS = 'smallCards',
  LARGE_CARDS = 'largeCards',
}

export enum DisplayField {
  TITLE = 'title',
  CREATED = 'created',
  ADDED = 'added',
  TAGS = 'tag',
  CORRESPONDENT = 'correspondent',
  DOCUMENT_TYPE = 'documenttype',
  STORAGE_PATH = 'storagepath',
  CUSTOM_FIELD = 'custom_field_',
  NOTES = 'note',
  OWNER = 'owner',
  SHARED = 'shared',
  ASN = 'asn',
}

export const DEFAULT_DISPLAY_FIELDS = [
  {
    id: DisplayField.TITLE,
    name: $localize`Title`,
  },
  {
    id: DisplayField.CREATED,
    name: $localize`Created`,
  },
  {
    id: DisplayField.ADDED,
    name: $localize`Added`,
  },
  {
    id: DisplayField.TAGS,
    name: $localize`Tags`,
  },
  {
    id: DisplayField.CORRESPONDENT,
    name: $localize`Correspondent`,
  },
  {
    id: DisplayField.DOCUMENT_TYPE,
    name: $localize`Document type`,
  },
  {
    id: DisplayField.STORAGE_PATH,
    name: $localize`Storage path`,
  },
  {
    id: DisplayField.NOTES,
    name: $localize`Notes`,
  },
  {
    id: DisplayField.OWNER,
    name: $localize`Owner`,
  },
  {
    id: DisplayField.SHARED,
    name: $localize`Shared`,
  },
  {
    id: DisplayField.ASN,
    name: $localize`ASN`,
  },
]

export const DEFAULT_DASHBOARD_VIEW_PAGE_SIZE = 10

export const DEFAULT_DASHBOARD_DISPLAY_FIELDS = [
  DisplayField.CREATED,
  DisplayField.TITLE,
  DisplayField.TAGS,
  DisplayField.CORRESPONDENT,
]

export interface SavedView extends ObjectWithPermissions {
  name?: string

  show_on_dashboard?: boolean

  show_in_sidebar?: boolean

  sort_field: string

  sort_reverse: boolean

  filter_rules: FilterRule[]

  page_size?: number

  display_mode?: DisplayMode

  display_fields?: DisplayField[]
}
