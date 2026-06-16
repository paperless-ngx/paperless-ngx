import { normalizeSync } from 'normalize-diacritics'

export function matchesSearchText(
  value: unknown,
  searchText: unknown
): boolean {
  return normalizeSync(String(value))
    .toLocaleLowerCase()
    .includes(normalizeSync(String(searchText)).toLocaleLowerCase())
}
