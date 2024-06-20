import { MatchingModel } from './matching-model'

export interface folders extends MatchingModel {

  type?: string

  parent_warehouse?: number

  path?: string
}