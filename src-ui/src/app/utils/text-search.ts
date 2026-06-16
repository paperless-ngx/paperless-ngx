import { normalizeSync } from 'normalize-diacritics'

export function normalizeSearchText(value: unknown): string {
  return normalizeSync(String(value ?? '')).toLocaleLowerCase()
}

export function matchesSearchText(
  value: unknown,
  searchText: unknown
): boolean {
  const normalizedValue = normalizeSearchText(value)
  const searchTerms = normalizeSearchText(searchText).trim().split(/\s+/)

  return searchTerms.every((term) => normalizedValue.includes(term))
}
