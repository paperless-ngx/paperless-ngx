import { FilterRule } from './filter-rule'
import { ObjectWithPermissions } from './object-with-permissions'

export enum DashboardViewMode {
  TABLE = 'table',
  SMALL_CARDS = 'small_cards',
}

export enum DashboardViewTableColumn {
  TITLE = 'title',
  CREATED = 'created',
  ADDED = 'added',
  TAGS = 'tag',
  CORRESPONDENT = 'correspondent',
  DOCUMENT_TYPE = 'documenttype',
  STORAGE_PATH = 'storagepath',
  CUSTOM_FIELD = 'custom_field_',
}

export const document_display_fields = [
  {
    id: DashboardViewTableColumn.TITLE,
    name: $localize`Title`,
  },
  {
    id: DashboardViewTableColumn.CREATED,
    name: $localize`Created`,
  },
  {
    id: DashboardViewTableColumn.ADDED,
    name: $localize`Added`,
  },
  {
    id: DashboardViewTableColumn.TAGS,
    name: $localize`Tags`,
  },
  {
    id: DashboardViewTableColumn.CORRESPONDENT,
    name: $localize`Correspondent`,
  },
  {
    id: DashboardViewTableColumn.DOCUMENT_TYPE,
    name: $localize`Document type`,
  },
  {
    id: DashboardViewTableColumn.STORAGE_PATH,
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

  dashboard_view_limit?: number

  dashboard_view_mode?: DashboardViewMode

  document_display_fields?: DashboardViewTableColumn[]
}
