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

// --- Reading a query back into the editor --------------------------------
//
// Deliberately narrow: this reads the forms serializeAdvancedSearchQuery
// writes, and nothing else. A query it cannot read is not a failure, it just
// stays text, so there is never a lossy or surprising conversion. The final
// round-trip check below is what holds that promise: a tree is only returned
// when writing it out again reproduces the query exactly.

const RELATIVE_BOUND = /^-(\d+) (day|week|month|year)s?$/
const FIELD_PREFIX = /^([a-z_]+(?:\.[a-z_]+)?):/
const KEYWORD_TOKEN = /^(AND|OR|NOT)(?=[\s(]|$)/
// Either bound may be missing: [50 to 150], [50 to], [to 50]
const RANGE_BOUNDS = /^(?:(.+?) )?to(?: (.+))?$/
const TRAILING_WILDCARD = /^([^*?]+)\*$/

class UnreadableQuery extends Error {}

interface Token {
  type: 'term' | 'AND' | 'OR' | 'NOT' | '(' | ')'
  field?: string
  value?: string
  quoted?: boolean
  range?: boolean
}

// A parsed element, plus what it takes to merge the per-word terms the
// serializer writes for "contains all words" back into a single condition
interface Parsed {
  element: AdvancedSearchQueryElement
  word?: { field: AdvancedSearchField; text: string }
}

function tokenize(query: string): Token[] {
  const tokens: Token[] = []
  let i = 0
  while (i < query.length) {
    const rest = query.slice(i)
    if (/^\s/.test(rest)) {
      i++
      continue
    }
    if (rest[0] === '(' || rest[0] === ')') {
      tokens.push({ type: rest[0] as '(' | ')' })
      i++
      continue
    }
    const keyword = KEYWORD_TOKEN.exec(rest)
    if (keyword) {
      tokens.push({ type: keyword[1] as 'AND' | 'OR' | 'NOT' })
      i += keyword[1].length
      continue
    }
    const fieldMatch = FIELD_PREFIX.exec(rest)
    const field = fieldMatch ? fieldMatch[1] : ''
    i += fieldMatch ? fieldMatch[0].length : 0

    const value = query.slice(i)
    if (value.startsWith('"')) {
      const end = query.indexOf('"', i + 1)
      if (end < 0) throw new UnreadableQuery()
      tokens.push({
        type: 'term',
        field,
        value: query.slice(i + 1, end),
        quoted: true,
      })
      i = end + 1
    } else if (value.startsWith('[')) {
      const end = query.indexOf(']', i + 1)
      if (end < 0) throw new UnreadableQuery()
      tokens.push({
        type: 'term',
        field,
        value: query.slice(i + 1, end),
        range: true,
      })
      i = end + 1
    } else {
      const bare = /^[^\s()]+/.exec(value)
      if (!bare) throw new UnreadableQuery()
      tokens.push({ type: 'term', field, value: bare[0] })
      i += bare[0].length
    }
    // Nothing may run on directly after a value, e.g. title:"a"b
    if (i < query.length && !/[\s)]/.test(query[i])) throw new UnreadableQuery()
  }
  return tokens
}

function resolveField(name: string): AdvancedSearchField {
  const fields = Object.values(AdvancedSearchField) as string[]
  // Aliases (type:, path:, notes:) are left to the text box on purpose:
  // reading one would mean rewriting the user's query as it was read
  if (!fields.includes(name)) throw new UnreadableQuery()
  return name as AdvancedSearchField
}

function atomFrom(
  field: AdvancedSearchField,
  operator: AdvancedSearchOperator,
  value: string,
  extra: Partial<AdvancedSearchQueryAtom> = {}
): AdvancedSearchQueryAtom {
  return {
    type: AdvancedSearchQueryElementType.Atom,
    field,
    operator,
    value,
    ...extra,
  }
}

function parseRange(
  field: AdvancedSearchField,
  kind: AdvancedSearchFieldKind,
  body: string
): AdvancedSearchQueryAtom {
  const bounds = RANGE_BOUNDS.exec(body)
  if (!bounds) throw new UnreadableQuery()
  const lo = bounds[1] ?? ''
  const hi = bounds[2] ?? ''

  if (kind === AdvancedSearchFieldKind.Date) {
    const relative = RELATIVE_BOUND.exec(lo)
    if (relative && hi === 'now') {
      return atomFrom(field, AdvancedSearchOperator.WithinLast, relative[1], {
        unit: relative[2] as AdvancedSearchDateUnit,
      })
    }
  } else if (kind !== AdvancedSearchFieldKind.Number) {
    throw new UnreadableQuery()
  }

  const isValid =
    kind === AdvancedSearchFieldKind.Date
      ? (v: string) => ISO_DATE.test(v)
      : (v: string) => WHOLE_NUMBER.test(v)

  if (lo && hi) {
    if (!isValid(lo) || !isValid(hi)) throw new UnreadableQuery()
    return atomFrom(field, AdvancedSearchOperator.Between, lo, { valueTo: hi })
  }
  if (lo && isValid(lo))
    return atomFrom(field, AdvancedSearchOperator.AtLeast, lo)
  if (hi && isValid(hi))
    return atomFrom(field, AdvancedSearchOperator.AtMost, hi)
  throw new UnreadableQuery()
}

