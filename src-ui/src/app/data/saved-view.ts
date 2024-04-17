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
}

export interface SavedView extends ObjectWithPermissions {
  name?: string

  show_on_dashboard?: boolean

  show_in_sidebar?: boolean

  sort_field: string

  sort_reverse: boolean

  filter_rules: FilterRule[]

  dashboard_view_limit?: number

  dashboard_view_mode?: DashboardViewMode

  dashboard_view_table_columns?: DashboardViewTableColumn[]
}
