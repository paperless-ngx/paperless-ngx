import { ObjectWithId } from './object-with-id'
import { PaperlessCustomField } from './paperless-custom-field'

export interface PaperlessCustomFieldInstance extends ObjectWithId {
  document: number // PaperlessDocument
  field: number // PaperlessCustomField
  created: Date
  value?: any
}
