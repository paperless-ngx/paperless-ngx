import { diacritics } from 'normalize-diacritics/diacritics'

export type SearchTextValue =
  string | number | boolean | bigint | null | undefined

const NON_ASCII = /[^\x00-\x7F]/
const SEPARATORS = /[^\p{L}\p{N}]+/u

export function normalizeSearchText(value: SearchTextValue): string {
  const text = String(value ?? '')

  // Nothing in the table matches ASCII, so skip normaliation
  if (!NON_ASCII.test(text)) return text.toLocaleLowerCase()

  const normalized = diacritics.reduce((text, replacement) => {
    return text.replace(replacement.diacritics, replacement.letter)
  }, text)

  return normalized.toLocaleLowerCase()
}

export function matchesSearchText(
  value: SearchTextValue,
  searchText: SearchTextValue
): boolean {
  const query = normalizeSearchText(searchText)
  const terms = query.split(SEPARATORS).filter(Boolean)

  // Empty or punctuation-only query, nothing to split into terms
  if (terms.length === 0) {
    return normalizeSearchText(value).includes(query.trim())
  }

  const words = normalizeSearchText(value).split(SEPARATORS).filter(Boolean)
  const claimed = new Array<boolean>(words.length).fill(false)

  // Each term takes a word of its own, longest first, so that "another tag th"
  // doesn't match "Another Tag" by finding the "th" inside "another"
  return terms
    .sort((a, b) => b.length - a.length)
    .every((term) => {
      for (let i = 0; i < words.length; i++) {
        if (!claimed[i] && words[i].includes(term)) {
          claimed[i] = true
          return true
        }
      }
      return false
    })
}
