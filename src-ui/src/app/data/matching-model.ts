import { ObjectWithId } from './object-with-id';

export class MatchingModel extends ObjectWithId {

    static MATCH_ANY = 1
    static MATCH_ALL = 2
    static MATCH_LITERAL = 3
    static MATCH_REGEX = 4
    static MATCH_FUZZY = 5
    static MATCH_AUTO = 6

    static MATCHING_ALGORITHMS = [
        {id: MatchingModel.MATCH_ANY, name: "Any"},
        {id: MatchingModel.MATCH_ALL, name: "All"},
        {id: MatchingModel.MATCH_LITERAL, name: "Literal"},
        {id: MatchingModel.MATCH_REGEX, name: "Regular Expression"},
        {id: MatchingModel.MATCH_FUZZY, name: "Fuzzy Match"},
        {id: MatchingModel.MATCH_AUTO, name: "Auto"},
    ]

    name?: string

    slug?: string

    match?: string

    matching_algorithm?: number

    is_insensitive?: boolean

}
