import { ObjectWithId } from './object-with-id'

export interface CustomFieldInstance extends ObjectWithId {
  document: number // Document
  field: number // CustomField
  created: Date
  value?: any
}
