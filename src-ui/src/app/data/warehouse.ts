import { MatchingModel } from './matching-model'

export interface Warehouse extends MatchingModel {

  type?: string

  parent_warehouse?: number
}
