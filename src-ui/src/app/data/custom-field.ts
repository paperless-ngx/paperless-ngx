import { MatchingModel } from './matching-model'

export interface CustomField extends MatchingModel {

  type?: string

  parent_customfield?: number
}
