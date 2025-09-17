import { MatchingModel } from './matching-model'

export interface Tag extends MatchingModel {
  color?: string

  text_color?: string

  is_inbox_tag?: boolean

  parent?: number // Tag ID

  children?: Tag[] // read-only

  // UI-only: computed depth and order for hierarchical dropdowns
  depth?: number
  orderIndex?: number
}
