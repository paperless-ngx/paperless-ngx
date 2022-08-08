import { ObjectWithId } from './object-with-id'
import { User } from './user'

export interface PaperlessDocumentComment extends ObjectWithId {
  created?: Date
  comment?: string
  user?: User
}
