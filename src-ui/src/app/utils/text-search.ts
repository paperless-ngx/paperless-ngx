import { diacritics } from 'normalize-diacritics/diacritics'

export type SearchTextValue =
  string | number | boolean | bigint | null | undefined

export function normalizeSearchText(value: SearchTextValue): string {
  const normalized = diacritics.reduce(
    (text, replacement) => {
      return text.replace(replacement.diacritics, replacement.letter)
    },
    String(value ?? '')
  )

  return normalized.toLocaleLowerCase()
}

export function matchesSearchText(
  value: SearchTextValue,
  searchText: SearchTextValue
): boolean {
  const normalizedValue = normalizeSearchText(value)
  const searchTerms = normalizeSearchText(searchText).trim().split(/\s+/)

  return searchTerms.every((term) => normalizedValue.includes(term))
}
