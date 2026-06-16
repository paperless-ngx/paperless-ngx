const EXTRA_DIACRITIC_REPLACEMENTS: Record<string, string> = {
  '\u00c6': 'AE',
  '\u00e6': 'ae',
  '\u00d0': 'D',
  '\u00f0': 'd',
  '\u00d8': 'O',
  '\u00f8': 'o',
  '\u00de': 'Th',
  '\u00fe': 'th',
  '\u0110': 'D',
  '\u0111': 'd',
  '\u0131': 'i',
  '\u0141': 'L',
  '\u0142': 'l',
  '\u0152': 'OE',
  '\u0153': 'oe',
  '\u00df': 'ss',
}

// ng-select has a similar private helper stripSpecialChars, but we can't use it
const EXTRA_DIACRITICS_PATTERN = new RegExp(
  `[${Object.keys(EXTRA_DIACRITIC_REPLACEMENTS).join('')}]`,
  'g'
)

function normalizeSearchText(value: unknown): string {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(
      EXTRA_DIACRITICS_PATTERN,
      (char) => EXTRA_DIACRITIC_REPLACEMENTS[char] ?? char
    )
    .toLocaleLowerCase()
}

export function matchesSearchText(
  value: unknown,
  searchText: unknown
): boolean {
  return normalizeSearchText(value).includes(normalizeSearchText(searchText))
}
