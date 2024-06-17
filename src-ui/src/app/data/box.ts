import { MatchingModel } from './matching-model'

export interface Box extends MatchingModel {

    type?: string

    parent_box?: number
}