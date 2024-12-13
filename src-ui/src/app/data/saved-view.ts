import { DisplayField, DisplayMode } from './document'
import { FilterRule } from './filter-rule'
import { ObjectWithPermissions } from './object-with-permissions'

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
