import { ObjectWithId } from './object-with-id'
import { User } from './user'

export interface DocumentNote extends ObjectWithId {
  created?: Date
  note?: string
  user?: User
}
