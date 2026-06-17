import { normalizeSync } from 'normalize-diacritics'

export type SearchTextValue =
  | string
  | number
  | boolean
  | bigint
  | null
  | undefined

export function normalizeSearchText(value: SearchTextValue): string {
  return normalizeSync(String(value ?? '')).toLocaleLowerCase()
}

export function matchesSearchText(
  value: SearchTextValue,
  searchText: SearchTextValue
): boolean {
  const normalizedValue = normalizeSearchText(value)
  const searchTerms = normalizeSearchText(searchText).trim().split(/\s+/)

  return searchTerms.every((term) => normalizedValue.includes(term))
}
