import { ObjectWithId } from './object-with-id'

export const MATCH_NONE = 0
export const MATCH_ANY = 1
export const MATCH_ALL = 2
export const MATCH_LITERAL = 3
export const MATCH_REGEX = 4
export const MATCH_FUZZY = 5
export const MATCH_AUTO = 6
export const DEFAULT_MATCHING_ALGORITHM = MATCH_AUTO

export const MATCHING_ALGORITHMS = [
  {
    id: MATCH_AUTO,
    shortName: $localize`Automatic`,
    name: $localize`Auto: Learn matching automatically`,
  },
  {
    id: MATCH_ANY,
    shortName: $localize`Any word`,
    name: $localize`Any: Document contains any of these words (space separated)`,
  },
  {
    id: MATCH_ALL,
    shortName: $localize`All words`,
    name: $localize`All: Document contains all of these words (space separated)`,
  },
  {
    id: MATCH_LITERAL,
    shortName: $localize`Exact match`,
    name: $localize`Exact: Document contains this string`,
  },
  {
    id: MATCH_REGEX,
    shortName: $localize`Regular expression`,
    name: $localize`Regular expression: Document matches this regular expression`,
  },
  {
    id: MATCH_FUZZY,
    shortName: $localize`Fuzzy word`,
    name: $localize`Fuzzy: Document contains a word similar to this word`,
  },
  {
    id: MATCH_NONE,
    shortName: $localize`None`,
    name: $localize`None: Disable matching`,
  },
]

export interface MatchingModel extends ObjectWithId {
  name?: string

  slug?: string

  match?: string

  matching_algorithm?: number

  is_insensitive?: boolean

  document_count?: number
}
