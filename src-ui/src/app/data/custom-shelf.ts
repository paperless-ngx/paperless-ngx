import { MatchingModel } from './matching-model'

export interface Shelf extends MatchingModel {
    data_type: any

    type?: string

    parent_shelf?: number
}