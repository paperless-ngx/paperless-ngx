import { MatchingModel } from './matching-model'

export interface CustomField extends MatchingModel {
  data_type: any

  type?: string

  parent_customfield?: number
}
