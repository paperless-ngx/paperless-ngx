import { MatchingModel } from './matching-model'

export interface Shelf extends MatchingModel {
    [x: string]: any
    data_type: any

    type?: string

    parent_shelf?: number
}