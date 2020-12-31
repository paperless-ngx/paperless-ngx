import { ObjectWithId } from './object-with-id';


export const MATCH_ANY = 1
export const MATCH_ALL = 2
export const MATCH_LITERAL = 3
export const MATCH_REGEX = 4
export const MATCH_FUZZY = 5
export const MATCH_AUTO = 6

export const MATCHING_ALGORITHMS = [
    {id: MATCH_ANY, name: $localize`Any`},
    {id: MATCH_ALL, name: $localize`All`},
    {id: MATCH_LITERAL, name: $localize`Literal`},
    {id: MATCH_REGEX, name: $localize`Regular expression`},
    {id: MATCH_FUZZY, name: $localize`Fuzzy match`},
    {id: MATCH_AUTO, name: $localize`Auto`},
]

export interface MatchingModel extends ObjectWithId {

    name?: string

    slug?: string

    match?: string

    matching_algorithm?: number

    is_insensitive?: boolean

    document_count?: number

}