function parseTerm(token: Token): Parsed {
  const field = resolveField(token.field)
  const kind = ADVANCED_SEARCH_FIELD_KINDS[field]
  const value = token.value
  const isKeyword = (
    ADVANCED_SEARCH_DATE_KEYWORDS as readonly string[]
  ).includes(value)

  if (token.range) {
    return { element: parseRange(field, kind, value) }
  }

  if (kind === AdvancedSearchFieldKind.Date) {
    if (!isKeyword) throw new UnreadableQuery()
    return {
      element: atomFrom(field, AdvancedSearchOperator.DateKeyword, value),
    }
  }

  if (token.quoted) {
    if (kind !== AdvancedSearchFieldKind.Text) throw new UnreadableQuery()
    return { element: atomFrom(field, AdvancedSearchOperator.Phrase, value) }
  }

  const wildcard = TRAILING_WILDCARD.exec(value)
  if (wildcard) {
    if (kind === AdvancedSearchFieldKind.Number) throw new UnreadableQuery()
    return {
      element: atomFrom(field, AdvancedSearchOperator.StartsWith, wildcard[1]),
    }
  }

  if (kind === AdvancedSearchFieldKind.Number) {
    if (!WHOLE_NUMBER.test(value)) throw new UnreadableQuery()
    return { element: atomFrom(field, AdvancedSearchOperator.Equals, value) }
  }
  // A checksum is only ever searched by its first characters
  if (kind === AdvancedSearchFieldKind.Checksum) throw new UnreadableQuery()

  return {
    element: atomFrom(field, AdvancedSearchOperator.AllWords, value),
    word: { field, text: value },
  }
}

// The serializer repeats the field for every word, because a field applies
// only to the word after it. Put those back together into one condition.
function mergeWords(
  parts: Parsed[],
  operator: AdvancedSearchLogicalOperator.And | AdvancedSearchLogicalOperator.Or
): AdvancedSearchQueryElement[] {
  const merged: AdvancedSearchQueryElement[] = []
  for (let i = 0; i < parts.length; i++) {
    const run = [parts[i]]
    while (
      parts[i].word &&
      parts[i + 1]?.word &&
      parts[i + 1].word.field === parts[i].word.field
    ) {
      run.push(parts[++i])
    }
    if (run.length === 1) {
      merged.push(run[0].element)
      continue
    }
    merged.push(
      atomFrom(
        run[0].word.field,
        operator === AdvancedSearchLogicalOperator.And
          ? AdvancedSearchOperator.AllWords
          : AdvancedSearchOperator.AnyWord,
        run.map((part) => part.word.text).join(' ')
      )
    )
  }
  return merged
}

interface Cursor {
  tokens: Token[]
  at: number
}

function parseExpression(cursor: Cursor): Parsed {
  const parts: Parsed[] = [parseOperand(cursor)]
  let operator:
    AdvancedSearchLogicalOperator.And | AdvancedSearchLogicalOperator.Or
  while (
    cursor.tokens[cursor.at]?.type === 'AND' ||
    cursor.tokens[cursor.at]?.type === 'OR'
  ) {
    const next = cursor.tokens[cursor.at++].type as
      AdvancedSearchLogicalOperator.And | AdvancedSearchLogicalOperator.Or
    // One level mixing AND and OR is never something the editor wrote
    if (operator && next !== operator) throw new UnreadableQuery()
    operator = next
    parts.push(parseOperand(cursor))
  }
  if (parts.length === 1) return parts[0]

  const children = mergeWords(parts, operator)
  if (children.length === 1) return { element: children[0] }
  return {
    element: {
      type: AdvancedSearchQueryElementType.Group,
      operator,
      children,
    },
  }
}

function parseOperand(cursor: Cursor): Parsed {
  const token = cursor.tokens[cursor.at++]
  if (!token) throw new UnreadableQuery()

  if (token.type === 'NOT') {
    const child = parseOperand(cursor)
    return {
      element: {
        type: AdvancedSearchQueryElementType.Group,
        operator: AdvancedSearchLogicalOperator.Not,
        children: [child.element],
      },
    }
  }
  if (token.type === '(') {
    const inner = parseExpression(cursor)
    if (cursor.tokens[cursor.at++]?.type !== ')') throw new UnreadableQuery()
    return { element: inner.element }
  }
  if (token.type !== 'term') throw new UnreadableQuery()
  return parseTerm(token)
}

/**
 * Reads a query the editor could have written back into an editor tree, or
 * returns null when the editor cannot show it, in which case the query stays
 * text. Never returns a tree that would be written back differently.
 */
export function parseAdvancedSearchQuery(
  query: string
): AdvancedSearchQueryGroup | null {
  const trimmed = query?.trim() ?? ''
  if (!trimmed) return null

  let parsed: Parsed
  try {
    const cursor: Cursor = { tokens: tokenize(trimmed), at: 0 }
    parsed = parseExpression(cursor)
    if (cursor.at !== cursor.tokens.length) throw new UnreadableQuery()
  } catch {
    return null
  }

  const root =
    parsed.element.type === AdvancedSearchQueryElementType.Group
      ? parsed.element
      : {
          type: AdvancedSearchQueryElementType.Group as const,
          operator: AdvancedSearchLogicalOperator.And,
          children: [parsed.element],
        }

  return serializeAdvancedSearchQuery(root) === trimmed ? root : null
}
