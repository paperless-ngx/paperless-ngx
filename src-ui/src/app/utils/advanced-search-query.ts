import {
  ADVANCED_SEARCH_DATE_KEYWORDS,
  ADVANCED_SEARCH_FIELD_KINDS,
  AdvancedSearchDateUnit,
  AdvancedSearchField,
  AdvancedSearchFieldKind,
  AdvancedSearchLogicalOperator,
  AdvancedSearchOperator,
  AdvancedSearchQueryAtom,
  AdvancedSearchQueryElement,
  AdvancedSearchQueryElementType,
  AdvancedSearchQueryGroup,
} from '../data/advanced-search-query'

// Anything the query grammar would read as syntax rather than as a word
const SYNTAX_CHARS = /[\s():"[\]*?,{}^~\\]/
const SYNTAX_CHARS_GLOBAL = new RegExp(SYNTAX_CHARS, 'g')
// A word wrapped in single quotes is also syntax, an apostrophe inside one is not
const EDGE_SINGLE_QUOTE = /^'|'$/
const RESERVED_WORDS = /^(AND|OR|NOT|TO)$/
const HAS_WORD_CHAR = /[\p{L}\p{N}]/u
const WHOLE_NUMBER = /^\d+$/
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

interface Serialized {
  text: string
  // The operator joining the top level of `text`, null when it is self-delimiting
  join:
    AdvancedSearchLogicalOperator.And | AdvancedSearchLogicalOperator.Or | null
}

const prefix = (field: AdvancedSearchField) => (field ? `${field}:` : '')

const quote = (text: string) => `"${text.replace(/"/g, '')}"`

const words = (value: string) =>
  value
    .trim()
    .split(/\s+/)
    .filter((word) => HAS_WORD_CHAR.test(word))

const word = (w: string) =>
  SYNTAX_CHARS.test(w) || EDGE_SINGLE_QUOTE.test(w) || RESERVED_WORDS.test(w)
    ? quote(w)
    : w

const atomic = (text: string): Serialized => ({ text, join: null })

function serializeWords(
  atom: AdvancedSearchQueryAtom,
  join: AdvancedSearchLogicalOperator.And | AdvancedSearchLogicalOperator.Or
): Serialized {
  // A field applies only to the word right after it, so repeat it per word
  const terms = words(atom.value ?? '').map(
    (w) => `${prefix(atom.field)}${word(w)}`
  )
  if (terms.length === 0) return null
  if (terms.length === 1) return atomic(terms[0])
  return { text: terms.join(` ${join} `), join }
}

function serializeRange(
  atom: AdvancedSearchQueryAtom,
  isValid: (v: string) => boolean
): Serialized {
  const lo = atom.value?.trim() ?? ''
  const hi = atom.valueTo?.trim() ?? ''
  const field = prefix(atom.field)
  switch (atom.operator) {
    case AdvancedSearchOperator.Equals:
      return isValid(lo) ? atomic(`${field}${lo}`) : null
    case AdvancedSearchOperator.AtLeast:
      return isValid(lo) ? atomic(`${field}[${lo} to]`) : null
    case AdvancedSearchOperator.AtMost:
      return isValid(lo) ? atomic(`${field}[to ${lo}]`) : null
    case AdvancedSearchOperator.Between:
      return isValid(lo) && isValid(hi)
        ? atomic(`${field}[${lo} to ${hi}]`)
        : null
  }
  return null
}

function serializeAtom(atom: AdvancedSearchQueryAtom): Serialized {
  const field = prefix(atom.field)
  const value = atom.value?.trim() ?? ''

  switch (atom.operator) {
    case AdvancedSearchOperator.AllWords:
      return serializeWords(atom, AdvancedSearchLogicalOperator.And)
    case AdvancedSearchOperator.AnyWord:
      return serializeWords(atom, AdvancedSearchLogicalOperator.Or)
    case AdvancedSearchOperator.Phrase:
      return HAS_WORD_CHAR.test(value)
        ? atomic(`${field}${quote(value)}`)
        : null
    case AdvancedSearchOperator.StartsWith: {
      if (/\s/.test(value)) return null
      let stem = value.replace(SYNTAX_CHARS_GLOBAL, '')
      if (!HAS_WORD_CHAR.test(stem)) return null
      // checksum is indexed as-is, in lowercase
      if (atom.field === AdvancedSearchField.Checksum) {
        stem = stem.toLowerCase()
      }
      return atomic(`${field}${stem}*`)
    }
    case AdvancedSearchOperator.DateKeyword:
      return (ADVANCED_SEARCH_DATE_KEYWORDS as readonly string[]).includes(
        value
      )
        ? atomic(`${field}${word(value)}`)
        : null
    case AdvancedSearchOperator.WithinLast: {
      const amount = parseInt(value, 10)
      const units = Object.values(AdvancedSearchDateUnit) as string[]
      if (!WHOLE_NUMBER.test(value) || amount < 1) return null
      if (!units.includes(atom.unit)) return null
      const unit = amount === 1 ? atom.unit : `${atom.unit}s`
      return atomic(`${field}[-${amount} ${unit} to now]`)
    }
    case AdvancedSearchOperator.Equals:
    case AdvancedSearchOperator.AtLeast:
    case AdvancedSearchOperator.AtMost:
    case AdvancedSearchOperator.Between:
      return serializeRange(
        atom,
        ADVANCED_SEARCH_FIELD_KINDS[atom.field] === AdvancedSearchFieldKind.Date
          ? (v) => ISO_DATE.test(v)
          : (v) => WHOLE_NUMBER.test(v)
      )
  }
  return null
}

function wrap(
  child: Serialized,
  parentJoin: AdvancedSearchLogicalOperator
): string {
  return child.join === null || child.join === parentJoin
    ? child.text
    : `(${child.text})`
}

function serializeGroup(group: AdvancedSearchQueryGroup): Serialized {
  const children = group.children.map(serializeElement).filter(Boolean)
  if (children.length === 0) return null

  if (group.operator === AdvancedSearchLogicalOperator.Not) {
    // A Not group matches documents matching none of its children
    if (children.length === 1 && children[0].join === null) {
      return atomic(`NOT ${children[0].text}`)
    }
    const inner =
      children.length === 1
        ? children[0].text
        : children
            .map((c) => wrap(c, AdvancedSearchLogicalOperator.Or))
            .join(' OR ')
    return atomic(`NOT (${inner})`)
  }

  if (children.length === 1) return children[0]
  return {
    text: children
      .map((c) => wrap(c, group.operator))
      .join(` ${group.operator} `),
    join: group.operator,
  }
}

function serializeElement(element: AdvancedSearchQueryElement): Serialized {
  return element.type === AdvancedSearchQueryElementType.Group
    ? serializeGroup(element)
    : serializeAtom(element)
}

/**
 * Writes an editor tree as a full-text query. Atoms that are not filled in
 * (or not valid) are left out, and empty groups with them.
 */
export function serializeAdvancedSearchQuery(
  element: AdvancedSearchQueryElement
): string {
  return serializeElement(element)?.text ?? ''
}
