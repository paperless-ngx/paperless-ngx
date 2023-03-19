import { ObjectWithId } from './object-with-id'

export interface PaperlessDocumentNote extends ObjectWithId {
  created?: Date
  note?: string
  user?: number // PaperlessUser
}
