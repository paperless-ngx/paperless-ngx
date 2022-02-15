import { FilterRule } from './filter-rule';
import { ObjectWithId } from './object-with-id';

export interface PaperlessSavedView extends ObjectWithId {

  name?: string

  show_on_dashboard?: boolean

  show_in_sidebar?: boolean

  sort_field: string

  sort_reverse: boolean

  filter_rules: FilterRule[]

}
