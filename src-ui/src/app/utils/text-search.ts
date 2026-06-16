import { normalizeSync } from 'normalize-diacritics'

export function normalizeSearchText(value: unknown): string {
  return normalizeSync(String(value ?? '')).toLocaleLowerCase()
}

export function matchesSearchText(
  value: unknown,
  searchText: unknown
): boolean {
  return normalizeSearchText(value).includes(normalizeSearchText(searchText))
}
