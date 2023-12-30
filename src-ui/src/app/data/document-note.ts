import { ObjectWithId } from './object-with-id'

export interface DocumentNote extends ObjectWithId {
  created?: Date
  note?: string
  user?: number // User
}
