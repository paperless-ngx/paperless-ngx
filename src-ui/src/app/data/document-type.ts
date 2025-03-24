import { MatchingModel } from './matching-model'
import { Observable } from 'rxjs'
import { CustomField } from './custom-field'

export interface DocumentType extends MatchingModel {
  code?: string

  custom_fields?: number[] // [CustomField.id]
  custom_fields$?: Observable<CustomField[]>
}
