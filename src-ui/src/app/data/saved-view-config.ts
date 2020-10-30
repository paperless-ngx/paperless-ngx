import { FilterRule } from './filter-rule';

export interface SavedViewConfig {

  id?: string

  filterRules: FilterRule[]

  sortField: string

  sortDirection: string

  title: string

  showInSideBar: boolean

  showInDashboard: boolean

}