import { ObjectWithId } from './object-with-id'

export interface PaperlessCustomFieldInstance extends ObjectWithId {
  document: number // PaperlessDocument
  field: number // PaperlessCustomField
  created: Date
}
