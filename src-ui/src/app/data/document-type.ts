import { MatchingModel } from './matching-model'

export interface DocumentType extends MatchingModel {
  code?: string

  assign_custom_fields?: number[] // [CustomField.id]
}
