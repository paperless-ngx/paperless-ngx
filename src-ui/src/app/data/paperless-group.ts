import { ObjectWithId } from './object-with-id'

export interface PaperlessGroup extends ObjectWithId {
  name?: string

  user_count?: number // not implemented yet

  permissions?: string[]
}
