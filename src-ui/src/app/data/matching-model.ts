import { ObjectWithId } from './object-with-id';


export const MATCH_ANY = 1
export const MATCH_ALL = 2
export const MATCH_LITERAL = 3
export const MATCH_REGEX = 4
export const MATCH_FUZZY = 5
export const MATCH_AUTO = 6

export const MATCHING_ALGORITHMS = [
    {id: MATCH_ANY, name: "Any"},
    {id: MATCH_ALL, name: "All"},
    {id: MATCH_LITERAL, name: "Literal"},
    {id: MATCH_REGEX, name: "Regular Expression"},
    {id: MATCH_FUZZY, name: "Fuzzy Match"},
    {id: MATCH_AUTO, name: "Auto"},
]

export interface MatchingModel extends ObjectWithId {

    name?: string

    slug?: string

    match?: string

    matching_algorithm?: number

    is_insensitive?: boolean

}
