import { FilterRule } from './filter-rule'
import { ObjectWithPermissions } from './object-with-permissions'

export enum DisplayMode {
  TABLE = 'table',
  SMALL_CARDS = 'smallCards',
}

export enum DocumentDisplayField {
  TITLE = 'title',
  CREATED = 'created',
  ADDED = 'added',
  TAGS = 'tag',
  CORRESPONDENT = 'correspondent',
  DOCUMENT_TYPE = 'documenttype',
  STORAGE_PATH = 'storagepath',
  CUSTOM_FIELD = 'custom_field_',
}

export const DOCUMENT_DISPLAY_FIELDS = [
  {
    id: DocumentDisplayField.TITLE,
    name: $localize`Title`,
  },
  {
    id: DocumentDisplayField.CREATED,
    name: $localize`Created`,
  },
  {
    id: DocumentDisplayField.ADDED,
    name: $localize`Added`,
  },
  {
    id: DocumentDisplayField.TAGS,
    name: $localize`Tags`,
  },
  {
    id: DocumentDisplayField.CORRESPONDENT,
    name: $localize`Correspondent`,
  },
  {
    id: DocumentDisplayField.DOCUMENT_TYPE,
    name: $localize`Document type`,
  },
  {
    id: DocumentDisplayField.STORAGE_PATH,
    name: $localize`Storage path`,
  },
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

  document_display_fields?: DocumentDisplayField[]
}
