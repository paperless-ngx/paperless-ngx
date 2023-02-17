import { ObjectWithId } from './object-with-id'
import { PaperlessUser } from './paperless-user'

export interface PaperlessDocumentComment extends ObjectWithId {
  created?: Date
  comment?: string
  user?: PaperlessUser
}
